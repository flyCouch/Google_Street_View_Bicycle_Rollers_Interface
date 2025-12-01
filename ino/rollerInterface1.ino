// arduino_simulator_interface.ino
// Connects Hall Sensor, Joystick (XY), and Rotary Dial to read bike speed,
// mouse look (XY), and zoom, sending data to Python via Serial.

// --- PIN DEFINITIONS ---
const int HALL_SENSOR_PIN = 2; // Digital Pin 2 (must be an interrupt pin)
const int JOYSTICK_X_PIN = A0;  // Analog Pin A0 for horizontal look (SteerX)
const int JOYSTICK_Y_PIN = A1;  // Analog Pin A1 for vertical look (SteerY)
const int ROTARY_DT_PIN = 7;    // Digital Pin for Rotary Encoder DT
const int ROTARY_CLK_PIN = 8;   // Digital Pin for Rotary Encoder CLK

// --- SPEED VARIABLES ---
volatile unsigned long lastPulseTime = 0;
volatile unsigned long pulseInterval = 0;
float rollerCircumferenceMeters = 2.0; // IMPORTANT: Set your roller circumference
float currentRPM = 0.0;
unsigned long speedTimer = 0;

// --- ROTARY ENCODER VARIABLES (ZOOM DIAL) ---
int lastZoomState;
volatile int zoomChange = 0; // +1 for zoom in, -1 for zoom out

// --- FUNCTION PROTOTYPE ---
void handleMagnetPulse();
void updateRPM();
void updateZoom();

void setup() {
  Serial.begin(9600);
  
  // Set up Hall Sensor (Speed)
  pinMode(HALL_SENSOR_PIN, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(HALL_SENSOR_PIN), handleMagnetPulse, FALLING);

  // Set up Rotary Encoder (Zoom Dial)
  pinMode(ROTARY_CLK_PIN, INPUT_PULLUP);
  pinMode(ROTARY_DT_PIN, INPUT_PULLUP);
  lastZoomState = digitalRead(ROTARY_CLK_PIN);
}

void loop() {
  // 1. Update RPM calculation every 50ms for smooth motion control
  if (millis() - speedTimer >= 50) {
    updateRPM();
    speedTimer = millis();
  }

  // 2. Read Steering Joystick (A0 and A1)
  int joystickX = analogRead(JOYSTICK_X_PIN);
  int joystickY = analogRead(JOYSTICK_Y_PIN);
  
  // Map joystick reading (0-1023) to a smooth directional range (-100 to 100)
  // This value determines the mouse movement speed and direction
  int steerXValue = map(joystickX, 0, 1023, -100, 100); // -100=left, 100=right
  int steerYValue = map(joystickY, 0, 1023, 100, -100); // 100=up, -100=down (reversed for mouse standard)

  // 3. Read Zoom Dial
  updateZoom();

  // 4. Send Data Packet (RPM, SteerX, SteerY, ZoomChange)
  // The Python script relies on this specific four-part format: R,X,Y,Z\n
  Serial.print(currentRPM);
  Serial.print(",");
  Serial.print(steerXValue);
  Serial.print(",");
  Serial.print(steerYValue);
  Serial.print(",");
  Serial.println(zoomChange);

  // Reset zoom change after sending
  zoomChange = 0;

  delay(50); // Send data every 50ms for smooth control
}

// --- INTERRUPT HANDLER (Called when magnet passes) ---
void handleMagnetPulse() {
  unsigned long currentTime = micros();
  pulseInterval = currentTime - lastPulseTime;
  lastPulseTime = currentTime;
}

// --- RPM CALCULATION ---
void updateRPM() {
  if (pulseInterval > 0) {
    // RPM = (60 seconds/minute * 1,000,000 microseconds/second) / pulse interval in microseconds
    currentRPM = (60000000.0 / pulseInterval);

    // If the interval is very long (bike stopped for > 500ms), assume 0 RPM
    if (micros() - lastPulseTime > 500000) {
      currentRPM = 0.0;
    }
  } else {
    currentRPM = 0.0;
  }
}

// --- ZOOM DIAL DETECTION ---
void updateZoom() {
  int newZoomState = digitalRead(ROTARY_CLK_PIN);
  if (newZoomState != lastZoomState) {
    if (digitalRead(ROTARY_DT_PIN) != newZoomState) {
      // Clockwise (Zoom In)
      zoomChange = 1;
    } else {
      // Counter-Clockwise (Zoom Out)
      zoomChange = -1;
    }
    lastZoomState = newZoomState;
  }
}
