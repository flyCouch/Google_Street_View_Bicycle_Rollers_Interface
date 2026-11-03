# headTracking2.py - Roller + OpenTrack -> Google Street View
# pip install pynput pyserial
# OpenTrack: Output = UDP 127.0.0.1:5550

import socket
import struct
import time
import sys
import threading
import serial
import serial.tools.list_ports
from pynput import keyboard
from pynput.mouse import Controller as MouseCtrl, Button
from pynput.keyboard import Controller as KeyCtrl, Key

mouse = MouseCtrl()
kbd = KeyCtrl()

# --- ROLLER HARDWARE (your 81mm drum) ---
ROLLER_DIAM_MM = 81
CIRCUM_MM = 3.1416 * ROLLER_DIAM_MM  # 254.5mm per "1"
BAUD = 9600
RPM_FAST_THRESHOLD = 45.0   # >45 rpm = hold UP
RPM_SLOW_THRESHOLD = 12.0   # >12 rpm = tap UP

# --- HEAD TRACKING TUNING ---
Z_DEAD = 2.0
X_DEAD = 1.8
Z_MAX = 12.0
X_MAX = 10.0
YAW_GAIN = 38
PITCH_GAIN = 38
X_PAN_GAIN = 3.0

# --- STATE ---
tracking_on = False
neutral_x = None
neutral_z = None
last_yaw = 0
last_pitch = 0
last_zoom = 0

is_moving = False
pulses = 0
pulse_times = []  # for RPM calc

# ---------- PORT CURATION (no auto-find) ----------
def curate_ports():
    ports = list(serial.tools.list_ports.comports())
    curated = []
    for p in ports:
        desc = f"{p.description} {p.manufacturer or ''}".lower()
        # filter Bluetooth junk that floods Windows
        if "bluetooth" in desc or "bthenum" in p.hwid.lower():
            continue

        score = 0
        is_arduino = False
        if "arduino" in desc: score += 10; is_arduino = True
        if "ch340" in desc or "ch341" in desc: score += 9; is_arduino = True
        if "cp210" in desc: score += 8; is_arduino = True
        if "usb serial" in desc: score += 5
        if p.vid == 0x2341 or p.vid == 0x1A86:  # Arduino / CH340
            score += 10; is_arduino = True

        curated.append({
            "device": p.device,
            "desc": p.description,
            "mfg": p.manufacturer or "",
            "hwid": p.hwid,
            "score": score,
            "arduino": is_arduino
        })

    curated.sort(key=lambda x: (-x["score"], x["device"]))
    return curated

def pick_port_manual():
    while True:
        curated = curate_ports()
        print("\n--- Curated Ports ---")
        if not curated:
            print("No serial ports. Plug in Uno, press Enter to rescan.")
            input()
            continue

        arduinos = [c for c in curated if c["arduino"]]
        others = [c for c in curated if not c["arduino"]]
        all_ports = arduinos + others

        idx = 0
        if arduinos:
            print("\n[ Likely Arduinos / Roller ]")
            for c in arduinos:
                print(f" [{idx}] {c['device']:6} - {c['desc']} ({c['mfg']})")
                idx += 1
        if others:
            print("\n[ Other Serial ]")
            for c in others:
                print(f" [{idx}] {c['device']:6} - {c['desc']}")
                idx += 1

        sel = input(f"\nPick 0-{len(all_ports)-1} or type COMx [q=head only, r=rescan]: ").strip()
        low = sel.lower()
        if low == 'q':
            return None
        if low == 'r':
            continue
        if sel.isdigit() and 0 <= int(sel) < len(all_ports):
            return all_ports[int(sel)]["device"]
        if "com" in low or "/dev/" in low:
            return sel
        print("Invalid")

def calculate_rpm():
    now = time.time()
    global pulse_times
    # keep last 2 sec
    pulse_times = [t for t in pulse_times if now - t < 2.0]
    if len(pulse_times) < 2:
        return 0.0
    duration = pulse_times[-1] - pulse_times[0]
    if duration < 0.2:
        return 0.0
    rps = len(pulse_times) / duration
    return rps * 60.0

