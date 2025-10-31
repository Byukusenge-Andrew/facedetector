import serial
import time

def test_stepper_motor():
    """Simple test script to manually control the stepper motor"""
    
    # Connect to Arduino
    try:
        arduino = serial.Serial('COM8', 9600, timeout=2)
        print("Connecting to Arduino...")
        time.sleep(3)  # Wait for Arduino to initialize
        
        # Read any startup messages
        while arduino.in_waiting > 0:
            msg = arduino.readline().decode().strip()
            print(f"Arduino: {msg}")
        
        print("\n=== Stepper Motor Test ===")
        print("Commands:")
        print("  L - Move Left")
        print("  R - Move Right") 
        print("  S - Stop")
        print("  H - Home (center)")
        print("  I - Get Info")
        print("  Q - Quit")
        print("  T - Auto Test")
        
        while True:
            # Get user command
            command = input("\nEnter command: ").upper().strip()
            
            if command == 'Q':
                break
            elif command == 'T':
                # Automated test sequence
                print("Running automated test...")
                test_commands = ['I', 'R', 'R', 'R', 'S', 'L', 'L', 'L', 'S', 'H']
                
                for cmd in test_commands:
                    print(f"\nSending: {cmd}")
                    arduino.write(cmd.encode())
                    time.sleep(0.5)
                    
                    # Read response
                    timeout_count = 0
                    while timeout_count < 10:  # 2 second timeout
                        if arduino.in_waiting > 0:
                            response = arduino.readline().decode().strip()
                            print(f"Response: {response}")
                            break
                        time.sleep(0.2)
                        timeout_count += 1
                    
                    time.sleep(1)  # Wait between commands
                
                print("Automated test complete")
                
            elif command in ['L', 'R', 'S', 'H', 'I']:
                print(f"Sending command: {command}")
                arduino.write(command.encode())
                
                # Read response
                start_time = time.time()
                responses = []
                
                while time.time() - start_time < 3:  # 3 second timeout
                    if arduino.in_waiting > 0:
                        response = arduino.readline().decode().strip()
                        if response:
                            responses.append(response)
                            print(f"Response: {response}")
                    time.sleep(0.1)
                
                if not responses:
                    print("No response received - check connection")
                    
            else:
                print("Invalid command. Use L, R, S, H, I, T, or Q")
    
    except serial.SerialException as e:
        print(f"Serial connection error: {e}")
        print("Check:")
        print("1. Arduino is connected to COM8")
        print("2. No other programs are using the port")
        print("3. Arduino drivers are installed")
        
    except KeyboardInterrupt:
        print("\nTest interrupted")
        
    finally:
        try:
            arduino.close()
            print("Serial connection closed")
        except:
            pass

if __name__ == "__main__":
    test_stepper_motor()