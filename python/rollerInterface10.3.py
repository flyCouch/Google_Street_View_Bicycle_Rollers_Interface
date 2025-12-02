# python_simulator_bridge.py
# Reads the single RPM value from Arduino and translates it into 'ArrowUp' keyboard input.
# Motion can be toggled ON/OFF by pressing the 'Control + M' keys on the PC keyboard.

import serial
import time
import threading 
from pynput.keyboard import Key, Controller as KeyboardController, Listener

# --- CONFIGURATION ---
# IMPORTANT: Change this to match your Receiver Arduino's serial port
SERIAL_PORT = 'COM_PORT_HERE'
BAUD_RATE = 9600

# Speed thresholds (adjust these based on how fast you want Street View to advance)
RPM_FAST_THRESHOLD = 120.0 # RPM needed to hold the 'Up' key down
RPM_SLOW_THRESHOLD = 30.0  # RPM needed to tap the 'Up' key

# --- GLOBAL CONTROLLER ---
keyboard = KeyboardController()

# --- STATE VARIABLES ---
is_moving = False           # Tracks if the 'ArrowUp' key is currently being held down
is_motion_enabled = True    # Tracks if the script should send 'ArrowUp' signals (PC keyboard toggle)
is_control_pressed = False  # New: Tracks if the Control key is currently held down

# --- KEYBOARD LISTENER FUNCTIONS ---

def on_press(key):
    """Handles PC keyboard input to toggle motion on/off. Uses Control + M."""
    global is_motion_enabled, is_moving, is_control_pressed
    
    # 1. Track Control Key State
    if key == Key.ctrl_l or key == Key.ctrl_r:
        is_control_pressed = True
        return 

    # 2. Check for Control + M combination
    try:
        # Check if Control is held AND the key pressed is 'm'
        if is_control_pressed and hasattr(key, 'char') and key.char == 'm':
            is_motion_enabled = not is_motion_enabled
            print(f"--- MOTION TOGGLED (Ctrl+M): {'ENABLED' if is_motion_enabled else 'DISABLED'} ---")

            # If motion is disabled while moving, release the 'Up' key immediately
            if not is_motion_enabled and is_moving:
                 keyboard.release(Key.up)
                 is_moving = False
            
    except AttributeError:
        # Ignore special keys other than Control that don't have a 'char' property
        pass

def on_release(key):
    """Handles releasing modifier keys."""
    global is_control_pressed
    if key == Key.ctrl_l or key == Key.ctrl_r:
        is_control_pressed = False

def start_keyboard_listener():
    """Starts the pynput Listener in a non-blocking way, listening for both press and release."""
    # We pass both on_press and on_release functions
    listener = Listener(on_press=on_press, on_release=on_release)
    listener.start()
    return listener

# --- STREET VIEW MODE FUNCTION ---

def simulate_motion(current_rpm):
    """Translates RPM into 'ArrowUp' key presses ONLY if motion is enabled."""
    global is_moving, is_motion_enabled

    if not is_motion_enabled:
        return 100 # Motion is disabled, just maintain default read interval

    if current_rpm > RPM_FAST_THRESHOLD:
        # Fast Speed: Hold 'ArrowUp' key down for continuous movement
        if not is_moving:
            keyboard.press(Key.up)
            is_moving = True
        return 5 # Short delay for continuous reading

    elif current_rpm > RPM_SLOW_THRESHOLD:
        # Slow Speed: Tap 'ArrowUp' key intermittently for step-by-step movement
        if is_moving:
            keyboard.release(Key.up)
            is_moving = False
        keyboard.press(Key.up)
        keyboard.release(Key.up)
        return 100 # Longer delay for step-by-step tapping

    else:
        # Stop pedaling
        if is_moving:
            keyboard.release(Key.up)
            is_moving = False
        return 100 # Default read interval

# --- MAIN LOOP ---

def main():
    print("--- Starting Bike-to-Street View Bridge ---")
    
    # Start the PC keyboard listener thread
    listener = start_keyboard_listener()
    print("Toggle Motion: Press 'Control + M' on the PC keyboard.")

    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.1)
        ser.flushInput()
        print("Bridge established. Ready for RPM input.")
        print(f"Current Motion State: {'ENABLED' if is_motion_enabled else 'DISABLED'}")
    except serial.SerialException as e:
        print(f"ERROR: Could not open serial port {SERIAL_PORT}. Please check the port name and connection.")
        print(e)
        listener.stop() # Stop the listener if serial fails
        return

    while True:
        try:
            # Read line from Arduino (should be just the RPM value)
            line = ser.readline().decode('utf-8').strip()

            if line:
                # The data packet now only contains one part: RPM
                try:
                    rpm = float(line)

                    # --- INPUT MAPPING ---
                    delay_ms = simulate_motion(rpm)
                    
                    time.sleep(delay_ms / 1000.0)

                except ValueError:
                    # Ignore lines that are malformed 
                    pass

        except KeyboardInterrupt:
            print("\nShutting down bridge...")
            if is_moving:
                keyboard.release(Key.up)
            ser.close()
            listener.stop() # Stop the keyboard listener
            break
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            time.sleep(1) 

if __name__ == "__main__":
    main()
