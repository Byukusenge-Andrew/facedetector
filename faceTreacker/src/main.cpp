#include <Arduino.h>
#include <Stepper.h>

// Stepper motor configuration for 28BYJ-48
const int stepsPerRevolution = 2048;
Stepper myStepper(stepsPerRevolution, 8, 10, 9, 11);

// Precision control parameters (reduced speeds for 28BYJ-48 reliability)
const int baseStepSize = 20;        // Base step size for movement
const int maxStepSize = 100;        // Maximum step size
const int speedSlow = 12;           // RPM for precise movements (28BYJ-48 optimal range)
const int speedFast = 18;           // RPM for larger movements (max reliable speed)

// Timing and control variables
unsigned long lastCommandTime = 0;
const unsigned long commandCooldown = 30;  // Minimum ms between movements
char lastCommand = 'S';
int consecutiveCommands = 0;

// Position tracking (approximate)
long currentPosition = 0;
const long maxPosition = 1024;     // Maximum steps in each direction
const long minPosition = -1024;

void setup() {
  Serial.begin(9600);
  myStepper.setSpeed(speedSlow);
  
  // Initialize position to center
  currentPosition = 0;
  lastCommandTime = millis();
  
  // Send ready signal with motor test
  Serial.println("=== Face Tracker Arduino v2.0 ===");
  Serial.println("Testing stepper motor...");
  
  // Quick motor test on startup
  myStepper.step(50);   // Small test movement
  delay(500);
  myStepper.step(-50);  // Return to start
  
  Serial.println("Motor test complete");
  Serial.println("Arduino Ready - Send L/R/S/H/I commands");
}

void loop() {
  if (Serial.available() > 0) {
    char command = Serial.read();
    unsigned long currentTime = millis();
    
    // Check command cooldown to prevent overwhelming the motor
    if (currentTime - lastCommandTime < commandCooldown) {
      // Clear remaining buffer and return
      while (Serial.available() > 0) {
        Serial.read();
      }
      return;
    }
    
    // Process command
    processMovementCommand(command);
    
    // Update timing
    lastCommandTime = currentTime;
    
    // Clear any remaining bytes in buffer
    while (Serial.available() > 0) {
      Serial.read();
    }
  }
}

void processMovementCommand(char command) {
  int stepSize = 0;
  int motorSpeed = speedSlow;
  
  // Track consecutive commands for adaptive stepping
  if (command == lastCommand && command != 'S') {
    consecutiveCommands++;
  } else {
    consecutiveCommands = 0;
  }
  
  switch (command) {
    case 'L':
      // Calculate step size based on consecutive commands
      stepSize = calculateStepSize();
      motorSpeed = (stepSize > baseStepSize * 2) ? speedFast : speedSlow;
      
      // Check position limits
      if (currentPosition - stepSize >= minPosition) {
        Serial.print("Moving L:");
        Serial.print(stepSize);
        Serial.print(" at ");
        Serial.print(motorSpeed);
        Serial.println("RPM");
        
        myStepper.setSpeed(motorSpeed);
        myStepper.step(-stepSize);
        currentPosition -= stepSize;
        
        // Send feedback
        Serial.print("L:");
        Serial.print(stepSize);
        Serial.print(",P:");
        Serial.println(currentPosition);
      } else {
        Serial.println("L:LIMIT_REACHED");
      }
      break;
      
    case 'R':
      // Calculate step size based on consecutive commands
      stepSize = calculateStepSize();
      motorSpeed = (stepSize > baseStepSize * 2) ? speedFast : speedSlow;
      
      // Check position limits
      if (currentPosition + stepSize <= maxPosition) {
        Serial.print("Moving R:");
        Serial.print(stepSize);
        Serial.print(" at ");
        Serial.print(motorSpeed);
        Serial.println("RPM");
        
        myStepper.setSpeed(motorSpeed);
        myStepper.step(stepSize);
        currentPosition += stepSize;
        
        // Send feedback
        Serial.print("R:");
        Serial.print(stepSize);
        Serial.print(",P:");
        Serial.println(currentPosition);
      } else {
        Serial.println("R:LIMIT_REACHED");
      }
      break;
      
    case 'S':
      // Stay still - just send acknowledgment
      Serial.println("S:STOP");
      break;
      
    case 'H':
      // Home position - return to center
      homeMotor();
      break;
      
    case 'I':
      // Info request - send current status
      Serial.print("INFO:P:");
      Serial.print(currentPosition);
      Serial.print(",L:");
      Serial.print(minPosition);
      Serial.print(",R:");
      Serial.println(maxPosition);
      break;
      
    default:
      Serial.println("ERROR:INVALID_COMMAND");
      break;
  }
  
  lastCommand = command;
}

int calculateStepSize() {
  // Progressive step size based on consecutive commands
  int stepSize = baseStepSize;
  
  if (consecutiveCommands > 0) {
    // Gradually increase step size for continuous movement
    stepSize = baseStepSize + (consecutiveCommands * 8);
    
    // Cap at maximum step size
    if (stepSize > maxStepSize) {
      stepSize = maxStepSize;
    }
  }
  
  return stepSize;
}

void homeMotor() {
  Serial.println("HOMING...");
  
  // Calculate steps needed to return to center
  long stepsToHome = -currentPosition;
  
  if (stepsToHome != 0) {
    myStepper.setSpeed(speedSlow);
    
    // Move in chunks to avoid blocking for too long
    int chunkSize = 50;
    while (abs(stepsToHome) > 0) {
      int moveSteps = (abs(stepsToHome) > chunkSize) ? 
                      (stepsToHome > 0 ? chunkSize : -chunkSize) : 
                      stepsToHome;
      
      myStepper.step(moveSteps);
      stepsToHome -= moveSteps;
      currentPosition += moveSteps;
      
      // Allow for interruption
      if (Serial.available() > 0) {
        break;
      }
    }
  }
  
  currentPosition = 0;
  consecutiveCommands = 0;
  Serial.println("HOME:COMPLETE");
}