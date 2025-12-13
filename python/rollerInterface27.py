# rollerInterface_Continuous.py - State Machine Driven
# Reads the single boolean 'spin' state from Arduino and translates it into continuous 'ArrowUp' keyboard input.
# The key is held down AS LONG AS the wheel is spinning (until the Arduino timeout).

import serial
import time
from pynput.keyboard import Key, Controller as KeyboardController
from pynput.mouse import Listener as MouseListener, Button

# --- CONFIGURATION ---
SERIAL_PORT = 'COM3'
BAUD_RATE = 9600

# --- GLOBAL CONTROLLER ---
keyboard = KeyboardController()

# --- STATE VARIABLES ---
is_moving = False           # Tracks if the 'ArrowUp' key is currently being held down
is_motion_enabled = True    # Tracks if the script should send 'ArrowUp' signals (Mouse Click toggle)

# --- MOUSE LISTENER FUNCTIONS ---

def on_click(x, y, button, pressed):
    """Handles mouse input to toggle motion on/off. Uses Middle Mouse Click."""
    global is_motion_enabled, is_moving
    
    # We only care about the moment the middle button is PRESSED down
    if button == Button.middle and pressed:
        is_motion_enabled = not is_motion_enabled
        print(f"--- TOGGLE: Motion is now {'ENABLED' if is_motion_enabled else 'DISABLED'} ---")

        # If motion is disabled, ensure the 'Up' key is released immediately
        if not is_motion_enabled and is_moving:
            keyboard.release(Key.up)
            is_moving = False
            print("ACTION: UP ARROW RELEASED (Motion Disabled)")

# --- KEYBOARD SIMULATION (STATE MACHINE) ---

def simulate_motion(spin_state):
    """
    Translates the boolean spin state into Key.up press/release actions.
    This holds the key down continuously while the Arduino sends 'True'.
    
    :param spin_state: True if spinning, False if not (i.e., wheel has stopped).
    """
    global is_moving, is_motion_enabled
    
    if not is_motion_enabled:
        return

    if spin_state and not is_moving:
        # START: Arduino sends True and key is not pressed -> Press the key and HOLD
        keyboard.press(Key.up)
        is_moving = True
        print("ACTION: UP ARROW PRESSED (START SPINNING)")

    elif not spin_state and is_moving:
        # STOP: Arduino sends False (due to timeout) and key is pressed -> Release the key
        keyboard.release(Key.up)
        is_moving = False
        print("ACTION: UP ARROW RELEASED (STOP SPINNING)")


# --- MAIN LOOP ---

def main():
    print("Starting bicycle-to-keyboard bridge (Continuous Mode)...")
    print("Motion can be toggled by performing a 'Middle Mouse Click'.")

    # Start the mouse listener thread
    listener = MouseListener(on_click=on_click)
    listener.start()
    print("Mouse listener started.")

    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.001)
        ser.flushInput()
        print("Bridge established. Ready for continuous SPIN state input.")
        print(f"Current Motion State: {'ENABLED' if is_motion_enabled else 'DISABLED'}")
    except serial.SerialException as e:
        print(f"ERROR: Could not open serial port {SERIAL_PORT}. Please check the port name and connection.")
        print(e)
        listener.stop() 
        return

    while True:
        try:
            # Read line from Arduino (should be just the boolean state '1' or '0')
            line = ser.readline().decode('utf-8').strip()

            if line:
                try:
                    # Convert the string '1' or '0' to a Python boolean
                    spin_state = bool(int(line))

                    # --- INPUT MAPPING ---
                    simulate_motion(spin_state)

                except ValueError:
                    # Ignore lines that are malformed 
                    pass

        except KeyboardInterrupt:
            print("\nShutting down bridge...")
            if is_moving:
                keyboard.release(Key.up)
            ser.close()
            listener.stop()
            break
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            time.sleep(1) 

if __name__ == "__main__":
    main()