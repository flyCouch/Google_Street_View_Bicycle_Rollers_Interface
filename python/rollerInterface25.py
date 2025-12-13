# python_simulator_bridge.py
# Reads the single boolean 'spin' value from Arduino and translates it into 'ArrowUp' keyboard input.
# Motion can be toggled ON/OFF by performing a 'Middle Mouse Click'.

import serial
import time
import threading 
from pynput.keyboard import Key, Controller as KeyboardController
from pynput.mouse import Listener as MouseListener, Button

# --- CONFIGURATION ---
SERIAL_PORT = 'COM3'
BAUD_RATE = 9600

# NEW VARIABLE: How long to hold the 'Up' key down when a spin pulse is received
KEY_HOLD_TIME_SECONDS = 0.5 

# --- GLOBAL CONTROLLER ---
keyboard = KeyboardController()

# --- STATE VARIABLES & LOCKS ---
is_moving = False           # Tracks if the 'ArrowUp' key is currently being held down
is_motion_enabled = True    # Tracks if the script should send 'ArrowUp' signals (Mouse Click toggle)
key_lock = threading.Lock() # Prevents multiple press threads from starting simultaneously

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
            # If a timed press is in progress, this stops it
            # (Note: The key_lock mechanism prevents re-triggering, not stopping an active sleep)
            # Since pynput doesn't offer a way to stop a sleep(), we just force the release.
            keyboard.release(Key.up)
            is_moving = False
            print("ACTION: UP ARROW RELEASED (Motion Disabled)")

# --- KEYBOARD SIMULATION ---

def key_press_and_release():
    """Presses the key, waits the configured time, and releases it."""
    global is_moving
    
    # 1. Acquire the lock and press the key
    with key_lock:
        if is_moving:
            # Another thread or pulse is already active, do nothing
            return
            
        is_moving = True
        keyboard.press(Key.up)
        print(f"ACTION: UP ARROW PRESSED for {KEY_HOLD_TIME_SECONDS}s")
    
    # 2. Hold the key
    time.sleep(KEY_HOLD_TIME_SECONDS)
    
    # 3. Release the key and free the state/lock
    keyboard.release(Key.up)
    is_moving = False
    print("ACTION: UP ARROW RELEASED")


def simulate_motion(spin_state):
    """
    Translates the boolean spin state into a timed Key.up action.
    
    :param spin_state: True if spinning pulse detected, False if not.
    """
    global is_motion_enabled
    
    if not is_motion_enabled:
        return

    # Check for a 'spin = true' pulse
    if spin_state:
        # Check if we are currently holding a key down OR if a timed press is already starting
        if not key_lock.locked():
            # Start the press and release sequence in a new, non-blocking thread
            thread = threading.Thread(target=key_press_and_release)
            thread.start()

    # Note: If spin_state is False, we do nothing. The release is handled by the thread.


# --- MAIN LOOP ---

def main():
    print("Starting bicycle-to-keyboard bridge...")
    print(f"Key will be held for {KEY_HOLD_TIME_SECONDS} seconds per spin pulse.")
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