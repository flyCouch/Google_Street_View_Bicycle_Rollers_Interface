# headTracker8hybrid_blob_only.py - High-Performance Version for Modern Hardware
import ctypes
try:
    x11 = ctypes.CDLL("libX11.so.6")
    x11.XInitThreads()
except Exception:
    pass

import time, sys, os, json, threading, traceback
import serial, serial.tools.list_ports
from pynput.mouse import Controller as MouseCtrl, Button
from pynput.keyboard import Controller as KeyCtrl, Key
from pynput import keyboard
import cv2
import numpy as np

mouse = MouseCtrl(); kbd = KeyCtrl()

DEFAULT_PROFILE = {
    "X_DEAD": 0.003, "Z_DEAD": 0.0008,
    "X_MAX": 0.08, "Z_MAX": 0.015,
    "X_PAN_GAIN": 375.0,
    "Y_PAN_GAIN": 22.0,
    "UP_DEAD": 0.025,
    "DOWN_DEAD": 0.005,
    "PITCH_UP_LIMIT": 12.0,
    "PITCH_DOWN_LIMIT": 30.0,
    "HORIZON_DRIFT_SPEED": 6.0,
    "YAW_DRIFT_SPEED": 18.0,
    "RPM_FAST": 45.0, "RPM_SLOW": 12.0,
    "BAUD": 9600,
    "H_MIN": 5, "S_MIN": 120, "V_MIN": 120,
    "H_MAX": 25, "S_MAX": 255, "V_MAX": 255
}

PROFILE_FILE = sys.argv[1] if len(sys.argv)>1 and sys.argv[1].endswith(".json") else "streetview.json"

if not os.path.exists(PROFILE_FILE):
    with open(PROFILE_FILE,"w") as f: json.dump(DEFAULT_PROFILE,f,indent=2)
    PROFILE = DEFAULT_PROFILE
else:
    try:
        with open(PROFILE_FILE) as f: PROFILE = json.load(f)
    except:
        PROFILE = {}
    for k, v in DEFAULT_PROFILE.items():
        if PROFILE.get(k) is None:
            PROFILE[k] = v

X_DEAD = float(PROFILE["X_DEAD"]); Z_DEAD = float(PROFILE["Z_DEAD"])
X_MAX = float(PROFILE["X_MAX"]); Z_MAX = float(PROFILE["Z_MAX"])
X_PAN_GAIN = float(PROFILE["X_PAN_GAIN"]); Y_PAN_GAIN = float(PROFILE["Y_PAN_GAIN"])
UP_DEAD = float(PROFILE.get("UP_DEAD", 0.025))
DOWN_DEAD = float(PROFILE.get("DOWN_DEAD", 0.005))
PITCH_UP_LIMIT = float(PROFILE["PITCH_UP_LIMIT"])
PITCH_DOWN_LIMIT = float(PROFILE["PITCH_DOWN_LIMIT"])
HORIZON_DRIFT_SPEED = float(PROFILE["HORIZON_DRIFT_SPEED"])
YAW_DRIFT_SPEED = float(PROFILE.get("YAW_DRIFT_SPEED", 18.0))
RPM_FAST_THRESHOLD = float(PROFILE["RPM_FAST"])
RPM_SLOW_THRESHOLD = float(PROFILE["RPM_SLOW"])
BAUD = int(PROFILE["BAUD"])

H_MIN = int(PROFILE["H_MIN"]); S_MIN = int(PROFILE["S_MIN"]); V_MIN = int(PROFILE["V_MIN"])
H_MAX = int(PROFILE["H_MAX"]); S_MAX = int(PROFILE["S_MAX"]); V_MAX = int(PROFILE["V_MAX"])

tracking_on = False; neutral_x = neutral_y = neutral_z = None
is_moving = False; pulses = 0; pulse_times = []
active_serial = None
last_space_time = 0.0
accumulated_pitch = 0.0
accumulated_yaw = 0.0
accumulated_zoom = 0.0

def curate_ports():
    ports = list(serial.tools.list_ports.comports()); curated = []
    for p in ports:
        if "bluetooth" in f"{p.description}".lower(): continue
        curated.append({"device": p.device, "desc": p.description, "score": 10 if "arduino" in p.description.lower() or "ch340" in p.description.lower() else 0, "arduino": True})
    curated.sort(key=lambda x: (-x["score"], x["device"])); return curated

def pick_port_manual():
    while True:
        cur = curate_ports()
        if not cur: print("No ports"); input(); continue
        for i, c in enumerate(cur): print(f" [{i}] {c['device']} {c['desc']}")
        sel = input(f"Pick 0-{len(cur)-1} [q=head only, r=rescan]: ").strip().lower()
        if sel == 'q': return None
        if sel == 'r': continue
        if sel.isdigit() and int(sel) < len(cur): return cur[int(sel)]["device"]

