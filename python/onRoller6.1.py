import serial
import threading
import serial.tools.list_ports
from pynput.keyboard import Key, Controller as KeyboardController, Listener as KeyboardListener

# --- CONFIG ---
SERIAL_PORT = 'COM4'
BAUD_RATE = 9600
ROLLER_DIA_MM = 81.0
# Math: One revolution = 0.254 meters
CIRCUM_M = (ROLLER_DIA_MM * 3.14159) / 1000.0 

# --- STATE ---
keyboard = KeyboardController()
meters_to_trigger = 10.0  # Default: Change image every 10m
meter_accumulator = 0.0
is_motion_enabled = True
is_running = True

def select_port():
    ports = list(serial.tools.list_ports.comports())
    if not ports:
        print("No serial ports found! Defaulting to COM4")
        return 'COM4'
    
    print("Available Serial Ports:")
    for i, port in enumerate(ports):
        # Print device name, description, and manufacturer/hardware ID for easy identification
        print(f"  [{i}] {port.device}")
        print(f"      Description: {port.description}")
        print(f"      Hardware ID: {port.hwid}")
        print("-" * 40)
    
    choice = input(f"Select port index (0-{len(ports)-1}) or press Enter for default ({ports[0].device}): ").strip()
    
    if choice == "" or not choice.isdigit():
        selected = ports[0].device
        print(f"-> Auto-selected default: {selected}\n")
        return selected
    
    idx = int(choice)
    if 0 <= idx < len(ports):
        selected = ports[idx].device
        print(f"-> Selected: {selected} ({ports[idx].description})\n")
        return selected
    else:
        print(f"Invalid choice! Defaulting to {ports[0].device}\n")
        return ports[0].device

SERIAL_PORT = select_port()

def on_press(key):
    global is_motion_enabled, meter_accumulator
    try:
        if key.char == 'm':
            is_motion_enabled = not is_motion_enabled
            meter_accumulator = 0.0 # Reset bucket on pause
            print(f"\n[TOGGLE] Motion: {'ENABLED' if is_motion_enabled else 'DISABLED'}")
            print(f"Target: {meters_to_trigger}m | New: ", end="", flush=True)
    except: pass

def serial_worker():
    """Reliable v31 Style Polling Loop for Analog Pulses"""
    global meter_accumulator, is_running
    try:
        # The aggressive 1ms timeout from your reliable v31 script
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.001)
        ser.flushInput()
        
        while is_running:
            line = ser.readline().decode('utf-8').strip()
            
            # If the analog sensor detected a pass
            if line == "1" and is_motion_enabled:
                meter_accumulator += CIRCUM_M
                
                # Speed Logic: If we reach the distance goal, tap Arrow Up
                if meter_accumulator >= meters_to_trigger:
                    keyboard.tap(Key.up)
                    meter_accumulator = 0.0
                    print(f".", end="", flush=True) # visual heartbeat
            
    except Exception as e:
        print(f"Serial Error: {e}")

def main():
    global meters_to_trigger
    # 1. Start Keyboard Listener (v31 style)
    KeyboardListener(on_press=on_press).start()
    
    # 2. Start Serial Thread
    threading.Thread(target=serial_worker, daemon=True).start()

    print("--- Analog Speed Bridge (81mm Edition) ---")
    print("Commands: 'm' to pause | Type a number to change jump distance")
    
    while True:
        try:
            val = input(f"Target: {meters_to_trigger}m | New: ")
            meters_to_trigger = float(val)
            print(f">>> Updated! Tapping every {meters_to_trigger} meters.")
        except: break

if __name__ == "__main__":
    main()
