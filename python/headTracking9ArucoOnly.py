# headTracker8hybrid_aruco_only.py - NO mediapipe, fixes Illegal Instruction on old CPUs
import time, sys, os, json, threading
import serial, serial.tools.list_ports
from pynput.mouse import Controller as MouseCtrl, Button
from pynput.keyboard import Controller as KeyCtrl, Key
from pynput import keyboard
import cv2

mouse = MouseCtrl(); kbd = KeyCtrl()

DEFAULT_PROFILE = {
  "YAW_GAIN": 45, "PITCH_GAIN": 35, "X_DEAD": 0.04, "Z_DEAD": 0.03,
  "X_MAX": 0.25, "Z_MAX": 0.20, "X_PAN_GAIN": 4.0,
  "RPM_FAST": 45.0, "RPM_SLOW": 12.0, "BAUD": 9600,
  "ARUCO_DICT": "DICT_4X4_50", "ARUCO_ID": 0
}
PROFILE_FILE = sys.argv[1] if len(sys.argv)>1 and sys.argv[1].endswith(".json") else "streetview.json"
if not os.path.exists(PROFILE_FILE):
    with open(PROFILE_FILE,"w") as f: json.dump(DEFAULT_PROFILE,f,indent=2)
    PROFILE=DEFAULT_PROFILE
else:
    with open(PROFILE_FILE) as f: PROFILE=json.load(f)
    for k,v in DEFAULT_PROFILE.items(): PROFILE.setdefault(k,v)

YAW_GAIN=PROFILE["YAW_GAIN"]; PITCH_GAIN=PROFILE["PITCH_GAIN"]
X_DEAD=PROFILE["X_DEAD"]; Z_DEAD=PROFILE["Z_DEAD"]; X_MAX=PROFILE["X_MAX"]; Z_MAX=PROFILE["Z_MAX"]
X_PAN_GAIN=PROFILE["X_PAN_GAIN"]; RPM_FAST_THRESHOLD=PROFILE["RPM_FAST"]; RPM_SLOW_THRESHOLD=PROFILE["RPM_SLOW"]
BAUD=PROFILE["BAUD"]; ARUCO_ID=PROFILE["ARUCO_ID"]

DICT_MAP={"DICT_4X4_50":cv2.aruco.DICT_4X4_50,"DICT_5X5_50":cv2.aruco.DICT_5X5_50,"DICT_6X6_50":cv2.aruco.DICT_6X6_50}
ARUCO_DICT_ID=DICT_MAP.get(PROFILE["ARUCO_DICT"],cv2.aruco.DICT_4X4_50)

tracking_on=False; neutral_x=neutral_z=None; last_yaw=last_pitch=0; last_zoom=0
is_moving=False; pulses=0; pulse_times=[]

def curate_ports():
    ports=list(serial.tools.list_ports.comports()); curated=[]
    for p in ports:
        if "bluetooth" in f"{p.description}".lower(): continue
        curated.append({"device":p.device,"desc":p.description,"score":10 if "arduino" in p.description.lower() or "ch340" in p.description.lower() else 0,"arduino":True})
    curated.sort(key=lambda x: (-x["score"], x["device"])); return curated

def pick_port_manual():
    while True:
        cur=curate_ports()
        if not cur: print("No ports"); input(); continue
        for i,c in enumerate(cur): print(f" [{i}] {c['device']} {c['desc']}")
        sel=input(f"Pick 0-{len(cur)-1} [q=head only, r=rescan]: ").strip().lower()
        if sel=='q': return None
        if sel=='r': continue
        if sel.isdigit(): return cur[int(sel)]["device"]

def calculate_rpm():
    global pulse_times; now=time.time()
    pulse_times=[t for t in pulse_times if now-t<2.0]
    if len(pulse_times)<2: return 0.0
    dur=pulse_times[-1]-pulse_times[0]
    return 0.0 if dur<0.2 else (len(pulse_times)/dur)*60.0

