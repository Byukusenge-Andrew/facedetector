#include <Arduino.h>
#include <Stepper.h>  // ✅ Built-in Arduino library

// Define steps per revolution (adjust for your motor)
const int stepsPerRevolution = 2048;

// Initialize stepper motor on pins IN1-IN4
Stepper myStepper(stepsPerRevolution, 8, 10, 9, 11);

void setup() {
  Serial.begin(9600);
  myStepper.setSpeed(10);  // Set motor speed in RPM
}

void loop() {
  if (Serial.available()) {
    char command = Serial.read();

    if (command == 'L') {
      myStepper.step(-50);  // Rotate left
    } else if (command == 'R') {
      myStepper.step(50);   // Rotate right
    }
    // 'S' means stay — no movement
  }
}