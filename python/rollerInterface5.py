# python_simulator_bridge.py
# Reads 8-part data from Arduino and translates it into keyboard/mouse inputs for the PC.
# Data Structure: RPM,SteerX,SteerY,LeftClick,RightClick,ScrollUp,ScrollDown,MotionToggle

import serial
import time
from pynput.keyboard import Key, Controller as KeyboardController
from pynput.mouse import Button, Controller as MouseController

# --- CONFIGURATION ---
# IMPORTANT: Change this to match your Receiver Arduino's serial port
SERIAL_PORT = 'COM_PORT_HERE'
BAUD_RATE = 9600

# Speed thresholds (adjust these based on how fast you want Street View to advance)
RPM_FAST_THRESHOLD = 120.0
RPM_SLOW_THRESHOLD = 30.0

# Steering thresholds (Joystick -100 to 100)
STEER_DEAD_ZONE = 10 

# Mouse Look Sensitivity 
MOUSE_SENSITIVITY = 1.0 

# --- GLOBAL CONTROLLERS ---
keyboard = KeyboardController()
mouse = MouseController()

# --- STATE VARIABLES ---
is_moving = False           # Tracks if the 'ArrowUp' key is currently being held down
is_left_down = False        # Tracks if the left mouse button is currently held down
is_right_down = False       # Tracks if the right mouse button is currently held down

# --- NEW TOGGLE STATE VARIABLES ---
is_motion_enabled = True        # Start with forward motion enabled
last_toggle_state = 0           # Tracks the previous state of the physical toggle button

def handle_motion_toggle(current_toggle_state):
    """
    Detects a press (transition from 0 to 1) of the momentary switch
    and flips the is_motion_enabled state.
    """
    global is_motion_enabled, last_toggle_state, is_moving
    
    # Press detected: Transition from released (0) to pressed (1)
    if current_toggle_state == 1 and last_toggle_state == 0:
        is_motion_enabled = not is_motion_enabled
        print(f"Motion Toggled: {'ENABLED' if is_motion_enabled else 'DISABLED'}")
        
        # Immediately stop movement if disabled
        if not is_motion_enabled and is_moving:
             keyboard.release(Key.up)
             is_moving = False

    last_toggle_state = current_toggle_state


def simulate_motion(current_rpm):
    """Translates RPM into 'ArrowUp' key presses ONLY if motion is enabled."""
    global is_moving, is_motion_enabled

    if not is_motion_enabled:
        return 100 # No motion, but keep checking inputs

    if current_rpm > RPM_FAST_THRESHOLD:
        # Fast Speed
        if not is_moving:
            keyboard.press(Key.up)
            is_moving = True
        return 5 

    elif current_rpm > RPM_SLOW_THRESHOLD:
        # Slow Speed
        if is_moving:
            keyboard.release(Key.up)
            is_moving = False
        keyboard.press(Key.up)
        keyboard.release(Key.up)
        return 100 

    else:
        # Stop pedaling
        if is_moving:
            keyboard.release(Key.up)
            is_moving = False
        return 100 

def simulate_mouse_look(steer_x, steer_y):
    """Translates Joystick XY input into continuous virtual mouse movement."""
    
    # Horizontal Movement (SteerX)
    move_x = 0
    if abs(steer_x) > STEER_DEAD_ZONE:
        move_x = int(steer_x * MOUSE_SENSITIVITY) 
        
    # Vertical Movement (SteerY)
    move_y = 0
    if abs(steer_y) > STEER_DEAD_ZONE:
        # Note: SteerY is mapped 100=up, -100=down in Arduino
        move_y = int(steer_y * MOUSE_SENSITIVITY)
        
    if move_x != 0 or move_y != 0:
        mouse.move(move_x, move_y)

def simulate_clicks(left_state, right_state):
    """Translates button states (0/1) into mouse clicks (press/release)."""
    global is_left_down, is_right_down
    
    # Left Click Logic
    if left_state == 1 and not is_left_down:
        mouse.press(Button.left)
        is_left_down = True
    elif left_state == 0 and is_left_down:
        mouse.release(Button.left)
        is_left_down = False

    # Right Click Logic
    if right_state == 1 and not is_right_down:
        mouse.press(Button.right)
        is_right_down = True
    elif right_state == 0 and is_right_down:
        mouse.release(Button.right)
        is_right_down = False

def simulate_scroll(scroll_up_state, scroll_down_state):
    """Translates Scroll Up/Down button states into Mouse Scroll events."""
    if scroll_up_state == 1 and scroll_down_state == 0:
        mouse.scroll(0, 1) # Scroll up/Zoom in
    elif scroll_down_state == 1 and scroll_up_state == 0:
        mouse.scroll(0, -1) # Scroll down/Zoom out
        
def main():
    print(f"Starting Serial Bridge on {SERIAL_PORT} @ {BAUD_RATE}...")
    
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.1)
        ser.flushInput()
        print("Bridge established. Press the Joystick Switch to toggle motion on/off.")
    except serial.SerialException as e:
        print(f"ERROR: Could not open serial port {SERIAL_PORT}. Please check the port name and connection.")
        print(e)
        return

    while True:
        try:
            # Read line from Arduino
            line = ser.readline().decode('utf-8').strip()

            if line:
                # Parse the data packet: RPM,SteerX,SteerY,LClick,RClick,ScrollUp,ScrollDown,MotionToggle
                parts = line.split(',')
                
                # Expecting exactly 8 parts
                if len(parts) == 8:
                    try:
                        rpm = float(parts[0])
                        steer_x = int(parts[1])
                        steer_y = int(parts[2])
                        left_click = int(parts[3])
                        right_click = int(parts[4])
                        scroll_up = int(parts[5])
                        scroll_down = int(parts[6])
                        motion_toggle = int(parts[7]) # NEW Toggle value

                        # --- INPUT MAPPING ---
                        handle_motion_toggle(motion_toggle) # Process the toggle first
                        simulate_mouse_look(steer_x, steer_y)
                        simulate_clicks(left_click, right_click)
                        simulate_scroll(scroll_up, scroll_down) 
                        
                        # Get delay from motion function (only proceeds if enabled)
                        delay_ms = simulate_motion(rpm)
                        
                        time.sleep(delay_ms / 1000.0)

                    except ValueError:
                        # Ignore lines that are malformed (e.g., during startup)
                        pass

        except KeyboardInterrupt:
            print("\nShutting down bridge...")
            if is_moving:
                keyboard.release(Key.up)
            # Ensure mouse buttons are released before exiting
            if is_left_down: mouse.release(Button.left)
            if is_right_down: mouse.release(Button.right)
            ser.close()
            break
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            time.sleep(1) # Wait a moment and try to continue

if __name__ == "__main__":
    main()
