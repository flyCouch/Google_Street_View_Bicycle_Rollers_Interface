# python_simulator_bridge.py
# Aggregates two inputs:
# 1. Bike RPM (via Serial) -> Controls 'ArrowUp' movement in Street View.
# 2. OpenTrack Head Position (via UDP) -> Controls Mouse Look.
# Motion can be toggled ON/OFF by pressing the 'Control + M' keys on the PC keyboard.

import serial
import time
import threading
import struct # Used to unpack binary FreeTrack data
import socket # Used for UDP listening
from pynput.keyboard import Key, Controller as KeyboardController, Listener

# --- CONFIGURATION ---
# IMPORTANT: Change this to match your Receiver Arduino's serial port
SERIAL_PORT = 'COM_PORT_HERE'
BAUD_RATE = 9600

# OpenTrack UDP Configuration
UDP_IP = "127.0.0.1" # Must match OpenTrack's IP
UDP_PORT = 4242      # Must match OpenTrack's Port (set to FreeTrack 2.0 Enhanced)
MOUSE_SENSITIVITY = 0.5 # Adjust for how quickly head movement translates to mouse movement

# Speed thresholds
RPM_FAST_THRESHOLD = 120.0
RPM_SLOW_THRESHOLD = 30.0

# --- GLOBAL CONTROLLER & STATE ---
keyboard = KeyboardController()

# Motion State
is_moving = False           # Tracks if 'ArrowUp' key is down
is_motion_enabled = True    # Toggled by Ctrl+M

# OpenTrack State
yaw = 0.0                   # Horizontal rotation (Left/Right)
pitch = 0.0                 # Vertical rotation (Up/Down)

# PC Keyboard State for Toggle
is_control_pressed = False 

# --- THREAD 1: KEYBOARD LISTENER (Ctrl+M Toggle) ---

def on_press(key):
    """Handles PC keyboard input to toggle motion on/off. Uses Control + M."""
    global is_motion_enabled, is_moving, is_control_pressed
    
    # 1. Track Control Key State
    if key == Key.ctrl_l or key == Key.ctrl_r:
        is_control_pressed = True
        return 

    # 2. Check for Control + M combination
    try:
        if is_control_pressed and hasattr(key, 'char') and key.char == 'm':
            is_motion_enabled = not is_motion_enabled
            print(f"--- MOTION TOGGLED (Ctrl+M): {'ENABLED' if is_motion_enabled else 'DISABLED'} ---")

            if not is_motion_enabled and is_moving:
                 keyboard.release(Key.up)
                 is_moving = False
            
    except AttributeError:
        pass

def on_release(key):
    """Handles releasing modifier keys."""
    global is_control_pressed
    if key == Key.ctrl_l or key == Key.ctrl_r:
        is_control_pressed = False

def start_keyboard_listener():
    """Starts the pynput Listener in a non-blocking way."""
    listener = Listener(on_press=on_press, on_release=on_release)
    listener.start()
    return listener


# --- THREAD 2: OPENTRACK UDP LISTENER (Steering Input) ---

def start_opentack_listener():
    """Listens for FreeTrack 2.0 data from OpenTrack via UDP."""
    global yaw, pitch
    
    # Create UDP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    # Set timeout so the thread doesn't block forever
    sock.settimeout(0.5) 
    
    try:
        sock.bind((UDP_IP, UDP_PORT))
        print(f"UDP Listener bound to {UDP_IP}:{UDP_PORT}. Waiting for OpenTrack data...")
    except OSError as e:
        print(f"ERROR: Could not bind to UDP port {UDP_PORT}. Ensure OpenTrack is configured correctly and not already running.")
        print(e)
        return

    # FreeTrack 2.0 Protocol uses a 36-byte structure (6 floats: X, Y, Z, Yaw, Pitch, Roll)
    # The format string is '<6f' (little-endian, 6 floats)
    while True:
        try:
            # Receive data packet (max 128 bytes)
            data, addr = sock.recvfrom(128) 
            
            # Check if the packet size matches the expected FreeTrack structure
            if len(data) == 24: # Standard FreeTrack (6 floats * 4 bytes/float = 24 bytes)
                
                # Unpack the binary data into 6 float values
                # Order: X, Y, Z, Yaw, Pitch, Roll
                unpacked_data = struct.unpack('<6f', data)
                
                # Yaw (Horizontal Look) is at index 3, Pitch (Vertical Look) is at index 4
                # Convert degrees to radians for pynput
                yaw = unpacked_data[3]
                pitch = unpacked_data[4]
                
        except socket.timeout:
            # Expected timeout if no data is received; just continue loop
            pass
        except struct.error:
            # Handle malformed packets (should not happen with OpenTrack)
            print("Warning: Received malformed FreeTrack packet.")
        except Exception as e:
            print(f"UDP Thread Error: {e}")
            break