def calculate_rpm():
    global pulse_times; now = time.time()
    pulse_times = [t for t in pulse_times if now-t < 2.0]
    if len(pulse_times) < 2: return 0.0
    dur = pulse_times[-1] - pulse_times[0]
    return 0.0 if dur < 0.2 else (len(pulse_times)/dur)*60.0

def background_roller():
    global is_moving, pulses, pulse_times, active_serial
    last_signal_time = time.time()
    while True:
        try:
            if active_serial and active_serial.is_open:
                if active_serial.in_waiting > 0:
                    line = active_serial.readline().decode('utf-8', errors='ignore').strip()
                    if line:
                        last_signal_time = time.time()
                        rpm = 0.0
                        if line == "1" or "1" in line: 
                            pulse_times.append(time.time()); pulses += 1; rpm = calculate_rpm()
                        else:
                            try: rpm = float(line)
                            except: continue
                        
                        if rpm > RPM_FAST_THRESHOLD:
                            if not is_moving: kbd.press(Key.up); is_moving = True
                        elif rpm > RPM_SLOW_THRESHOLD:
                            if is_moving: kbd.release(Key.up); is_moving = False
                            kbd.press(Key.up); time.sleep(0.05); kbd.release(Key.up); time.sleep(0.15)
                        else:
                            if is_moving: kbd.release(Key.up); is_moving = False
                else:
                    if is_moving and (time.time() - last_signal_time > 0.35):
                        kbd.release(Key.up)
                        is_moving = False
                    time.sleep(0.001)
            else:
                time.sleep(0.1)
        except Exception as ex:
            time.sleep(0.5)

print(f"=== Initializing Arduino Roller Connection ===")
selected_port = pick_port_manual()

if selected_port:
    try:
        active_serial = serial.Serial(selected_port, BAUD, timeout=0.05)
        print("[INFO] Waiting for Arduino bootloader...")
        time.sleep(2.0)
        active_serial.flushInput()
        print(f"Connected successfully to {selected_port}")
        threading.Thread(target=background_roller, daemon=True).start()
    except Exception as e:
        print(f"[WARNING] Could not open port {selected_port}: {e}. Running head-only.")

print(f"Initializing Orange Hat Blob Tracking (High-Performance Mode)...")

def on_press(key):
    global tracking_on, neutral_x, neutral_y, neutral_z, accumulated_pitch, accumulated_yaw, accumulated_zoom, last_space_time
    try:
        if key == keyboard.Key.space:
            now = time.time()
            if now - last_space_time > 0.3:
                last_space_time = now
                tracking_on = not tracking_on
                if not tracking_on: mouse.release(Button.left)
                print(f"Tracking {'ON' if tracking_on else 'OFF'}")
        elif hasattr(key, 'char') and key.char and key.char.lower() == 'c':
            neutral_x = neutral_y = neutral_z = None
            accumulated_pitch = 0.0
            accumulated_yaw = 0.0
            accumulated_zoom = 0.0
            print("Recenter & Drift States Reset triggered")
        elif key == keyboard.Key.esc:
            sys.exit(0)
    except: pass

listener = keyboard.Listener(on_press=on_press)
listener.daemon = True
listener.start()

cap = cv2.VideoCapture(0, cv2.CAP_V4L2)
cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('M','J','P','G'))
cap.set(3, 640)
cap.set(4, 480)
cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

window_title = f"Orange Hat Tracker (High-Performance) - SPACE ON/OFF C center Q quit"

missing_frames = 0
cached_x_off = cached_y_off = cached_z_off = 0.0

