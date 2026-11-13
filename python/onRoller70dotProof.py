# headTracker_roller_unified.py - Unified Orange Hat Tracking & Roller Bridge (EXE Ready)
# pip install pyserial pynput opencv-python numpy
import sys
import time
import os
import json
import threading
import traceback
import serial
import serial.tools.list_ports
from pynput.mouse import Controller as MouseCtrl, Button
from pynput.keyboard import Key, Controller as KeyboardController, Listener as KeyboardListener
import cv2
import numpy as np

# --- CONFIG & PROFILES ---
BAUD_RATE = 9600
ROLLER_DIA_MM = 81.0
CIRCUM_M = (ROLLER_DIA_MM * 3.1415926535) / 1000.0

DEFAULT_PROFILE = {
    "YAW_GAIN": 45, "PITCH_GAIN": 35,
    "X_DEAD": 0.04, "Z_DEAD": 0.03,
    "X_MAX": 0.25, "Z_MAX": 0.20,
    "X_PAN_GAIN": 4.0,
    "METERS_TO_TRIGGER": 10.0,  # Distance trigger for roller bridge
    "BAUD": 9600,
    "H_MIN": 5, "S_MIN": 120, "V_MIN": 120,
    "H_MAX": 25, "S_MAX": 255, "V_MAX": 255
}

PROFILE_FILE = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1].endswith(".json") else "streetview.json"
if not os.path.exists(PROFILE_FILE):
    with open(PROFILE_FILE, "w") as f:
        json.dump(DEFAULT_PROFILE, f, indent=2)
    PROFILE = DEFAULT_PROFILE
else:
    try:
        with open(PROFILE_FILE) as f:
            PROFILE = json.load(f)
    except:
        PROFILE = {}
    for k, v in DEFAULT_PROFILE.items():
        if PROFILE.get(k) is None:
            PROFILE[k] = v

X_DEAD = float(PROFILE["X_DEAD"])
Z_DEAD = float(PROFILE["Z_DEAD"])
X_MAX = float(PROFILE["X_MAX"])
Z_MAX = float(PROFILE["Z_MAX"])
X_PAN_GAIN = float(PROFILE["X_PAN_GAIN"])
meters_to_trigger = float(PROFILE.get("METERS_TO_TRIGGER", 10.0))

H_MIN = int(PROFILE["H_MIN"]); S_MIN = int(PROFILE["S_MIN"]); V_MIN = int(PROFILE["V_MIN"])
H_MAX = int(PROFILE["H_MAX"]); S_MAX = int(PROFILE["S_MAX"]); V_MAX = int(PROFILE["V_MAX"])

# --- STATE ---
mouse = MouseCtrl()
keyboard = KeyboardController()
tracking_on = False
neutral_x = neutral_z = None
meter_accumulator = 0.0
acc_lock = threading.Lock()
is_motion_enabled = True
is_running = True
ser = None
last_space_time = 0.0

def select_port():
    all_ports = list(serial.tools.list_ports.comports())
    ports = [p for p in all_ports if p.description != 'n/a' and p.hwid != 'n/a']
    
    if not ports:
        print("No active USB/Serial devices found!")
        print("Make sure Arduino is plugged in and not open in another app.")
        input("Press Enter to exit...")
        sys.exit(1)

    print("\n--- SELECT ROLLER PORT ---")
    for i, port in enumerate(ports):
        print(f" [{i}] Port: {port.device}")
        print(f"      Device: {port.description}")
        print(f"      HWID: {port.hwid}")
        print("-" * 40)

    while True:
        try:
            choice = input(f"Choose port index 0-{len(ports)-1}: ").strip()
            if choice.isdigit():
                idx = int(choice)
                if 0 <= idx < len(ports):
                    selected = ports[idx].device
                    print(f"-> Selected: {selected} ({ports[idx].description})\n")
                    return selected
            print(f"Invalid! Enter number 0 to {len(ports)-1}")
        except (EOFError, KeyboardInterrupt):
            sys.exit(0)

def on_press(key):
    global tracking_on, neutral_x, neutral_z, is_motion_enabled, meter_accumulator, is_running, last_space_time
    try:
        # Spacebar toggles head tracking ON/OFF
        if key == Key.space:
            now = time.time()
            if now - last_space_time > 0.3:
                last_space_time = now
                tracking_on = not tracking_on
                if tracking_on:
                    mouse.press(Button.left)
                else:
                    mouse.release(Button.left)
                print(f"\n[TRACKING] {'ON' :<10} (Left mouse down)")

        # 'c' key recenters tracking neutral points
        elif hasattr(key, 'char') and key.char and key.char.lower() == 'c':
            neutral_x = neutral_z = None
            print("\n[RECENTER] Head tracking neutral position reset.")

        # 'm' key toggles roller motion bridge
        elif hasattr(key, 'char') and key.char and key.char.lower() == 'm':
            with acc_lock:
                is_motion_enabled = not is_motion_enabled
                meter_accumulator = 0.0
            print(f"\n[TOGGLE] Roller Motion: {'ENABLED' if is_motion_enabled else 'DISABLED'}")

        # ESC exits completely
        elif key == Key.esc:
            print("\n[ESC] Shutting down...")
            is_running = False
            return False
    except Exception:
        pass

