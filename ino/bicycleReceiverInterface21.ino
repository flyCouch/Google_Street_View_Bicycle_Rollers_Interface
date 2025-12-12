// rx_serial_interface.ino - Receiver (PC Side)
// Receives wireless data and prints it to the PC's Serial port
// in the EXACT 1-part format required by the Python script: 1 or 0, followed by \n


#include <SPI.h>
#include "RF24.h"

// --- NRF24L01 PIN DEFINITIONS ---
RF24 radio(10, 9); // CE, CSN
const byte addresses[][6] = {"00100"}; // Unique address for the pipe (MUST MATCH TX)

// --- DATA STRUCTURE (MUST MATCH TRANSMITTER) ---
struct Payload {
    bool spin;
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
    
    // Check radio connection status only for debugging, commented out for cleaner output
    // Serial.println(radio.isChipConnected() ? "NRF yes" : "NRF no");
    
    // Read the data packet
    radio.read(&receivedData, sizeof(receivedData));

    // Print the received boolean spin state as '1' or '0' followed by a newline (\r\n)
    Serial.println(receivedData.spin);
  }
}