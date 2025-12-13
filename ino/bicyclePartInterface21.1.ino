// tx_simulator.ino - Transmitter (Bike Side) - SS49E ANALOG VERSION

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
const int MAGNET_THRESHOLD = 650; 

// --- STATE & TIMING VARIABLES ---
unsigned long lastPulseTime_us = 0;  // Last pulse time in microseconds (for debounce)
unsigned long lastPulseTime_ms = 0;  // Last pulse time in milliseconds (for timeout check)
unsigned long lastTransmitTime = 0;  // Last time we sent ANY radio message
bool magnetDetected = false; 
bool isSpinning = false; // Tracks the current transmission state

// TIMING CONFIGURATION (Crucial for responsiveness)
const unsigned long TIMEOUT_STOP_MS = 500;       // 0.5 seconds without a pulse = stopped
const unsigned long TRANSMIT_INTERVAL_MS = 50;   // Force re-transmit state every 50ms

void readSensor();
void transmitState(bool state);

void setup() {
  Serial.begin(9600); 
  Serial.println("--- Transmitter Setup Start ---");
  radio.begin();
  radio.openWritingPipe(addresses[0]);
  radio.setPALevel(RF24_PA_LOW); 
  radio.stopListening(); 
  Serial.println("Sensor Ready.");
}

void loop() {
  // 1. Read Sensor for Pulse Detection (updates lastPulseTime_us and lastPulseTime_ms)
  readSensor();
  
  unsigned long currentTime = millis();
  
  // 2. CHECK FOR STOPPED STATE (TIMEOUT)
  if (isSpinning == true && (currentTime - lastPulseTime_ms) > TIMEOUT_STOP_MS) {
    // Wheel was spinning but timed out. Change state to OFF.
    isSpinning = false;
    transmitState(false);
    Serial.println("STATE CHANGE: Stopped spinning (false)");
  }

  // 3. PERIODIC RE-TRANSMISSION (Keeps the 'Up' key held down continuously)
  if (isSpinning == true && (currentTime - lastTransmitTime) >= TRANSMIT_INTERVAL_MS) {
    // Wheel is still spinning, but we haven't sent a packet in 50ms. Send 'True' again.
    transmitState(true);
    // Note: Serial debugging for this will spam the console!
  }
}

// --- ANALOG SENSOR READER ---
void readSensor() {
  int analogReading = analogRead(HALL_SENSOR_PIN);
  
  if (analogReading > MAGNET_THRESHOLD) {
    if (magnetDetected == false) {
      unsigned long currentTime_us = micros();
      
      // Simple debounce (1ms) - prevents chatter
      if (currentTime_us - lastPulseTime_us > 1000) { 
        lastPulseTime_us = currentTime_us;
        lastPulseTime_ms = millis(); // Update the millisecond time for the timeout check
        
        // CHECK FOR STARTED STATE (only send True on FIRST pulse)
        if (isSpinning == false) {
            isSpinning = true;
            transmitState(true);
            Serial.println("STATE CHANGE: Started spinning (true)");
        }
      }
      magnetDetected = true;
    }
  } else {
    magnetDetected = false;
  }
}

// --- RADIO TRANSMITTER FUNCTION ---
void transmitState(bool state) {
    Payload data;
    data.spin = state;
    radio.write(&data, sizeof(data));
    lastTransmitTime = millis();
}