def serial_worker(port_name):
    global meter_accumulator, is_running, ser
    try:
        ser = serial.Serial(port_name, BAUD_RATE, timeout=0.1)
        ser.flushInput()
        print(f"[Serial] Opened {port_name} @ {BAUD_RATE}")
        
        while is_running:
            try:
                raw = ser.readline()
                if not raw:
                    continue
                line = raw.decode('utf-8', errors='ignore').strip()
            except Exception:
                continue

            if line == "1" and is_motion_enabled:
                with acc_lock:
                    meter_accumulator += CIRCUM_M
                    if meter_accumulator >= meters_to_trigger:
                        try:
                            keyboard.tap(Key.up)
                        except Exception as e:
                            print(f"\n[KeyTap Error] {e}")
                        meter_accumulator = 0.0
                        print(".", end="", flush=True)
    except Exception as e:
        print(f"\nSerial Error: {e}")
    finally:
        if ser and ser.is_open:
            try:
                ser.close()
                print(f"\n[Serial] Closed {port_name}")
            except:
                pass

def main():
    global is_running, neutral_x, neutral_z
    serial_port = select_port()
    
    # Start keyboard listener
    listener = KeyboardListener(on_press=on_press)
    listener.start()
    
    # Start background roller serial worker thread
    t = threading.Thread(target=serial_worker, args=(serial_port,), daemon=True)
    t.start()

    # Initialize Webcam for Orange Hat Tracking
    cap = cv2.VideoCapture(0, cv2.CAP_V4L2)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('M', 'J', 'P', 'G'))
    cap.set(3, 640)
    cap.set(4, 480)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    print("\n--- Unified Orange Hat Tracker & Roller Bridge ---")
    print(" SPACE = Toggle Head Tracking ON/OFF")
    print(" C     = Recenter neutral head position")
    print(" M     = Toggle roller motion bridge")
    print(" ESC   = Quit cleanly")
    print("-" * 60)

    window_title = "Orange Hat Tracker + Roller Bridge"
    missing_frames = 0
    cached_x_off = 0.0
    cached_z_off = 0.0

    try:
        while is_running:
            ret, frame = cap.read()
            if not ret:
                time.sleep(0.05)
                continue

            frame = cv2.flip(frame, 1)
            h, w = frame.shape[:2]

            # Convert frame to HSV for robust orange detection
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            lower_orange = np.array([H_MIN, S_MIN, V_MIN])
            upper_orange = np.array([H_MAX, S_MAX, V_MAX])
            mask = cv2.inRange(hsv, lower_orange, upper_orange)

            # Clean mask noise
            kernel = np.ones((5, 5), np.uint8)
            mask = cv2.erode(mask, kernel, iterations=1)
            mask = cv2.dilate(mask, kernel, iterations=2)

            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            found_current_frame = False
            x_off = z_off = 0.0

            if contours:
                largest_c = max(contours, key=cv2.contourArea)
                area = cv2.contourArea(largest_c)

                if area > 400:
                    ((x, y), radius) = cv2.minEnclosingCircle(largest_c)
                    if radius > 10:
                        cx = float(x) / w
                        x_off = cx - 0.5
                        norm_radius = radius / w
                        z_off = 0.15 - (norm_radius * 2)

                        cached_x_off, cached_z_off = x_off, z_off
                        missing_frames = 0
                        found_current_frame = True

                        cv2.circle(frame, (int(x), int(y)), int(radius), (0, 255, 0), 2)
                        cv2.circle(frame, (int(x), int(y)), 5, (0, 0, 255), -1)
                        cv2.putText(frame, f"ORANGE HAT LOCKED (Area: {int(area)})", (10, 30),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

            if not found_current_frame:
                missing_frames += 1
                if missing_frames <= 60:
                    x_off, z_off = cached_x_off, cached_z_off
                    tracked = True
                    cv2.putText(frame, "HOLDING ORANGE HAT...", (10, 30),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 165, 0), 2)
                else:
                    tracked = False
                    x_off = z_off = 0.0
                    cv2.putText(frame, "SEARCHING FOR ORANGE HAT...", (10, 30),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
            else:
                tracked = True

            # Smooth Head Tracking Controls (Tourist Trap Avoidance via Relative Movement & Keyboard Zoom)
            if tracked and tracking_on:
                if neutral_x is None:
                    neutral_x = x_off
                    neutral_z = z_off

                # Zoom via keyboard + / - keys to prevent random mouse-scroll clicks over UI elements
                if abs(z_off - neutral_z) > Z_DEAD:
                    key_to_tap = '+' if z_off > neutral_z else '-'
                    keyboard.press(key_to_tap)
                    keyboard.release(key_to_tap)

                # Smooth relative pan using exponential scaling curve
                if abs(x_off - neutral_x) > X_DEAD:
                    norm_x = min(abs(x_off - neutral_x) - X_DEAD, X_MAX) / X_MAX
                    speed = (norm_x ** 1.8) * X_PAN_GAIN
                    move_x = int(speed if (x_off - neutral_x) > 0 else -speed)
                    if move_x == 0:
                        move_x = 1 if (x_off - neutral_x) > 0 else -1
                    mouse.move(move_x, 0)

            cv2.imshow(window_title, frame)
            key_press = cv2.waitKey(1) & 0xFF
            if key_press == ord('q') or key_press == 27:
                is_running = False
                break

    except KeyboardInterrupt:
        is_running = False
    finally:
        is_running = False
        try:
            if tracking_on:
                mouse.release(Button.left)
            keyboard.release(Key.up)
        except:
            pass
        listener.stop()
        if ser and ser.is_open:
            try:
                ser.close()
            except:
                pass
        cap.release()
        cv2.destroyAllWindows()
        print("\n[INFO] Exited cleanly.")
        sys.exit(0)

if __name__ == "__main__":
    main()
