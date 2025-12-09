// tx_simulator.ino - Transmitter (Bike Side) - SS49E ANALOG VERSION
// Reads Hall sensor on Analog Pin A0 and transmits RPM.

#include <SPI.h>
#include "RF24.h"

// --- NRF24L01 PIN DEFINITIONS ---
RF24 radio(9, 10); // CE, CSN
const byte addresses[][6] = {"00001"}; // Unique address for the pipe

// --- DATA STRUCTURE (MUST MATCH RECEIVER - 1 PART) ---
struct Payload {
    float rpm;
};

// --- SENSOR PIN DEFINITIONS ---
// *** CHANGED TO ANALOG PIN A0 FOR SS49E ***
const int HALL_SENSOR_PIN = A0;   

// --- SS49E ANALOG THRESHOLDS ---
// Center reading (no magnet) is usually around 512 (2.5V).
// Adjust THRESHOLD based on your sensor and magnet strength.
// Example: If reading drops to 300 when magnet passes, set THRESHOLD to 400.
const int MAGNET_THRESHOLD = 400; 

// --- SPEED VARIABLES ---
unsigned long lastPulseTime = 0;
unsigned long pulseInterval = 0;
float currentRPM = 0.0;
unsigned long speedTimer = 0;

// --- STATE VARIABLES ---
bool magnetDetected = false; // Tracks if the magnet is currently near the sensor

// --- FUNCTION PROTOTYPES ---
void readSensor(); // Replaces the interrupt handler
void updateRPM();

void setup() {
  Serial.begin(9600); 
  Serial.println("--- Transmitter Setup (SS49E Analog) Start ---");
  
  // 1. Initialize Radio
  radio.begin();
  radio.openWritingPipe(addresses[0]);
  radio.setPALevel(RF24_PA_LOW); 
  radio.stopListening(); 

  // 2. Setup Sensor Pin (No PinMode needed for AnalogRead)
  // DETACH INTERRUPT since we are using analog reading
  detachInterrupt(digitalPinToInterrupt(2)); 

  Serial.println("Sensor Ready. Start spinning the wheel to test.");
}

void loop() {
  // 1. Read Sensor and Check for Pulse
  readSensor();

  // 2. Sensor Reading and Calculation
  if (millis() - speedTimer >= 50) {
    updateRPM();
    speedTimer = millis();
  }
  
  // 3. Assemble Data Payload (1-part structure)
  Payload data;
  data.rpm = currentRPM;

  // 4. Transmit Data
  radio.write(&data, sizeof(data));

  delay(50); // Transmit every 50ms
}

// --- NEW: ANALOG SENSOR READER ---
void readSensor() {
  int analogReading = analogRead(HALL_SENSOR_PIN);
  
  // Logic to detect the *falling edge* of the pulse (crossing the threshold)
  if (analogReading < MAGNET_THRESHOLD) {
    // Magnet is near the sensor
    if (magnetDetected == false) {
      // This is the moment the magnet crosses the threshold (falling edge)
      unsigned long currentTime = micros();
      
      // Simple debounce
      if (currentTime - lastPulseTime > 5000) { 
        pulseInterval = currentTime - lastPulseTime;
        lastPulseTime = currentTime;
        Serial.println("ANALOG PULSE DETECTED!"); 
      }
      magnetDetected = true;
    }
  } else {
    // Magnet is away from the sensor
    magnetDetected = false;
  }

  // Debugging the raw analog value (optional, can be removed once tuned)
  Serial.print("Analog Reading (A0): ");
  Serial.print(analogReading);
  Serial.print(" | Current RPM: ");
  Serial.println(currentRPM);
}


// --- RPM CALCULATION (UNCHANGED) ---
void updateRPM() {
  if (pulseInterval > 0) {
    currentRPM = (60000000.0 / pulseInterval);

    if (micros() - lastPulseTime > 500000) {
      currentRPM = 0.0;
      pulseInterval = 0; 
    }
  } else {
    currentRPM = 0.0;
  }
}
