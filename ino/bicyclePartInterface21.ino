// tx_simulator.ino - Transmitter (Bike Side) - SS49E ANALOG VERSION
// Reads Hall sensor on Analog Pin A0 and transmits the simple boolean 'spin' state.

#include <SPI.h>
#include "RF24.h"

// --- NRF24L01 PIN DEFINITIONS ---
RF24 radio(10, 9); // CE, CSN
const byte addresses[][6] = {"00100"}; 

// --- DATA STRUCTURE (MUST MATCH RECEIVER) ---
struct Payload {
    bool spin;
};

// --- SENSOR PIN DEFINITIONS ---
const int HALL_SENSOR_PIN = A0;   
const int MAGNET_THRESHOLD = 650; // Adjust this based on your sensor and magnet strength

// --- STATE VARIABLES ---
unsigned long lastPulseTime = 0;
bool magnetDetected = false; 
bool isSpinning = false; // Tracks the current transmission state
const unsigned long TIMEOUT_STOP_MS = 1000; // 1 second without a pulse = stopped

// --- FUNCTION PROTOTYPES ---
void readSensor();

void setup() {
  Serial.begin(9600); 
  Serial.println("--- Transmitter Setup (SS49E Analog) Start ---");

  // 1. Initialize Radio
  radio.begin();
  radio.openWritingPipe(addresses[0]);
  radio.setPALevel(RF24_PA_LOW); 
  radio.stopListening(); 

  Serial.println("Sensor Ready. Start spinning the wheel to test.");
}

void loop() {
  // 1. Read Sensor for Pulse Detection (updates lastPulseTime)
  readSensor();
  
  unsigned long currentTime = millis();
  
  // 2. CHECK FOR STOPPED STATE (TIMEOUT)
  if (currentTime - (lastPulseTime / 1000) > TIMEOUT_STOP_MS) {
    if (isSpinning == true) {
      // It was spinning, but a pulse hasn't been seen in over TIMEOUT_STOP_MS.
      // CHANGE STATE TO FALSE AND TRANSMIT
      isSpinning = false;
      Payload data;
      data.spin = isSpinning; // false
      radio.write(&data, sizeof(data));
      Serial.println("STATE CHANGE: Stopped spinning (false)");
    }
  }
}

// --- ANALOG SENSOR READER ---
void readSensor() {
  int analogReading = analogRead(HALL_SENSOR_PIN);
  
  // Logic to detect the *rising edge* of the pulse (crossing the threshold)
  if (analogReading > MAGNET_THRESHOLD) {
    // Magnet is near the sensor
    if (magnetDetected == false) {
      // This is the moment the magnet crosses the threshold (rising edge)
      unsigned long currentTime = micros();
      
      // Simple debounce (1ms)
      if (currentTime - lastPulseTime > 1000) { 
        lastPulseTime = currentTime;
        Serial.println("ANALOG PULSE DETECTED!"); 
        
        // CHECK FOR STARTED STATE
        if (isSpinning == false) {
            // It was stopped, now a new pulse is detected.
            // CHANGE STATE TO TRUE AND TRANSMIT
            isSpinning = true;
            Payload data;
            data.spin = isSpinning; // true
            radio.write(&data, sizeof(data));
            Serial.println("STATE CHANGE: Started spinning (true)");
        }
      }
      magnetDetected = true;
    }
  } else {
    // Magnet is away from the sensor
    magnetDetected = false;
  }

  // Debugging the current state
  Serial.print("Analog Reading (A0): ");
  Serial.print(analogReading);
  Serial.print(" | Is Spinning State: ");
  Serial.println(isSpinning);
}
