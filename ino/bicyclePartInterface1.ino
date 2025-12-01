// tx_simulator.ino - Transmitter (Bike Side)
// Reads sensor data (Speed, Joystick XY, two Buttons, and Rotary Dial)
// and transmits the 6-part data packet wirelessly.

#include <SPI.h>
#include "RF24.h"

// --- NRF24L01 PIN DEFINITIONS ---
RF24 radio(9, 10); // CE, CSN
const byte addresses[][6] = {"00001"}; // Unique address for the pipe

// --- DATA STRUCTURE (MUST MATCH RECEIVER) ---
struct Payload {
    float rpm;
    int steerX;
    int steerY;
    int leftClick;
    int rightClick;
    int zoomChange; // New: Rotary Dial Scroll
};

// --- SENSOR PIN DEFINITIONS ---
const int HALL_SENSOR_PIN = 2;   // Digital Pin 2 (interrupt)
const int JOYSTICK_X_PIN = A0;   
const int JOYSTICK_Y_PIN = A1;   
const int LEFT_CLICK_PIN = 4;    // Left Click Button
const int RIGHT_CLICK_PIN = 5;   // Right Click Button
const int ROTARY_DT_PIN = 7;     // New: Rotary Encoder DT
const int ROTARY_CLK_PIN = 8;    // New: Rotary Encoder CLK

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
void updateZoom(); // Re-introduced

void setup() {
  Serial.begin(9600);
  
  // 1. Initialize Radio
  radio.begin();
  radio.openWritingPipe(addresses[0]);
  radio.setPALevel(RF24_PA_LOW); 
  radio.stopListening(); 

  // 2. Setup Sensor Pins
  pinMode(HALL_SENSOR_PIN, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(HALL_SENSOR_PIN), handleMagnetPulse, FALLING);
  
  pinMode(LEFT_CLICK_PIN, INPUT_PULLUP);
  pinMode(RIGHT_CLICK_PIN, INPUT_PULLUP);
  
  // Setup Rotary Encoder Pins
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

  // Read Analog Inputs (Joystick)
  int joystickX = analogRead(JOYSTICK_X_PIN);
  int joystickY = analogRead(JOYSTICK_Y_PIN);
  
  int steerXValue = map(joystickX, 0, 1023, -100, 100);
  int steerYValue = map(joystickY, 0, 1023, 100, -100); 

  // Read Digital Inputs (Buttons and Rotary)
  int leftState = digitalRead(LEFT_CLICK_PIN) == LOW ? 1 : 0;
  int rightState = digitalRead(RIGHT_CLICK_PIN) == LOW ? 1 : 0;
  updateZoom(); // Read dial input

  // 2. Assemble Data Payload
  Payload data;
  data.rpm = currentRPM;
  data.steerX = steerXValue;
  data.steerY = steerYValue;
  data.leftClick = leftState;
  data.rightClick = rightState;
  data.zoomChange = zoomChange; // Add zoom

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

// --- RPM CALCULATION ---
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

// --- ZOOM DIAL DETECTION (Rotary Encoder) ---
void updateZoom() {
  int newZoomState = digitalRead(ROTARY_CLK_PIN);
  if (newZoomState != lastZoomState) {
    if (digitalRead(ROTARY_DT_PIN) != newZoomState) {
      zoomChange = 1; // Clockwise (Scroll Up)
    } else {
      zoomChange = -1; // Counter-Clockwise (Scroll Down)
    }
    lastZoomState = newZoomState;
  }
}
