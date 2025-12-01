# python_simulator_bridge.py
# Reads data from Arduino and translates it into keyboard/mouse inputs for Google Street View.

import serial
import time
from pynput.keyboard import Key, Controller as KeyboardController
from pynput.mouse import Button, Controller as MouseController

# --- CONFIGURATION ---
# IMPORTANT: Change this to match your Arduino's serial port (e.g., 'COM3' on Windows or '/dev/ttyUSB0' on Linux/Mac)
SERIAL_PORT = 'COM_PORT_HERE'
BAUD_RATE = 9600

# Speed thresholds (adjust these based on how fast you want Street View to advance)
RPM_FAST_THRESHOLD = 120.0
RPM_SLOW_THRESHOLD = 30.0

# Steering thresholds (Joystick -100 to 100)
# Joystick movement below this value is considered 'dead zone' (no movement)
STEER_DEAD_ZONE = 10 

# Mouse Look Sensitivity (Higher value means faster mouse movement per joystick input)
MOUSE_SENSITIVITY = 1.0 

# --- GLOBAL CONTROLLERS ---
keyboard = KeyboardController()
mouse = MouseController()

# --- STATE VARIABLES ---
is_moving = False # Tracks if the 'ArrowUp' key is currently being held down

def simulate_motion(current_rpm):
    """Translates RPM into 'ArrowUp' key presses for forward motion."""
    global is_moving

    if current_rpm > RPM_FAST_THRESHOLD:
        # Fast Speed: Hold the key down for continuous smooth movement
        if not is_moving:
            keyboard.press(Key.up)
            is_moving = True
        # Return quick loop delay
        return 5 

    elif current_rpm > RPM_SLOW_THRESHOLD:
        # Slow Speed: Press the key briefly for small steps
        if is_moving:
            keyboard.release(Key.up)
            is_moving = False
        keyboard.press(Key.up)
        keyboard.release(Key.up)
        # Return longer loop delay for controlled steps
        return 100 

    else:
        # Stop: Release the key
        if is_moving:
            keyboard.release(Key.up)
            is_moving = False
        # Return longer loop delay when stopped
        return 100 

def simulate_mouse_look(steer_x, steer_y):
    """Translates Joystick XY input into continuous virtual mouse movement."""
    
    # Calculate movement only if outside the dead zone
    # Horizontal Movement (SteerX)
    move_x = 0
    if abs(steer_x) > STEER_DEAD_ZONE:
        # Scale the movement value by sensitivity
        move_x = int(steer_x * MOUSE_SENSITIVITY) 
        
    # Vertical Movement (SteerY)
    move_y = 0
    if abs(steer_y) > STEER_DEAD_ZONE:
        # Scale the movement value by sensitivity
        move_y = int(steer_y * MOUSE_SENSITIVITY)
        
    if move_x != 0 or move_y != 0:
        # Move the mouse relative to its current position
        mouse.move(move_x, move_y)


def simulate_zoom(zoom_change):
    """Translates Zoom Dial into Mouse Scroll for Street View internal zoom."""
    if zoom_change != 0:
        # Scroll up (positive) or down (negative)
        # This controls the internal Street View zoom/field of view
        mouse.scroll(0, zoom_change) 

def main():
    print(f"Starting Serial Bridge on {SERIAL_PORT} @ {BAUD_RATE}...")
    
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.1)
        ser.flushInput()
        print("Bridge established. Pedal to start simulation. Use joystick to look.")
    except serial.SerialException as e:
        print(f"ERROR: Could not open serial port {SERIAL_PORT}. Please check the port name and connection.")
        print(e)
        return

    while True:
        try:
            # Read line from Arduino
            line = ser.readline().decode('utf-8').strip()

            if line:
                # Parse the data packet: RPM,SteerX,SteerY,Zoom
                parts = line.split(',')
                # Expecting exactly 4 parts
                if len(parts) == 4:
                    try:
                        rpm = float(parts[0])
                        steer_x = int(parts[1])
                        steer_y = int(parts[2])
                        zoom = int(parts[3])

                        # --- INPUT MAPPING ---
                        simulate_mouse_look(steer_x, steer_y)
                        simulate_zoom(zoom)
                        
                        # Get delay from motion function to ensure responsiveness
                        delay_ms = simulate_motion(rpm)
                        
                        # Sleep for the calculated delay
                        time.sleep(delay_ms / 1000.0)

                    except ValueError:
                        # Ignore lines that are malformed (e.g., during startup)
                        pass

        except KeyboardInterrupt:
            print("\nShutting down bridge...")
            if is_moving:
                keyboard.release(Key.up)
            ser.close()
            break
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            time.sleep(1) # Wait a moment and try to continue

if __name__ == "__main__":
    main()
