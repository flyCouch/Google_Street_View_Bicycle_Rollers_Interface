// tx_simulator.ino - Transmitter (Bike Side)
// Reads ONLY the Hall sensor (Speed) and transmits a single RPM value wirelessly.

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
const int HALL_SENSOR_PIN = 2;   // Digital Pin 2 (interrupt) - Bike Speed

// --- SPEED VARIABLES ---
volatile unsigned long lastPulseTime = 0;
volatile unsigned long pulseInterval = 0;
float currentRPM = 0.0;
unsigned long speedTimer = 0;

// --- FUNCTION PROTOTYPES ---
void handleMagnetPulse();
void updateRPM();

void setup() {
  Serial.begin(9600);
  
  // 1. Initialize Radio
  radio.begin();
  radio.openWritingPipe(addresses[0]);
  radio.setPALevel(RF24_PA_LOW); 
  radio.stopListening(); 

  // 2. Setup Sensor Pin
  pinMode(HALL_SENSOR_PIN, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(HALL_SENSOR_PIN), handleMagnetPulse, FALLING);
}

void loop() {
  // 1. Sensor Reading and Calculation
  if (millis() - speedTimer >= 50) {
    updateRPM();
    speedTimer = millis();
  }

  // 2. Assemble Data Payload (1-part structure)
  Payload data;
  data.rpm = currentRPM;

  // 3. Transmit Data
  radio.write(&data, sizeof(data));

  delay(50); // Transmit every 50ms
}

// --- INTERRUPT HANDLER (SPEED) ---
void handleMagnetPulse() {
  unsigned long currentTime = micros();
  // Simple debounce
  if (currentTime - lastPulseTime > 5000) { 
    pulseInterval = currentTime - lastPulseTime;
    lastPulseTime = currentTime;
  }
}

// --- RPM CALCULATION ---
void updateRPM() {
  if (pulseInterval > 0) {
    // RPM = (60 seconds * 1,000,000 microseconds) / pulseInterval
    currentRPM = (60000000.0 / pulseInterval);

    // If no pulse received for half a second, assume stopped
    if (micros() - lastPulseTime > 500000) {
      currentRPM = 0.0;
    }
  } else {
    currentRPM = 0.0;
  }
}
