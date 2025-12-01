// tx_simulator.ino - Transmitter (Bike Side)
// Reads sensor data and transmits wirelessly to the Receiver Arduino.

#include <SPI.h>
#include "RF24.h"

// --- NRF24L01 PIN DEFINITIONS ---
// Use standard Arduino pins for CE and CSN
RF24 radio(9, 10); // CE, CSN
const byte addresses[][6] = {"00001"}; // Unique address for the pipe

// --- DATA STRUCTURE (MUST MATCH RECEIVER) ---
struct Payload {
    float rpm;
    int steerX;
    int steerY;
    int zoomChange;
};

// --- SENSOR PIN DEFINITIONS ---
const int HALL_SENSOR_PIN = 2; // Digital Pin 2 (interrupt)
const int JOYSTICK_X_PIN = A0;  
const int JOYSTICK_Y_PIN = A1;  
const int ROTARY_DT_PIN = 7;    
const int ROTARY_CLK_PIN = 8;   

// --- SPEED VARIABLES ---
volatile unsigned long lastPulseTime = 0;
volatile unsigned long pulseInterval = 0;
float currentRPM = 0.0;
unsigned long speedTimer = 0;

// --- ROTARY ENCODER VARIABLES (ZOOM DIAL) ---
int lastZoomState;
volatile int zoomChange = 0; 

// --- FUNCTION PROTOTYPES ---
void handleMagnetPulse();
void updateRPM();
void updateZoom();

void setup() {
  Serial.begin(9600); // For debugging purposes only
  
  // 1. Initialize Radio
  radio.begin();
  radio.openWritingPipe(addresses[0]);
  radio.setPALevel(RF24_PA_LOW); // Low power for short distance, save battery
  radio.stopListening(); // Set as transmitter

  // 2. Setup Sensor Pins (same as before)
  pinMode(HALL_SENSOR_PIN, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(HALL_SENSOR_PIN), handleMagnetPulse, FALLING);
  pinMode(ROTARY_CLK_PIN, INPUT_PULLUP);
  pinMode(ROTARY_DT_PIN, INPUT_PULLUP);
  lastZoomState = digitalRead(ROTARY_CLK_PIN);
}

void loop() {
  // 1. Sensor Reading and Calculation
  if (millis() - speedTimer >= 50) {
    updateRPM();
    speedTimer = millis();
  }

  int joystickX = analogRead(JOYSTICK_X_PIN);
  int joystickY = analogRead(JOYSTICK_Y_PIN);
  
  int steerXValue = map(joystickX, 0, 1023, -100, 100);
  int steerYValue = map(joystickY, 0, 1023, 100, -100); 

  updateZoom();

  // 2. Assemble Data Payload
  Payload data;
  data.rpm = currentRPM;
  data.steerX = steerXValue;
  data.steerY = steerYValue;
  data.zoomChange = zoomChange;

  // 3. Transmit Data
  radio.write(&data, sizeof(data));

  // Reset zoom change after sending
  zoomChange = 0;

  delay(50); // Transmit every 50ms
}

// --- INTERRUPT HANDLER (SPEED) ---
void handleMagnetPulse() {
  unsigned long currentTime = micros();
  pulseInterval = currentTime - lastPulseTime;
  lastPulseTime = currentTime;
}

// --- RPM CALCULATION (Same as before) ---
void updateRPM() {
  if (pulseInterval > 0) {
    currentRPM = (60000000.0 / pulseInterval);

    if (micros() - lastPulseTime > 500000) {
      currentRPM = 0.0;
    }
  } else {
    currentRPM = 0.0;
  }
}

// --- ZOOM DIAL DETECTION (Same as before) ---
void updateZoom() {
  int newZoomState = digitalRead(ROTARY_CLK_PIN);
  if (newZoomState != lastZoomState) {
    if (digitalRead(ROTARY_DT_PIN) != newZoomState) {
      zoomChange = 1; // Clockwise (Zoom In)
    } else {
      zoomChange = -1; // Counter-Clockwise (Zoom Out)
    }
    lastZoomState = newZoomState;
  }
}