# --- MOUSE MOVEMENT (Called in Main Loop) ---

def simulate_mouse_look():
    """Uses global yaw and pitch from OpenTrack to move the mouse pointer."""
    
    # yaw and pitch are typically measured in degrees. 
    # Move the mouse based on the head angle and sensitivity.
    
    # OpenTrack's Yaw: Negative moves head Left (mouse moves Left), Positive moves head Right (mouse moves Right)
    # Street View needs negative movement (left) and positive movement (right).
    move_x = int(yaw * MOUSE_SENSITIVITY)
    
    # OpenTrack's Pitch: Negative moves head Down (mouse moves Down), Positive moves head Up (mouse moves Up)
    # Street View needs negative movement (down) and positive movement (up).
    move_y = int(pitch * MOUSE_SENSITIVITY)

    if move_x != 0 or move_y != 0:
        mouse_controller.move(move_x, move_y)

# --- SPEED MOTION (Called in Main Loop) ---

def simulate_motion(current_rpm):
    """Translates RPM into 'ArrowUp' key presses ONLY if motion is enabled."""
    global is_moving, is_motion_enabled

    if not is_motion_enabled:
        return 100 

    if current_rpm > RPM_FAST_THRESHOLD:
        if not is_moving:
            keyboard.press(Key.up)
            is_moving = True
        return 5 

    elif current_rpm > RPM_SLOW_THRESHOLD:
        if is_moving:
            keyboard.release(Key.up)
            is_moving = False
        keyboard.press(Key.up)
        keyboard.release(Key.up)
        return 100 

    else:
        if is_moving:
            keyboard.release(Key.up)
            is_moving = False
        return 100 

# --- MAIN LOOP ---

# Initialize mouse controller here for use in simulate_mouse_look
mouse_controller = Controller() 

def main():
    print("--- Starting Bike-to-Street View Bridge (Dual Input) ---")
    
    # Start the PC keyboard listener thread (Ctrl+M)
    listener = start_keyboard_listener()
    print("Toggle Motion: Press 'Control + M' on the PC keyboard.")
    
    # Start the OpenTrack UDP listener thread
    udp_thread = threading.Thread(target=start_opentack_listener, daemon=True)
    udp_thread.start()

    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.1)
        ser.flushInput()
        print("Serial established. Ready for RPM input.")
        print(f"Current Motion State: {'ENABLED' if is_motion_enabled else 'DISABLED'}")
    except serial.SerialException as e:
        print(f"ERROR: Could not open serial port {SERIAL_PORT}. Please check the port name and connection.")
        print(e)
        listener.stop() 
        return

    # MAIN LOOP: Read serial data and simulate both controls
    while True:
        try:
            # 1. Handle Serial Data (RPM)
            line = ser.readline().decode('utf-8').strip()

            if line:
                try:
                    rpm = float(line)
                    delay_ms = simulate_motion(rpm)
                except ValueError:
                    delay_ms = 100 # Default delay if data is malformed
            else:
                 delay_ms = 100 # Default delay if no data received

            # 2. Handle UDP Data (Mouse Look)
            simulate_mouse_look()
            
            time.sleep(delay_ms / 1000.0)

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
