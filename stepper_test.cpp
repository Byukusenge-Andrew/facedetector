#include <Arduino.h>
#include <Stepper.h>

// Stepper motor configuration - 28BYJ-48 with ULN2003 driver
const int stepsPerRevolution = 2048;  // 28BYJ-48 is 2048 steps per full revolution

// Initialize the stepper library on pins 8-11:
// Note: The sequence should be 8,10,9,11 for proper operation with ULN2003
Stepper myStepper(stepsPerRevolution, 8, 10, 9, 11);

void setup() {
  Serial.begin(9600);
  
  // Set a slow speed for testing
  myStepper.setSpeed(10);  // 10 RPM - slow for testing
  
  Serial.println("=== Stepper Motor Test ===");
  Serial.println("Starting in 3 seconds...");
  delay(3000);
  
  Serial.println("Testing stepper motor...");
}

void loop() {
  Serial.println("Moving clockwise 1/4 turn (512 steps)");
  myStepper.step(512);
  delay(2000);
  
  Serial.println("Moving counter-clockwise 1/4 turn (-512 steps)");
  myStepper.step(-512);
  delay(2000);
  
  Serial.println("Moving clockwise 1/8 turn (256 steps)");
  myStepper.step(256);
  delay(1000);
  
  Serial.println("Moving counter-clockwise 1/8 turn (-256 steps)");
  myStepper.step(-256);
  delay(1000);
  
  Serial.println("Test cycle complete. Pausing...");
  delay(5000);
}