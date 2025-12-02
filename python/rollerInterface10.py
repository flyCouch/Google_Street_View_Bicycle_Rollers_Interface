# python_simulator_bridge.py
# Reads the single RPM value from Arduino and translates it into 'ArrowUp' keyboard input.
# All other controls are assumed to be handled by the handlebar-mounted keyboard.

import serial
import time
from pynput.keyboard import Key, Controller as KeyboardController

# --- CONFIGURATION ---
# IMPORTANT: Change this to match your Receiver Arduino's serial port
SERIAL_PORT = 'COM_PORT_HERE'
BAUD_RATE = 9600

# Speed thresholds (adjust these based on how fast you want Street View to advance)
RPM_FAST_THRESHOLD = 120.0 # RPM needed to hold the 'Up' key down
RPM_SLOW_THRESHOLD = 30.0  # RPM needed to tap the 'Up' key

# --- GLOBAL CONTROLLER ---
keyboard = KeyboardController()

# --- STATE VARIABLE ---
is_moving = False           # Tracks if the 'ArrowUp' key is currently being held down

def simulate_motion(current_rpm):
    """Translates RPM into 'ArrowUp' key presses."""
    global is_moving

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
    print(f"Starting Serial Bridge on {SERIAL_PORT} @ {BAUD_RATE}...")
    
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.1)
        ser.flushInput()
        print("Bridge established. Ready for RPM input.")
    except serial.SerialException as e:
        print(f"ERROR: Could not open serial port {SERIAL_PORT}. Please check the port name and connection.")
        print(e)
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
            break
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            time.sleep(1) 

if __name__ == "__main__":
    main()
