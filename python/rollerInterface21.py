# python_simulator_bridge.py
# Reads the single boolean 'spin' value from Arduino and translates it into 'ArrowUp' keyboard input.
# Motion can be toggled ON/OFF by performing a 'Middle Mouse Click'.

import serial
import time
import threading 
from pynput.keyboard import Key, Controller as KeyboardController
from pynput.mouse import Listener as MouseListener, Button, Controller as MouseController

# --- CONFIGURATION ---
# IMPORTANT: Change this to match your Receiver Arduino's serial port
SERIAL_PORT = 'COM3'
BAUD_RATE = 9600

# RPM thresholds are now OBSOLETE. The logic is now direct True/False state mapping.

# --- GLOBAL CONTROLLER ---
keyboard = KeyboardController()
# We don't need the MouseController instance for input *control*, only for *listening*

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

# --- KEYBOARD SIMULATION ---

def simulate_motion(spin_state):
    """
    Translates the boolean spin state into Key.up press/release actions.
    
    :param spin_state: True if spinning, False if not.
    """
    global is_moving, is_motion_enabled
    
    if not is_motion_enabled:
        # Do nothing if motion is disabled (the on_click handler ensures key is released)
        return

    if spin_state and not is_moving:
        # START: Spinning is True and key is not pressed -> Press the key
        keyboard.press(Key.up)
        is_moving = True
        print("ACTION: UP ARROW PRESSED (START SPINNING)")

    elif not spin_state and is_moving:
        # STOP: Spinning is False and key is pressed -> Release the key
        keyboard.release(Key.up)
        is_moving = False
        print("ACTION: UP ARROW RELEASED (STOP SPINNING)")
        
    # If state is spin=True and is_moving=True, do nothing (maintain press)
    # If state is spin=False and is_moving=False, do nothing (maintain release)


# --- MAIN LOOP ---

def main():
    print("Starting bicycle-to-keyboard bridge...")
    print("Motion can be toggled by performing a 'Middle Mouse Click'.")

    # Start the mouse listener thread
    listener = MouseListener(on_click=on_click)
    listener.start()
    print("Mouse listener started.")

    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.1)
        ser.flushInput()
        print("Bridge established. Ready for SPIN input.")
        print(f"Current Motion State: {'ENABLED' if is_motion_enabled else 'DISABLED'}")
    except serial.SerialException as e:
        print(f"ERROR: Could not open serial port {SERIAL_PORT}. Please check the port name and connection.")
        print(e)
        listener.stop() # Stop the listener if serial fails
        return

    while True:
        try:
            # Read line from Arduino (should be just the boolean state '1' or '0')
            line = ser.readline().decode('utf-8').strip()

            if line:
                # The data packet now only contains one part: '1' (True) or '0' (False)
                try:
                    # Convert the string '1' or '0' to a Python boolean
                    # int('1') -> 1. bool(1) -> True.
                    # int('0') -> 0. bool(0) -> False.
                    spin_state = bool(int(line))

                    # --- INPUT MAPPING ---
                    simulate_motion(spin_state)
                    
                    # time.sleep(delay_ms / 1000.0) # check this Ron -> NO LONGER NEEDED FOR STATE MACHINE

                except ValueError:
                    # Ignore lines that are malformed (like initial setup messages or malformed data)
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
            # If an error occurs, wait a moment before trying to read again
            time.sleep(1) 

if __name__ == "__main__":
    main()