// rx_serial_interface.ino - Receiver (PC Side)
// Receives wireless data and prints it to the PC's Serial port
// in the exact format required by the Python script: RPM,SteerX,SteerY,Zoom\n

#include <SPI.h>
#include "RF24.h"

// --- NRF24L01 PIN DEFINITIONS ---
RF24 radio(9, 10); // CE, CSN
const byte addresses[][6] = {"00001"}; // Unique address for the pipe (MUST MATCH TX)

// --- DATA STRUCTURE (MUST MATCH TRANSMITTER) ---
struct Payload {
    float rpm;
    int steerX;
    int steerY;
    int zoomChange;
};

void setup() {
  // IMPORTANT: The Python script is looking for this exact baud rate!
  Serial.begin(9600); 
  
  // 1. Initialize Radio
  radio.begin();
  radio.openReadingPipe(1, addresses[0]);
  radio.setPALevel(RF24_PA_LOW); 
  radio.startListening(); // Set as receiver
  
  Serial.println("Wireless Receiver Ready. Waiting for data...");
}

void loop() {
  // Check if data is available in the radio buffer
  if (radio.available()) {
    Payload receivedData;
    
    // Read the data packet
    radio.read(&receivedData, sizeof(receivedData));

    // Print the received data to the Serial port in the EXACT format 
    // the Python script expects: R,X,Y,Z\n
    Serial.print(receivedData.rpm);
    Serial.print(",");
    Serial.print(receivedData.steerX);
    Serial.print(",");
    Serial.print(receivedData.steerY);
    Serial.print(",");
    Serial.println(receivedData.zoomChange);
  }
  
  delay(10); // Small delay to prevent blocking
}
