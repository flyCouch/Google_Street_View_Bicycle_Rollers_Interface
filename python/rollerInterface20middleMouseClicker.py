# python_simulator_bridge.py
# Reads the single RPM value from Arduino and translates it into 'ArrowUp' keyboard input.
# Motion can be toggled ON/OFF by performing a 'Middle Mouse Click'.

import serial
import time
import threading 
from pynput.keyboard import Key, Controller as KeyboardController
from pynput.mouse import Listener as MouseListener, Button, Controller as MouseController

# --- CONFIGURATION ---
# IMPORTANT: Change this to match your Receiver Arduino's serial port
SERIAL_PORT = 'COM_PORT_HERE'
BAUD_RATE = 9600

# Speed thresholds (adjust these based on how fast you want Street View to advance)
RPM_FAST_THRESHOLD = 120.0 # RPM needed to hold the 'Up' key down
RPM_SLOW_THRESHOLD = 30.0  # RPM needed to tap the 'Up' key

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
        print(f"--- MOTION TOGGLED (Middle Click): {'ENABLED' if is_motion_enabled else 'DISABLED'} ---")

        # If motion is disabled while the 'Up' key is held down, release it immediately
        if not is_motion_enabled and is_moving:
             keyboard.release(Key.up)
             is_moving = False

    # Return True to continue listening; returning False stops the listener.
    return True 

def start_mouse_listener():
    """Starts the pynput Mouse Listener in a non-blocking way, listening for clicks."""
    # We only pass the on_click function to handle all button events
    listener = MouseListener(on_click=on_click)
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
    print("--- Starting Bike-to-Street View Bridge (Mouse Toggle) ---")
    
    # Start the mouse listener thread
    listener = start_mouse_listener()
    print("Toggle Motion: Perform a 'Middle Mouse Click'.")

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