try:
    while True:
        try:
            ret, frame = cap.read()
            if not ret: 
                time.sleep(0.01)
                continue
                
            frame = cv2.flip(frame, 1)
            h, w = frame.shape[:2]
            
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            lower_orange = np.array([H_MIN, S_MIN, V_MIN])
            upper_orange = np.array([H_MAX, S_MAX, V_MAX])
            mask = cv2.inRange(hsv, lower_orange, upper_orange)
            
            kernel = np.ones((5, 5), np.uint8)
            mask = cv2.erode(mask, kernel, iterations=1)
            mask = cv2.dilate(mask, kernel, iterations=2)
            
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            found_current_frame = False
            x_off = y_off = z_off = 0.0
            
            if contours:
                largest_c = max(contours, key=cv2.contourArea)
                area = cv2.contourArea(largest_c)
                
                if area > 400:
                    ((x, y), radius) = cv2.minEnclosingCircle(largest_c)
                    
                    if radius > 10:
                        cx = float(x) / w
                        cy = float(y) / h
                        x_off = cx - 0.5
                        y_off = cy - 0.5
                        
                        norm_radius = radius / w
                        z_off = norm_radius - 0.15 
                        
                        cached_x_off, cached_y_off, cached_z_off = x_off, y_off, z_off
                        missing_frames = 0
                        found_current_frame = True
                        
                        cv2.circle(frame, (int(x), int(y)), int(radius), (0, 255, 0), 2)
                        cv2.circle(frame, (int(x), int(y)), 5, (0, 0, 255), -1)
                        cv2.putText(frame, f"HP LOCKED", (10, 30), 
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            
            if not found_current_frame:
                missing_frames += 1
                if missing_frames <= 60:
                    x_off, y_off, z_off = cached_x_off, cached_y_off, cached_z_off
                    tracked = True
                    cv2.putText(frame, f"HOLDING...", (10, 30), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 165, 0), 2)
                else:
                    tracked = False
                    x_off = y_off = z_off = 0.0
                    cv2.putText(frame, f"SEARCHING...", (10, 30), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
            else:
                tracked = True

            if tracked and tracking_on:
                if neutral_x is None: 
                    neutral_x = x_off
                    neutral_y = y_off
                    neutral_z = z_off
                
                is_currently_moving = False
                
                # Damped Micro Zoom
                if abs(z_off - neutral_z) > Z_DEAD:
                    diff_z = (z_off - neutral_z) / Z_MAX
                    accumulated_zoom += diff_z * 3.0
                    scroll_steps = int(accumulated_zoom)
                    if scroll_steps != 0:
                        mouse.scroll(0, scroll_steps)
                        accumulated_zoom -= scroll_steps
                        time.sleep(0.01)
                    is_currently_moving = True
                else:
                    accumulated_zoom *= 0.8
                    
                # Yaw (X-Axis) with Hearty Auto-Centering Drift Return
                dx_head = x_off - neutral_x
                move_x = 0
                if abs(dx_head) > X_DEAD:
                    norm_x = min(abs(dx_head) - X_DEAD, X_MAX) / X_MAX
                    speed = (norm_x ** 0.5) * X_PAN_GAIN
                    step_x = int(-speed if dx_head > 0 else speed)
                    if step_x == 0: step_x = -10 if dx_head > 0 else 10
                    move_x = step_x
                    accumulated_yaw += move_x
                    is_currently_moving = True
                else:
                    if abs(accumulated_yaw) > 0.5:
                        drift_step_x = -np.sign(accumulated_yaw) * min(abs(accumulated_yaw), YAW_DRIFT_SPEED)
                        move_x = int(drift_step_x)
                        accumulated_yaw += drift_step_x
                        is_currently_moving = True
                    else:
                        accumulated_yaw = 0.0
                        move_x = 0

                if move_x != 0:
                    mouse.move(move_x, 0)

                # Pitch (Y-Axis) with Asymmetric Limits & Horizon Drift Return
                dy = y_off - neutral_y
                move_y = 0

                if dy > DOWN_DEAD:
                    norm_y = min((dy - DOWN_DEAD) / 0.08, 1.0)
                    step = -((norm_y ** 0.6) * Y_PAN_GAIN)
                    step = max(step, -PITCH_DOWN_LIMIT)
                    move_y = int(step)
                    accumulated_pitch += move_y
                    is_currently_moving = True
                elif dy < -UP_DEAD:
                    norm_y = min((abs(dy) - UP_DEAD) / 0.08, 1.0)
                    step = (norm_y ** 0.6) * Y_PAN_GAIN
                    step = min(step, PITCH_UP_LIMIT)
                    move_y = int(step)
                    accumulated_pitch += move_y
                    is_currently_moving = True
                else:
                    if abs(accumulated_pitch) > 0.5:
                        drift_step = -np.sign(accumulated_pitch) * min(abs(accumulated_pitch), HORIZON_DRIFT_SPEED)
                        move_y = int(drift_step)
                        accumulated_pitch += drift_step
                        is_currently_moving = True
                    else:
                        accumulated_pitch = 0.0
                        move_y = 0

                if move_y != 0:
                    mouse.move(0, move_y)

                # Dynamic Left Mouse Button Press
                if is_currently_moving:
                    try: mouse.press(Button.left)
                    except: pass
                else:
                    try: mouse.release(Button.left)
                    except: pass
            else:
                try: mouse.release(Button.left)
                except: pass

            cv2.imshow(window_title, frame)
            
            key_press = cv2.waitKey(1) & 0xFF
            if key_press == ord('q') or key_press == 27:
                print("\n[INFO] Shutting down...")
                break
                
        except Exception as loop_ex:
            print(f"[ERROR IN MAIN LOOP]: {loop_ex}")
            traceback.print_exc()
            time.sleep(0.05)

except KeyboardInterrupt:
    print("\n[INFO] Interrupted by user.")

finally:
    try:
        if tracking_on: mouse.release(Button.left)
        kbd.release(Key.up); kbd.release('+'); kbd.release('-')
    except:
        pass
    if active_serial and active_serial.is_open: active_serial.close()
    cap.release()
    cv2.destroyAllWindows()
    print("[INFO] Exited cleanly.")
    sys.exit(0)
