# python_simulator_bridge.py
# Reads data from Arduino and translates it into keyboard/mouse inputs for the PC.
# Current data structure: RPM,SteerX,SteerY,LeftClick,RightClick,ScrollUp,ScrollDown

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
# Joystick movement below this value is considered 'dead zone' (no mouse movement)
STEER_DEAD_ZONE = 10 

# Mouse Look Sensitivity (Higher value means faster mouse movement per joystick input)
MOUSE_SENSITIVITY = 1.0 

# --- GLOBAL CONTROLLERS ---
keyboard = KeyboardController()
mouse = MouseController()

# --- STATE VARIABLES ---
is_moving = False     # Tracks if the 'ArrowUp' key is currently being held down
is_left_down = False  # Tracks if the left mouse button is currently held down
is_right_down = False # Tracks if the right mouse button is currently held down


def simulate_motion(current_rpm):
    """Translates RPM into 'ArrowUp' key presses for forward motion."""
    global is_moving

    if current_rpm > RPM_FAST_THRESHOLD:
        # Fast Speed: Hold the key down for continuous smooth movement
        if not is_moving:
            keyboard.press(Key.up)
            is_moving = True
        return 5 

    elif current_rpm > RPM_SLOW_THRESHOLD:
        # Slow Speed: Press the key briefly for small steps
        if is_moving:
            keyboard.release(Key.up)
            is_moving = False
        keyboard.press(Key.up)
        keyboard.release(Key.up)
        return 100 

    else:
        # Stop: Release the key
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
        # Positive value scrolls up (or zooms in in Street View)
        # Note: A scroll value of 1 is usually sufficient for a single step
        mouse.scroll(0, 1) 
    elif scroll_down_state == 1 and scroll_up_state == 0:
        # Negative value scrolls down (or zooms out in Street View)
        mouse.scroll(0, -1)
        
def main():
    print(f"Starting Serial Bridge on {SERIAL_PORT} @ {BAUD_RATE}...")
    
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.1)
        ser.flushInput()
        print("Bridge established. Pedal, steer, click, and scroll.")
    except serial.SerialException as e:
        print(f"ERROR: Could not open serial port {SERIAL_PORT}. Please check the port name and connection.")
        print(e)
        return

    while True:
        try:
            # Read line from Arduino
            line = ser.readline().decode('utf-8').strip()

            if line:
                # Parse the data packet: RPM,SteerX,SteerY,LeftClick,RightClick,ScrollUp,ScrollDown
                parts = line.split(',')
                # Expecting exactly 7 parts
                if len(parts) == 7:
                    try:
                        rpm = float(parts[0])
                        steer_x = int(parts[1])
                        steer_y = int(parts[2])
                        left_click = int(parts[3])
                        right_click = int(parts[4])
                        scroll_up = int(parts[5])
                        scroll_down = int(parts[6])

                        # --- INPUT MAPPING ---
                        simulate_mouse_look(steer_x, steer_y)
                        simulate_clicks(left_click, right_click)
                        simulate_scroll(scroll_up, scroll_down) 
                        
                        # Get delay from motion function to ensure responsiveness
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
