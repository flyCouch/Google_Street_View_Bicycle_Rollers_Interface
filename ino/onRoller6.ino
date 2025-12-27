/*
 * RollerAnalog_Uno.ino
 * CALIBRATED FOR SS49E ANALOG SENSOR
 * Logic: Every time the analog value crosses 650, send "1" to Python.
 */

const int HALL_SENSOR_PIN = A0;   //
const int MAGNET_THRESHOLD = 650; //

// --- STATE ---
bool magnetDetected = false;
unsigned long lastPulseTime_us = 0;

void setup() {
  Serial.begin(9600);
  pinMode(HALL_SENSOR_PIN, INPUT);
  Serial.println("--- Analog Roller System Active ---");
}

void loop() {
  int analogReading = analogRead(HALL_SENSOR_PIN);
  
  if (analogReading > MAGNET_THRESHOLD) {
    if (magnetDetected == false) {
      unsigned long currentTime_us = micros();
      
      // 1ms Debounce - prevents 'chatter'
      if (currentTime_us - lastPulseTime_us > 1000) { 
        lastPulseTime_us = currentTime_us;
        
        // Send '1' to Python: Every pulse = One 81mm roller rotation
        Serial.println("1"); 
      }
      magnetDetected = true;
    }
  } else {
    magnetDetected = false;
  }
}