def roller_thread():
    global is_moving,pulses,pulse_times
    while True:
        port=pick_port_manual()
        if not port: return
        try:
            ser=serial.Serial(port,BAUD,timeout=0.1); ser.flushInput()
            print(f"Connected {port}")
            while True:
                line=ser.readline().decode(errors='ignore').strip()
                if not line: continue
                rpm=0.0
                if line=="1": pulse_times.append(time.time()); pulses+=1; rpm=calculate_rpm()
                else:
                    try: rpm=float(line)
                    except: continue
                if rpm>RPM_FAST_THRESHOLD:
                    if not is_moving: kbd.press(Key.up); is_moving=True
                elif rpm>RPM_SLOW_THRESHOLD:
                    if is_moving: kbd.release(Key.up); is_moving=False
                    kbd.press(Key.up); time.sleep(0.05); kbd.release(Key.up); time.sleep(0.15)
                else:
                    if is_moving: kbd.release(Key.up); is_moving=False
        except: time.sleep(1)

threading.Thread(target=roller_thread,daemon=True).start()

# ArUco setup
aruco_dict_obj=cv2.aruco.getPredefinedDictionary(ARUCO_DICT_ID)
aruco_params=cv2.aruco.DetectorParameters()
aruco_det=cv2.aruco.ArucoDetector(aruco_dict_obj, aruco_params)

def on_press(key):
    global tracking_on,neutral_x,neutral_z
    try:
        if key==keyboard.Key.space:
            tracking_on=not tracking_on
            if tracking_on: mouse.press(Button.left)
            else: mouse.release(Button.left)
            print(f"{'ON' if tracking_on else 'OFF'}")
        elif hasattr(key,'char') and key.char and key.char.lower()=='c':
            neutral_x=neutral_z=None; print("Recenter")
        elif key==keyboard.Key.esc: sys.exit(0)
    except: pass

keyboard.Listener(on_press=on_press).start()

cap=cv2.VideoCapture(0)
cap.set(3,640); cap.set(4,480)
print(f"ArUco only mode - looking for ID {ARUCO_ID}. SPACE toggle, C recenter, ESC quit")

while True:
    ret,frame=cap.read()
    if not ret: continue
    frame=cv2.flip(frame,1); h,w=frame.shape[:2]
    tracked=False; x_off=z_off=yaw=pitch=0.0

    corners,ids,_=aruco_det.detectMarkers(frame)
    if ids is not None:
        for idx,mid in enumerate(ids.flatten()):
            if int(mid)==int(ARUCO_ID):
                c=corners[idx][0]
                cx=float(c[:,0].mean())/w
                x_off=cx-0.5
                marker_w=float(abs(c[1,0]-c[0,0]))/w
                z_off=0.15-(marker_w*4)
                top_w=abs(c[1,0]-c[0,0]); bottom_w=abs(c[2,0]-c[3,0])
                yaw=(bottom_w-top_w)/(top_w+1e-6)*2
                tracked=True
                cv2.aruco.drawDetectedMarkers(frame,corners,[ids[idx]])
                break

    if tracked and tracking_on:
        if neutral_x is None: neutral_x=x_off; neutral_z=z_off; last_yaw=yaw
        dyaw=yaw-last_yaw
        if abs(dyaw)>0.015: mouse.move(-dyaw*YAW_GAIN,0)
        last_yaw=yaw
        if abs(z_off-neutral_z)>Z_DEAD: 
            kbd.press('+' if z_off>neutral_z else '-'); kbd.release('+' if z_off>neutral_z else '-')
        if abs(x_off-neutral_x)>X_DEAD:
            norm_x=min(abs(x_off-neutral_x)-X_DEAD,X_MAX)/X_MAX
            speed=(norm_x**1.8)*X_PAN_GAIN
            mouse.move(speed if (x_off-neutral_x)>0 else -speed,0)

    cv2.imshow(f"ArUco Preview ID {ARUCO_ID} - SPACE ON/OFF C center Q quit", frame)
    if cv2.waitKey(1)&0xFF==ord('q'): break
