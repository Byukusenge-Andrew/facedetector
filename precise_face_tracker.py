import cv2
import serial
import time
import numpy as np
from collections import deque

class PreciseFaceTracker:
    def __init__(self, com_port='COM8', baud_rate=9600):
        # Initialize Arduino connection
        try:
            self.arduino = serial.Serial(com_port, baud_rate, timeout=1)
            time.sleep(2)  # Allow Arduino to initialize
            print(f"Connected to Arduino on {com_port}")
        except serial.SerialException as e:
            print(f"Failed to connect to Arduino: {e}")
            self.arduino = None
        
        # Load face cascade with improved parameters
        self.face_cascade = cv2.CascadeClassifier('haarcascade_frontalface_default.xml')
        if self.face_cascade.empty():
            # Fallback to system cascade
            self.face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        
        # Initialize camera with optimized settings
        self.cap = cv2.VideoCapture(0)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.cap.set(cv2.CAP_PROP_FPS, 30)
        
        # Get frame dimensions
        self.frame_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.frame_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.frame_center_x = self.frame_width // 2
        
        # Tracking parameters
        self.deadband = 30  # Reduced deadband for more precision
        self.face_history = deque(maxlen=10)  # For temporal smoothing
        self.last_command_time = time.time()
        self.command_interval = 0.05  # Minimum time between commands (50ms)
        
        # Face detection parameters (optimized for accuracy)
        self.detection_params = {
            'scaleFactor': 1.1,  # More precise scaling
            'minNeighbors': 6,   # Higher threshold for stability
            'minSize': (40, 40), # Minimum face size
            'maxSize': (300, 300), # Maximum face size
            'flags': cv2.CASCADE_SCALE_IMAGE
        }
        
        print(f"Camera initialized: {self.frame_width}x{self.frame_height}")
    
    def detect_faces(self, frame):
        """Detect faces with improved accuracy"""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Apply histogram equalization for better contrast
        gray = cv2.equalizeHist(gray)
        
        # Apply Gaussian blur to reduce noise
        gray = cv2.GaussianBlur(gray, (3, 3), 0)
        
        faces = self.face_cascade.detectMultiScale(gray, **self.detection_params)
        return faces
    
    def smooth_face_position(self, face_center_x):
        """Apply temporal smoothing to reduce jitter"""
        self.face_history.append(face_center_x)
        
        if len(self.face_history) < 3:
            return face_center_x
        
        # Use weighted average with more weight on recent positions
        weights = np.exp(np.linspace(-1, 0, len(self.face_history)))
        weights /= weights.sum()
        
        smoothed_x = np.average(list(self.face_history), weights=weights)
        return int(smoothed_x)
    
    def calculate_direction(self, face_center_x):
        """Calculate movement direction with proportional control - FIXED for mirror mode"""
        smoothed_x = self.smooth_face_position(face_center_x)
        error = smoothed_x - self.frame_center_x
        
        # Proportional control zones
        if abs(error) <= self.deadband:
            return 'S', "Centered", 0
        elif error < -self.deadband:
            # Face is to the left in mirrored view, camera should move RIGHT
            intensity = min(abs(error) // 20, 5)  # Scale 1-5
            return 'R', f"Move Right (Face Left) - Intensity: {intensity}", intensity
        else:
            # Face is to the right in mirrored view, camera should move LEFT
            intensity = min(abs(error) // 20, 5)  # Scale 1-5
            return 'L', f"Move Left (Face Right) - Intensity: {intensity}", intensity
    
    def send_command(self, command):
        """Send command to Arduino with error handling"""
        current_time = time.time()
        
        # Limit command frequency to prevent overwhelming Arduino
        if current_time - self.last_command_time < self.command_interval:
            return
            
        if self.arduino and self.arduino.is_open:
            try:
                self.arduino.write(command.encode())
                self.arduino.flush()
                self.last_command_time = current_time
            except serial.SerialException as e:
                print(f"Serial communication error: {e}")
    
    def draw_tracking_info(self, frame, faces, direction, status, intensity):
        """Draw tracking information on frame"""
        # Draw center line
        cv2.line(frame, (self.frame_center_x, 0), (self.frame_center_x, self.frame_height), (0, 255, 255), 1)
        
        # Draw deadband zone
        deadband_left = self.frame_center_x - self.deadband
        deadband_right = self.frame_center_x + self.deadband
        cv2.line(frame, (deadband_left, 0), (deadband_left, self.frame_height), (0, 255, 0), 1)
        cv2.line(frame, (deadband_right, 0), (deadband_right, self.frame_height), (0, 255, 0), 1)
        
        # Draw faces
        for i, (x, y, w, h) in enumerate(faces):
            # Face rectangle
            cv2.rectangle(frame, (x, y), (x + w, y + h), (255, 0, 0), 2)
            
            # Face center
            face_center_x = x + w // 2
            face_center_y = y + h // 2
            cv2.circle(frame, (face_center_x, face_center_y), 5, (0, 0, 255), -1)
            
            # Face ID
            cv2.putText(frame, f'Face {i+1}', (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
        
        # Status information
        y_offset = 30
        cv2.putText(frame, f"Status: {status}", (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        
        if intensity > 0:
            y_offset += 30
            cv2.putText(frame, f"Intensity: {intensity}", (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
        
        # Frame info
        y_offset += 30
        cv2.putText(frame, f"Center: {self.frame_center_x} | Deadband: ±{self.deadband}", 
                   (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        # Connection status
        y_offset += 25
        arduino_status = "Connected" if (self.arduino and self.arduino.is_open) else "Disconnected"
        color = (0, 255, 0) if arduino_status == "Connected" else (0, 0, 255)
        cv2.putText(frame, f"Arduino: {arduino_status}", (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
    
    def run(self):
        """Main tracking loop"""
        print("Starting face tracking... Press 'q' to quit, 'r' to reset history")
        
        try:
            while True:
                ret, frame = self.cap.read()
                if not ret:
                    print("Failed to capture frame")
                    break
                
                # Flip frame horizontally for mirror effect
                frame = cv2.flip(frame, 1)
                
                # Detect faces
                faces = self.detect_faces(frame)
                
                direction = 'S'
                status = "No face detected"
                intensity = 0
                
                if len(faces) > 0:
                    # Use the largest face (most likely to be the main subject)
                    largest_face = max(faces, key=lambda face: face[2] * face[3])
                    x, y, w, h = largest_face
                    face_center_x = x + w // 2
                    
                    direction, status, intensity = self.calculate_direction(face_center_x)
                    
                    # Only consider faces array with the largest face for display
                    faces = [largest_face]
                
                else:
                    # Clear history when no face is detected
                    self.face_history.clear()
                
                # Send command to Arduino
                self.send_command(direction)
                
                # Draw tracking information
                self.draw_tracking_info(frame, faces, direction, status, intensity)
                
                # Display frame
                cv2.imshow('Precise Face Tracker', frame)
                
                # Handle keypresses
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    break
                elif key == ord('r'):
                    self.face_history.clear()
                    print("Face tracking history reset")
                elif key == ord('c'):
                    # Recalibrate center
                    self.frame_center_x = self.frame_width // 2
                    print(f"Center recalibrated to: {self.frame_center_x}")
                    
        except KeyboardInterrupt:
            print("\nTracking interrupted by user")
        
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Clean up resources"""
        print("Cleaning up...")
        if self.cap:
            self.cap.release()
        if self.arduino and self.arduino.is_open:
            self.arduino.close()
        cv2.destroyAllWindows()
        print("Cleanup completed")

def main():
    tracker = PreciseFaceTracker()
    tracker.run()

if __name__ == "__main__":
    main()