def roller_thread():
    global is_moving, pulses, pulse_times
    while True:  # survive transient unplug
        port = pick_port_manual()
        if not port:
            print("Running head tracking only - no roller")
            return

        try:
            ser = serial.Serial(port, BAUD, timeout=0.1)
            ser.flushInput()
            print(f"\nConnected to {port} - waiting for '1' pulses. Unplug to re-pick.\n")

            while True:
                try:
                    line = ser.readline().decode(errors='ignore').strip()
                    if not line:
                        continue

                    rpm = 0.0
                    if line == "1":
                        pulse_times.append(time.time())
                        pulses += 1
                        rpm = calculate_rpm()
                    else:
                        try:
                            rpm = float(line)
                        except:
                            continue

                    # fast = hold UP, slow = tap UP
                    if rpm > RPM_FAST_THRESHOLD:
                        if not is_moving:
                            kbd.press(Key.up)
                            is_moving = True
                    elif rpm > RPM_SLOW_THRESHOLD:
                        if is_moving:
                            kbd.release(Key.up)
                            is_moving = False
                        kbd.press(Key.up)
                        time.sleep(0.05)
                        kbd.release(Key.up)
                        time.sleep(0.15)
                    else:
                        if is_moving:
                            kbd.release(Key.up)
                            is_moving = False

                except serial.SerialException:
                    print(f"\n{port} disconnected.")
                    if is_moving:
                        kbd.release(Key.up)
                        is_moving = False
                    break

        except Exception as e:
            print(f"Could not open {port}: {e}")
            time.sleep(1)
            continue

# start roller in background
threading.Thread(target=roller_thread, daemon=True).start()

# ---------- HEAD TRACKING ----------
def on_press(key):
    global tracking_on, neutral_x, neutral_z
    try:
        if key == keyboard.Key.space:
            tracking_on = not tracking_on
            if tracking_on:
                mouse.press(Button.left)
            else:
                mouse.release(Button.left)
            print(f"{'HEAD ON' if tracking_on else 'HEAD OFF'} - revs: {pulses}")
        elif hasattr(key, 'char') and key.char and key.char.lower() == 'c':
            neutral_x = neutral_z = None
            print("Recalibrate center")
        elif key == keyboard.Key.esc:
            print("Quit")
            if tracking_on:
                mouse.release(Button.left)
            if is_moving:
                kbd.release(Key.up)
            sys.exit(0)
    except:
        pass

keyboard.Listener(on_press=on_press).start()

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("127.0.0.1", 5550))
sock.setblocking(False)

print("OpenTrack UDP 5550 active.")
print("Keys: C=center, SPACE=toggle head drag, ESC=quit")
print("Pedal to make cyclist work - head tracking toggled separately.\n")

while True:
    try:
        data, _ = sock.recvfrom(1024)
        if len(data) < 24:
            continue
        if len(data) >= 48:
            x, y, z, yaw, pitch, roll = struct.unpack('6d', data[:48])
        else:
            x, y, z, yaw, pitch, roll = struct.unpack('6f', data[:24])

        if neutral_x is None:
            neutral_x, neutral_z = x, z
            last_yaw, last_pitch = yaw, pitch
            print(f"Neutral set X:{x:.1f} Z:{z:.1f}")
            continue

        if not tracking_on:
            last_yaw, last_pitch = yaw, pitch
            continue

        dyaw = yaw - last_yaw
        dpitch = pitch - last_pitch
        if abs(dyaw) > 0.12:
            mouse.move(-dyaw * YAW_GAIN, 0)
        if abs(dpitch) > 0.12:
            mouse.move(0, -dpitch * PITCH_GAIN)
        last_yaw, last_pitch = yaw, pitch

        now = time.time()
        z_off = neutral_z - z
        if abs(z_off) > Z_DEAD:
            norm = min(abs(z_off) - Z_DEAD, Z_MAX - Z_DEAD) / (Z_MAX - Z_DEAD)
            interval = 0.35 - norm * 0.31
            if now - last_zoom > interval:
                kbd.press('+' if z_off > 0 else '-')
                kbd.release('+' if z_off > 0 else '-')
                last_zoom = now

        x_off = x - neutral_x
        if abs(x_off) > X_DEAD:
            norm_x = min(abs(x_off) - X_DEAD, X_MAX - X_DEAD) / (X_MAX - X_DEAD)
            speed = (norm_x ** 1.8) * X_PAN_GAIN
            mouse.move(speed if x_off > 0 else -speed, 0)

    except BlockingIOError:
        pass
    except:
        pass

    time.sleep(0.002)
