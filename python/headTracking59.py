# headTracking59.py - v10 FINAL - copy/paste ready - F11 safe
import os
os.environ["QT_LOGGING_RULES"] = "*.debug=false;qt.qpa.*=false;qt.qpa.fonts=false"

import ctypes
try:
    x11 = ctypes.CDLL("libX11.so.6")
    x11.XInitThreads()
except Exception:
    pass

import time
import sys
import json
import threading
import subprocess
import shutil
import serial
import serial.tools.list_ports
from pynput.mouse import Controller as MouseCtrl, Button
from pynput.keyboard import Controller as KeyCtrl, Key
from pynput import keyboard
import cv2
import numpy as np

mouse = MouseCtrl()
kbd = KeyCtrl()
HAS_XDOTOOL = shutil.which("xdotool") is not None

def press_up():
    try:
        if HAS_XDOTOOL:
            subprocess.Popen(["xdotool", "keydown", "Up"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            kbd.press(Key.up)
    except Exception:
        try:
            kbd.press(Key.up)
        except Exception:
            pass

def release_up():
    try:
        if HAS_XDOTOOL:
            subprocess.Popen(["xdotool", "keyup", "Up"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            kbd.release(Key.up)
    except Exception:
        try:
            kbd.release(Key.up)
        except Exception:
            pass

# YOUR TUNE - no planet zoom
DEFAULT_PROFILE = {
    "X_DEAD": 0.02,
    "Z_DEAD": 0.12,
    "X_MAX": 0.18,
    "Z_MAX": 0.3,
    "X_PAN_GAIN": 250.0,
    "Y_PAN_GAIN": 35.0,
    "UP_DEAD": 0.1,
    "DOWN_DEAD": 0.1,
    "PITCH_UP_LIMIT": 12.0,
    "PITCH_DOWN_LIMIT": 10.0,
    "HORIZON_DRIFT_SPEED": 10.0,
    "YAW_DRIFT_SPEED": 6.0,
    "RPM_FAST": 45.0,
    "RPM_SLOW": 12.0,
    "BAUD": 9600,
    "H_MIN": 5,
    "S_MIN": 120,
    "V_MIN": 120,
    "H_MAX": 25,
    "S_MAX": 255,
    "V_MAX": 255,
    "ZOOM_GAIN": 1.0,
    "ZOOM_ENABLED": 0
}

PROFILE_FILE = "streetview.json"
if not os.path.exists(PROFILE_FILE):
    with open(PROFILE_FILE, "w") as f:
        json.dump(DEFAULT_PROFILE, f, indent=2)
    PROFILE = DEFAULT_PROFILE
else:
    try:
        with open(PROFILE_FILE) as f:
            PROFILE = json.load(f)
    except Exception:
        PROFILE = {}
    for k, v in DEFAULT_PROFILE.items():
        if PROFILE.get(k) is None:
            PROFILE[k] = v

X_DEAD = float(PROFILE["X_DEAD"])
Z_DEAD = float(PROFILE["Z_DEAD"])
X_MAX = float(PROFILE["X_MAX"])
Z_MAX = float(PROFILE["Z_MAX"])
X_PAN_GAIN = float(PROFILE["X_PAN_GAIN"])
Y_PAN_GAIN = float(PROFILE["Y_PAN_GAIN"])
UP_DEAD = float(PROFILE["UP_DEAD"])
DOWN_DEAD = float(PROFILE["DOWN_DEAD"])
PITCH_UP_LIMIT = float(PROFILE["PITCH_UP_LIMIT"])
PITCH_DOWN_LIMIT = float(PROFILE["PITCH_DOWN_LIMIT"])
HORIZON_DRIFT_SPEED = float(PROFILE["HORIZON_DRIFT_SPEED"])
YAW_DRIFT_SPEED = float(PROFILE["YAW_DRIFT_SPEED"])
BAUD = int(PROFILE["BAUD"])
H_MIN = int(PROFILE["H_MIN"])
S_MIN = int(PROFILE["S_MIN"])
V_MIN = int(PROFILE["V_MIN"])
H_MAX = int(PROFILE["H_MAX"])
S_MAX = int(PROFILE["S_MAX"])
V_MAX = int(PROFILE["V_MAX"])
ZOOM_GAIN = float(PROFILE.get("ZOOM_GAIN", 1.0))
ZOOM_ENABLED = int(PROFILE.get("ZOOM_ENABLED", 0))

tracking_on = False
neutral_x = None
neutral_y = None
neutral_z = None
is_moving = False
pulses = 0
active_serial = None
last_space_time = 0.0
accumulated_pitch = 0.0
accumulated_yaw = 0.0
accumulated_zoom = 0.0
dragging = False

def safe_release_left():
    global dragging
    try:
        # release in center, not URL bar, with flick
        mouse.position = (960, 540)
        time.sleep(0.02)
        mouse.move(0, -100)
        time.sleep(0.02)
        mouse.release(Button.left)
    except Exception:
        pass
    dragging = False

def safe_press_left():
    global dragging
    try:
        # always press in middle of Street View
        mouse.position = (960, 540)
        time.sleep(0.05)
        mouse.press(Button.left)
    except Exception:
        pass
    dragging = True

def curate_ports():
    ports = list(serial.tools.list_ports.comports())
    curated = []
    for p in ports:
        if "bluetooth" in f"{p.description}".lower():
            continue
        curated.append({
            "device": p.device,
            "desc": p.description,
            "score": 10 if "arduino" in p.description.lower() or "ch340" in p.description.lower() else 0
        })
    curated.sort(key=lambda x: (-x["score"], x["device"]))
    return curated

def pick_port_manual():
    while True:
        cur = curate_ports()
        if not cur:
            print("No ports - press q for head only")
            inp = input("q=head only, r=rescan: ").strip().lower()
            if inp == 'q':
                return None
            continue
        for i, c in enumerate(cur):
            print(f" [{i}] {c['device']} {c['desc']}")
        sel = input(f"Pick 0-{len(cur)-1} [q=head only, r=rescan]: ").strip().lower()
        if sel == 'q':
            return None
        if sel == 'r':
            continue
        if sel.isdigit() and int(sel) < len(cur):
            return cur[int(sel)]["device"]

def background_roller():
    global is_moving, pulses, active_serial
    last_pulse_time = 0
    print(f"[ROLLER] v10 HAS_XDOTOOL={HAS_XDOTOOL}")
    while True:
        try:
            now = time.time()
            if is_moving and (now - last_pulse_time > 0.7):
                release_up()
                is_moving = False
            if active_serial and active_serial.is_open and active_serial.in_waiting > 0:
                try:
                    raw = active_serial.read(active_serial.in_waiting).decode('utf-8', errors='ignore')
                except Exception:
                    time.sleep(0.005)
                    continue
                if "1" in raw:
                    pulses += raw.count("1")
                    last_pulse_time = now
                    if not is_moving:
                        press_up()
                        is_moving = True
            else:
                time.sleep(0.005)
        except Exception as e:
            print(f"[ROLLER ERROR] {e}")
            try:
                release_up()
            except Exception:
                pass
            is_moving = False
            time.sleep(0.5)

print("=== Arduino Roller v10 FINAL ===")
selected_port = pick_port_manual()
if selected_port:
    try:
        active_serial = serial.Serial(selected_port, BAUD, timeout=0.1)
        time.sleep(2.0)
        active_serial.reset_input_buffer()
        print(f"Connected {selected_port}")
        threading.Thread(target=background_roller, daemon=True).start()
    except Exception as e:
        print(f"Could not open {selected_port}: {e}")
        active_serial = None
        threading.Thread(target=background_roller, daemon=True).start()
else:
    print("Head only mode (q) - press F11 for fullscreen, then SPACE to look")
    threading.Thread(target=background_roller, daemon=True).start()

def on_press(key):
    global tracking_on, neutral_x, neutral_y, neutral_z, accumulated_pitch, accumulated_yaw, accumulated_zoom, last_space_time, dragging
    try:
        if key == keyboard.Key.space:
            now = time.time()
            if now - last_space_time > 0.3:
                last_space_time = now
                tracking_on = not tracking_on
                if tracking_on:
                    neutral_x = None
                    neutral_y = None
                    neutral_z = None
                    accumulated_pitch = 0.0
                    accumulated_yaw = 0.0
                    accumulated_zoom = 0.0
                    print("Tracking ON - auto recentered")
                else:
                    if dragging:
                        safe_release_left()
                    print("Tracking OFF")
        elif hasattr(key, 'char') and key.char and key.char.lower() == 'c':
            neutral_x = None
            neutral_y = None
            neutral_z = None
            accumulated_pitch = 0.0
            accumulated_yaw = 0.0
            accumulated_zoom = 0.0
            print("Recenter")
        elif key == keyboard.Key.esc:
            print("ESC exit")
            release_up()
            if dragging:
                safe_release_left()
            os._exit(0)
    except Exception as e:
        print(f"Key handler error {e}")

listener = keyboard.Listener(on_press=on_press)
listener.daemon = True
listener.start()

cap = cv2.VideoCapture(0, cv2.CAP_V4L2)
cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('M', 'J', 'P', 'G'))
cap.set(3, 640)
cap.set(4, 480)
cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

missing_frames = 0
cached_x_off = 0.0
cached_y_off = 0.0
cached_z_off = 0.0

try:
    while True:
        ret, frame = cap.read()
        if not ret:
            time.sleep(0.005)
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
        found_current = False
        x_off = 0.0
        y_off = 0.0
        z_off = 0.0
        if contours:
            largest_c = max(contours, key=cv2.contourArea)
            if cv2.contourArea(largest_c) > 400:
                (x, y), radius = cv2.minEnclosingCircle(largest_c)
                if radius > 10:
                    x_off = float(x) / w - 0.5
                    y_off = float(y) / h - 0.5
                    z_off = radius / w - 0.15
                    cached_x_off = x_off
                    cached_y_off = y_off
                    cached_z_off = z_off
                    missing_frames = 0
                    found_current = True
        if not found_current:
            missing_frames += 1
            if missing_frames <= 60:
                x_off = cached_x_off
                y_off = cached_y_off
                z_off = cached_z_off
                tracked = True
            else:
                tracked = False
        else:
            tracked = True

        if tracked and tracking_on:
            if neutral_x is None:
                neutral_x = x_off
                neutral_y = y_off
                neutral_z = z_off
            if ZOOM_ENABLED and abs(z_off - neutral_z) > Z_DEAD:
                diff_z = (z_off - neutral_z) / Z_MAX
                accumulated_zoom += diff_z * ZOOM_GAIN
                scroll_steps = int(accumulated_zoom)
                if scroll_steps != 0:
                    try:
                        mouse.scroll(0, scroll_steps)
                    except Exception:
                        pass
                    accumulated_zoom -= scroll_steps
            dx_head = x_off - neutral_x
            move_x = 0
            if abs(dx_head) > X_DEAD:
                norm_x = min(abs(dx_head) - X_DEAD, X_MAX) / X_MAX
                speed = (norm_x ** 0.5) * X_PAN_GAIN
                step_x = int(-speed if dx_head > 0 else speed)
                if step_x == 0:
                    step_x = -10 if dx_head > 0 else 10
                move_x = step_x
                accumulated_yaw += move_x
            else:
                if abs(accumulated_yaw) > 0.5:
                    drift_step_x = -np.sign(accumulated_yaw) * min(abs(accumulated_yaw), YAW_DRIFT_SPEED)
                    move_x = int(drift_step_x)
                    accumulated_yaw += drift_step_x
                else:
                    accumulated_yaw = 0.0
            if move_x != 0:
                try:
                    mouse.move(move_x, 0)
                except Exception:
                    pass
            dy = y_off - neutral_y
            move_y = 0
            if dy > DOWN_DEAD:
                norm_y = min((dy - DOWN_DEAD) / 0.08, 1.0)
                step = -((norm_y ** 0.6) * Y_PAN_GAIN)
                step = max(step, -PITCH_DOWN_LIMIT)
                move_y = int(step)
                accumulated_pitch += move_y
            elif dy < -UP_DEAD:
                norm_y = min((abs(dy) - UP_DEAD) / 0.08, 1.0)
                step = (norm_y ** 0.6) * Y_PAN_GAIN
                step = min(step, PITCH_UP_LIMIT)
                move_y = int(step)
                accumulated_pitch += move_y
            else:
                if abs(accumulated_pitch) > 0.5:
                    drift_step = -np.sign(accumulated_pitch) * min(abs(accumulated_pitch), HORIZON_DRIFT_SPEED)
                    move_y = int(drift_step)
                    accumulated_pitch += drift_step
                else:
                    accumulated_pitch = 0.0
            if move_y != 0:
                try:
                    mouse.move(0, move_y)
                except Exception:
                    pass
            # keep out of URL bar
            try:
                mx, my = mouse.position
                if my < 150:
                    mouse.position = (mx, 250)
            except Exception:
                pass

        if tracking_on and tracked:
            if not dragging:
                safe_press_left()
        else:
            if dragging and not tracking_on:
                safe_release_left()
            elif dragging and not tracked and missing_frames > 60:
                safe_release_left()

        cv2.putText(frame, f"{'TRACK ON' if tracking_on else 'TRACK OFF'} Pulses:{pulses}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        cv2.putText(frame, "SPACE=ON/OFF C=center ESC=quit | F11=fullscreen", (10, h - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)
        cv2.imshow("Orange Hat v10 - ESC to quit", frame)
        if cv2.waitKey(1) & 0xFF == 27:
            break

except KeyboardInterrupt:
    pass
finally:
    try:
        if dragging:
            safe_release_left()
        release_up()
    except Exception:
        pass
    try:
        if active_serial and active_serial.is_open:
            active_serial.close()
    except Exception:
        pass
    cap.release()
    cv2.destroyAllWindows()
    print("Exited cleanly.")
    sys.exit(0)
