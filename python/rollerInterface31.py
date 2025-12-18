# rollerInterface_m_Key.py
# Reads the 'spin' state from Arduino and holds 'ArrowUp' while spinning.
# Press the 'm' key to toggle motion ON or OFF.

import serial
import time
from pynput.keyboard import Key, Controller as KeyboardController, Listener as KeyboardListener

# --- CONFIGURATION ---
SERIAL_PORT = 'COM3'
BAUD_RATE = 9600

# --- GLOBAL CONTROLLER ---
keyboard = KeyboardController()

# --- STATE VARIABLES ---
is_moving = False           # Tracks if 'ArrowUp' is currently held down
is_motion_enabled = True    # Tracks if motion is enabled (toggled by 'm' key)

# --- KEYBOARD LISTENER (TOGGLE) ---

def on_press(key):
    """Handles keyboard input to toggle motion on/off using the 'm' key."""
    global is_motion_enabled, is_moving
    
    try:
        # Check if the alphanumeric key 'm' was pressed
        if key.char == 'm':
            is_motion_enabled = not is_motion_enabled
            print(f"--- TOGGLE: Motion is now {'ENABLED' if is_motion_enabled else 'DISABLED'} ---")

            # If motion is disabled while moving, release the 'Up' key immediately
            if not is_motion_enabled and is_moving:
                keyboard.release(Key.up)
                is_moving = False
                print("ACTION: UP ARROW RELEASED (Motion Disabled)")
    except AttributeError:
        # Ignore special keys (Shift, Ctrl, etc.) which do not have a .char attribute
        pass

# --- MOTION SIMULATION (STATE MACHINE) ---

def simulate_motion(spin_state):
    """
    Holds the 'Up' key down continuously while spin_state is True.
    Releases it when spin_state is False (based on Arduino timeout).
    """
    global is_moving, is_motion_enabled
    
    if not is_motion_enabled:
        return

    if spin_state and not is_moving:
        # START: Arduino detects spinning and key is currently UP
        keyboard.press(Key.up)
        is_moving = True
        print("ACTION: UP ARROW PRESSED (START SPINNING)")

    elif not spin_state and is_moving:
        # STOP: Arduino timeout reached (not spinning) and key is currently DOWN
        keyboard.release(Key.up)
        is_moving = False
        print("ACTION: UP ARROW RELEASED (STOP SPINNING)")

# --- MAIN LOOP ---

def main():
    print("Starting bicycle-to-keyboard bridge...")
    print("Motion Toggle: Press the 'm' key on your keyboard.")

    # Start the keyboard listener in a non-blocking thread
    listener = KeyboardListener(on_press=on_press)
    listener.start()
    print("Keyboard listener started.")

    try:
        # Aggressive timeout (1ms) for high responsiveness
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.001)
        ser.flushInput()
        print("Bridge established. Ready for SPIN state input.")
        print(f"Current Motion State: {'ENABLED' if is_motion_enabled else 'DISABLED'}")

    except serial.SerialException as e:
        print(f"ERROR: Could not open serial port {SERIAL_PORT}.")
        print(e)
        listener.stop() 
        return

    while True:
        try:
            # Read state from Arduino ('1' or '0')
            line = ser.readline().decode('utf-8').strip()

            if line:
                try:
                    # Convert '1'/'0' to True/False
                    spin_state = bool(int(line))
                    simulate_motion(spin_state)
                except ValueError:
                    pass

        except KeyboardInterrupt:
            print("\nShutting down...")
            if is_moving:
                keyboard.release(Key.up)
            ser.close()
            listener.stop()
            break
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(1) 

if __name__ == "__main__":
    main()