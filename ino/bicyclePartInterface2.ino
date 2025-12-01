// tx_simulator.ino - Transmitter (Bike Side)
// Reads sensor data (Speed, Joystick XY, and four Left-Handlebar Buttons)
// and transmits the 7-part data packet wirelessly.

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
    int leftClick;   // D4
    int rightClick;  // D5
    int scrollUp;    // D7
    int scrollDown;  // D8
};

// --- SENSOR PIN DEFINITIONS ---
const int HALL_SENSOR_PIN = 2;   // Digital Pin 2 (interrupt) - Bike Speed
const int JOYSTICK_X_PIN = A0;   // Analog 0 - Steering X
const int JOYSTICK_Y_PIN = A1;   // Analog 1 - Steering Y

// --- LEFT HANDLEBAR BUTTONS (All using INPUT_PULLUP) ---
const int LEFT_CLICK_PIN = 4;    // Digital Pin 4
const int RIGHT_CLICK_PIN = 5;   // Digital Pin 5
const int SCROLL_UP_PIN = 7;     // Digital Pin 7 (Scroll/Zoom In)
const int SCROLL_DOWN_PIN = 8;   // Digital Pin 8 (Scroll/Zoom Out)

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

  // 2. Setup Sensor Pins
  pinMode(HALL_SENSOR_PIN, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(HALL_SENSOR_PIN), handleMagnetPulse, FALLING);
  
  // Setup all four buttons with internal pull-up resistors
  pinMode(LEFT_CLICK_PIN, INPUT_PULLUP);
  pinMode(RIGHT_CLICK_PIN, INPUT_PULLUP);
  pinMode(SCROLL_UP_PIN, INPUT_PULLUP);
  pinMode(SCROLL_DOWN_PIN, INPUT_PULLUP);
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

  // Read Digital Inputs (Buttons)
  // LOW means pressed because of INPUT_PULLUP, resulting in a value of 1
  int leftState = digitalRead(LEFT_CLICK_PIN) == LOW ? 1 : 0;
  int rightState = digitalRead(RIGHT_CLICK_PIN) == LOW ? 1 : 0;
  int scrollUpState = digitalRead(SCROLL_UP_PIN) == LOW ? 1 : 0;
  int scrollDownState = digitalRead(SCROLL_DOWN_PIN) == LOW ? 1 : 0;

  // 2. Assemble Data Payload (7-part structure)
  Payload data;
  data.rpm = currentRPM;
  data.steerX = steerXValue;
  data.steerY = steerYValue;
  data.leftClick = leftState;
  data.rightClick = rightState;
  data.scrollUp = scrollUpState;
  data.scrollDown = scrollDownState;

  // 3. Transmit Data
  radio.write(&data, sizeof(data));

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
