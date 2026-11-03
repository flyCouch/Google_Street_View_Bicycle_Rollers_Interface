# onRoller63.py - EXE-ready - 81mm rollers - NO AUTO-PICK
#pip install pyserial pynput pyinstaller
# Build Windows EXE: pyinstaller --onedir --console --collect-all serial --hidden-import=pynput.keyboard._win32 onRoller64.py

#Linux version, 
#pip install pyserial pynput pyinstaller
#pyinstaller --onedir --console --collect-all serial onRoller64.py
import sys
import time
import threading
import serial
import serial.tools.list_ports
from pynput.keyboard import Key, Controller as KeyboardController, Listener as KeyboardListener

# --- CONFIG ---
BAUD_RATE = 9600
ROLLER_DIA_MM = 81.0
CIRCUM_M = (ROLLER_DIA_MM * 3.1415926535) / 1000.0

# --- STATE ---
keyboard = KeyboardController()
meters_to_trigger = 10.0
meter_accumulator = 0.0
acc_lock = threading.Lock()
is_motion_enabled = True
is_running = True
ser = None

def select_port():
    all_ports = list(serial.tools.list_ports.comports())
    ports = [p for p in all_ports if p.description != 'n/a' and p.hwid != 'n/a']
    
    if not ports:
        print("No active USB/Serial devices found!")
        print("Make sure UNO is plugged in and not open in Arduino IDE.")
        input("Press Enter to exit...")
        sys.exit(1)

    print("\n--- SELECT ROLLER PORT (no auto-pick) ---")
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
    global is_motion_enabled, meter_accumulator
    try:
        if hasattr(key, 'char') and key.char == 'm':
            with acc_lock:
                is_motion_enabled = not is_motion_enabled
                meter_accumulator = 0.0
            print(f"\n[TOGGLE] Motion: {'ENABLED' if is_motion_enabled else 'DISABLED'}")
            print(f"Target: {meters_to_trigger}m | New: ", end="", flush=True)
        if key == Key.esc:
            print("\n[ESC] Exiting...")
            global is_running
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
                        print(f".", end="", flush=True)
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
    global meters_to_trigger, is_running
    serial_port = select_port()
    listener = KeyboardListener(on_press=on_press)
    listener.start()
    t = threading.Thread(target=serial_worker, args=(serial_port,), daemon=True)
    t.start()

    print("\n--- Analog Speed Bridge 63 (81mm Edition) ---")
    print("m = pause/resume | ESC = quit | Type number + Enter to change distance")
    print(f"1 rev = {CIRCUM_M:.4f}m | Trigger = {meters_to_trigger}m")
    print("-" * 60)

    while is_running:
        try:
            val = input(f"Target: {meters_to_trigger}m | New: ")
            if not is_running:
                break
            if val.strip() == "":
                continue
            meters_to_trigger = float(val)
            print(f">>> Updated! Every {meters_to_trigger} meters = UP arrow")
        except ValueError:
            print("Invalid number, try again.")
        except (EOFError, KeyboardInterrupt):
            break

    is_running = False
    print("\nShutting down...")
    time.sleep(0.3)
    listener.stop()
    if ser and ser.is_open:
        try:
            ser.close()
        except:
            pass
    print("Done.")
    sys.exit(0)

if __name__ == "__main__":
    main()
