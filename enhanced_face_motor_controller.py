import cv2
import serial
import time
import threading
import queue
from collections import deque
import numpy as np

class EnhancedFaceMotorController:
    def __init__(self, com_port='COM10', baud_rate=9600):
        # Serial communication setup
        self.arduino = None
        self.serial_queue = queue.Queue()
        self.response_queue = queue.Queue()
        self.connect_arduino(com_port, baud_rate)
        
        # Face detection setup
        self.face_cascade = cv2.CascadeClassifier('haarcascade_frontalface_default.xml')
        if self.face_cascade.empty():
            self.face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        
        # Camera setup
        self.cap = cv2.VideoCapture(0)
        self.setup_camera()
        
        # Tracking parameters
        self.frame_center_x = self.frame_width // 2
        self.deadband = 20  # Tighter deadband for precision
        self.face_history = deque(maxlen=8)
        self.last_command_time = time.time()
        self.command_interval = 0.01  # Very fast command rate for aggressive continuous tracking
        
        # Continuous tracking parameters
        self.last_direction = 'S'
        self.continuous_movement = False
        self.movement_momentum = 0
        self.no_face_timeout = 0
        self.max_no_face_frames = 15  # More frames before stopping
        self.rotation_active = False
        
        # Centering stability (require N consecutive centered frames before stopping)
        self.centered_frames = 0
        self.centered_required = 5  # frames

    # Smoothing controls
        self.min_cmd_hz = 12.0   # min command frequency near center
        self.max_cmd_hz = 45.0   # max command frequency when far
        self.dir_lock_required = 3  # frames before switching direction
        self._dir_lock_counter = 0
        self._dir_locked = 'S'
        
        # Motor status
        self.motor_position = 0
        self.motor_limits = {'min': -1024, 'max': 1024}
        self.connection_status = False
        
        # Performance metrics
        self.frame_count = 0
        self.start_time = time.time()
        self.last_fps_update = time.time()
        self.fps = 0
        
        # Start serial communication thread
        self.serial_thread = threading.Thread(target=self.serial_communication_handler, daemon=True)
        self.serial_thread.start()
        
    def connect_arduino(self, com_port, baud_rate):
        """Connect to Arduino with error handling"""
        try:
            self.arduino = serial.Serial(com_port, baud_rate, timeout=1)
            time.sleep(2)  # Allow Arduino to initialize
            print(f"Connected to Arduino on {com_port}")
            self.connection_status = True
        except serial.SerialException as e:
            print(f"Failed to connect to Arduino: {e}")
            self.arduino = None
            self.connection_status = False
    
    def setup_camera(self):
        """Configure camera for optimal performance"""
        # Set camera resolution and FPS
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.cap.set(cv2.CAP_PROP_FPS, 30)
        
        # Auto-exposure and focus settings
        self.cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)  # Manual exposure
        self.cap.set(cv2.CAP_PROP_EXPOSURE, -6)         # Faster exposure
        
        # Get actual camera settings
        self.frame_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.frame_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.actual_fps = self.cap.get(cv2.CAP_PROP_FPS)
        
        print(f"Camera configured: {self.frame_width}x{self.frame_height} @ {self.actual_fps} FPS")
    
    def serial_communication_handler(self):
        """Handle serial communication in separate thread"""
        while True:
            try:
                # Send commands from queue
                if not self.serial_queue.empty() and self.arduino and self.arduino.is_open:
                    command = self.serial_queue.get_nowait()
                    self.arduino.write(command.encode())
                    self.arduino.flush()
                
                # Read responses
                if self.arduino and self.arduino.is_open and self.arduino.in_waiting > 0:
                    try:
                        response = self.arduino.readline().decode().strip()
                        if response:
                            self.process_arduino_response(response)
                    except UnicodeDecodeError:
                        pass  # Skip invalid characters
                
                time.sleep(0.001)  # Small delay to prevent excessive CPU usage
                
            except (serial.SerialException, OSError):
                self.connection_status = False
                time.sleep(0.1)
    
    def process_arduino_response(self, response):
        """Process responses from Arduino"""
        if ':' in response:
            parts = response.split(':')
            command_type = parts[0]
            
            if command_type in ['L', 'R']:
                # Parse movement response: "L:15,P:100"
                if ',' in parts[1]:
                    step_info, pos_info = parts[1].split(',')
                    if pos_info.startswith('P:'):
                        self.motor_position = int(pos_info[2:])
            
            elif command_type == 'INFO':
                # Parse info response: "INFO:P:0,L:-1024,R:1024"
                info_parts = parts[1].split(',')
                for info in info_parts:
                    if info.startswith('P:'):
                        self.motor_position = int(info[2:])
                    elif info.startswith('L:'):
                        self.motor_limits['min'] = int(info[2:])
                    elif info.startswith('R:'):
                        self.motor_limits['max'] = int(info[2:])
            
            self.connection_status = True
    
    def detect_and_track_face(self, frame):
        """Enhanced face detection with preprocessing"""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Preprocessing for better detection
        gray = cv2.equalizeHist(gray)
        gray = cv2.GaussianBlur(gray, (3, 3), 0)
        
        # Multi-scale detection for better accuracy
        faces = self.face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.08,
            minNeighbors=5,
            minSize=(50, 50),
            maxSize=(250, 250),
            flags=cv2.CASCADE_SCALE_IMAGE
        )
        
        return faces
    
    def smooth_face_position(self, face_center_x):
        """Apply temporal smoothing with outlier rejection"""
        # Add to history
        self.face_history.append(face_center_x)
        
        if len(self.face_history) < 3:
            return face_center_x
        
        # Remove outliers using median filter
        recent_positions = list(self.face_history)[-5:]  # Last 5 positions
        median_pos = np.median(recent_positions)
        
        # Filter out positions too far from median
        filtered_positions = [pos for pos in recent_positions 
                            if abs(pos - median_pos) < 100]
        
        if not filtered_positions:
            filtered_positions = recent_positions
        
        # Weighted average with more weight on recent positions
        weights = np.exp(np.linspace(-0.5, 0, len(filtered_positions)))
        weights /= weights.sum()
        
        smoothed_x = np.average(filtered_positions, weights=weights)
        return int(smoothed_x)
    
    def calculate_motor_command(self, face_center_x):
        """AGGRESSIVE CONTINUOUS ROTATION with center hysteresis
        - Keeps rotating in your direction until centered for N consecutive frames
        - Mirror-aware: if face appears left, rotate right, and vice versa
        """
        smoothed_x = self.smooth_face_position(face_center_x)
        error = smoothed_x - self.frame_center_x
        
        # Very tight deadband for precise centering
        effective_deadband = 8  # Much tighter for precise centering
        
        if abs(error) <= effective_deadband:
            # Only stop if we remain centered for several consecutive frames
            self.centered_frames += 1
            if self.centered_frames >= self.centered_required:
                self.rotation_active = False
                self.continuous_movement = False
                self.last_direction = 'S'
                return 'S', "✅ PERFECTLY CENTERED", 0, error
            else:
                # Keep slowly rotating in the last known direction until fully stable
                self.rotation_active = True
                self.continuous_movement = True
                direction = self.last_direction if self.last_direction in ('L','R') else ('R' if error < 0 else 'L')
                # Slow command rate near center
                self._update_command_interval(abs(error))
                return direction, "⚖️ NEAR CENTER - HOLDING DIRECTION", 2, error
        elif error < -effective_deadband:
            # Face is left in mirrored view, CONTINUOUSLY rotate RIGHT
            self.rotation_active = True
            self.continuous_movement = True
            proposed_dir = 'R'
            self._apply_direction_lock(proposed_dir)
            self.last_direction = self._dir_locked
            self.centered_frames = 0
            self._update_command_interval(abs(error))
            return self.last_direction, f"🔄 ROTATING RIGHT >>> Error: {error}px", 4, error
        else:
            # Face is right in mirrored view, CONTINUOUSLY rotate LEFT
            self.rotation_active = True
            self.continuous_movement = True  
            proposed_dir = 'L'
            self._apply_direction_lock(proposed_dir)
            self.last_direction = self._dir_locked
            self.centered_frames = 0
            self._update_command_interval(abs(error))
            return self.last_direction, f"🔄 ROTATING LEFT <<< Error: {error}px", 4, error

    def _update_command_interval(self, abs_error):
        """Adapt command interval based on how far from center we are (ease-in/out)."""
        # Map error pixels to Hz in [min_cmd_hz, max_cmd_hz]
        # Assume 0..200px typical range
        e = max(0.0, min(float(abs_error), 200.0))
        frac = e / 200.0
        target_hz = self.min_cmd_hz + frac * (self.max_cmd_hz - self.min_cmd_hz)
        # Convert to interval seconds
        self.command_interval = max(0.01, 1.0 / target_hz)

    def _apply_direction_lock(self, proposed_dir):
        """Prevent rapid direction flips; require N consecutive frames to switch."""
        if proposed_dir == self._dir_locked:
            self._dir_lock_counter = 0
            return
        # Different direction proposed
        if self._dir_locked in ('L', 'R'):
            self._dir_lock_counter += 1
            if self._dir_lock_counter >= self.dir_lock_required:
                self._dir_locked = proposed_dir
                self._dir_lock_counter = 0
        else:
            # If no lock yet, accept immediately
            self._dir_locked = proposed_dir
            self._dir_lock_counter = 0
    
    def send_motor_command(self, command):
        """Send command to motor with rate limiting"""
        current_time = time.time()
        
        if current_time - self.last_command_time >= self.command_interval:
            if not self.serial_queue.full():
                self.serial_queue.put(command)
                self.last_command_time = current_time
    
    def update_fps(self):
        """Update FPS calculation"""
        self.frame_count += 1
        current_time = time.time()
        
        if current_time - self.last_fps_update >= 1.0:  # Update every second
            elapsed_time = current_time - self.last_fps_update
            self.fps = self.frame_count / elapsed_time
            self.frame_count = 0
            self.last_fps_update = current_time
    
    def draw_enhanced_ui(self, frame, faces, command, status, intensity, error):
        """Draw comprehensive tracking interface"""
        # Draw reference lines
        cv2.line(frame, (self.frame_center_x, 0), (self.frame_center_x, self.frame_height), (0, 255, 255), 1)
        
        # Draw deadband zone
        deadband_left = self.frame_center_x - self.deadband
        deadband_right = self.frame_center_x + self.deadband
        cv2.rectangle(frame, (deadband_left, 0), (deadband_right, self.frame_height), (0, 255, 0), 1)
        
        # Draw faces with enhanced information
        for i, (x, y, w, h) in enumerate(faces):
            # Face rectangle with confidence-based color
            confidence_color = (0, 255, 0) if w*h > 5000 else (0, 165, 255)  # Green for high confidence
            cv2.rectangle(frame, (x, y), (x + w, y + h), confidence_color, 2)
            
            # Face center
            face_center_x = x + w // 2
            face_center_y = y + h // 2
            cv2.circle(frame, (face_center_x, face_center_y), 3, (0, 0, 255), -1)
            
            # Face size and position info
            cv2.putText(frame, f'Face {i+1} ({w}x{h})', (x, y-10), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.4, confidence_color, 1)
        
        # Status panel background
        cv2.rectangle(frame, (5, 5), (400, 160), (0, 0, 0), -1)
        cv2.rectangle(frame, (5, 5), (400, 160), (255, 255, 255), 1)
        
        # Status information
        y_offset = 25
        cv2.putText(frame, f"Status: {status}", (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        
        y_offset += 25
        cv2.putText(frame, f"Error: {error:+d}px | Deadband: ±{self.deadband}", 
                   (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        y_offset += 20
        cv2.putText(frame, f"Motor Pos: {self.motor_position} | Cmd: {command}", 
                   (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        # Connection and performance info
        y_offset += 20
        conn_color = (0, 255, 0) if self.connection_status else (0, 0, 255)
        conn_status = "Connected" if self.connection_status else "Disconnected"
        cv2.putText(frame, f"Arduino: {conn_status} | FPS: {self.fps:.1f}", 
                   (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.5, conn_color, 1)
        
        # Controls help
        y_offset += 20
        cv2.putText(frame, "Controls: Q=Quit, R=Reset, H=Home, I=Info", 
                   (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)
    
    def run(self):
        """Main tracking loop with enhanced performance"""
        print("Starting Enhanced Face Motor Controller...")
        print("Commands: Q=Quit, R=Reset tracking, H=Home motor, I=Motor info")
        
        # Request initial motor info
        self.send_motor_command('I')
        
        try:
            while True:
                ret, frame = self.cap.read()
                if not ret:
                    print("Failed to capture frame")
                    break
                
                # Flip for mirror effect
                frame = cv2.flip(frame, 1)
                
                # Detect faces
                faces = self.detect_and_track_face(frame)
                
                # Initialize defaults
                command = 'S'
                status = "No face detected"
                intensity = 0
                error = 0
                
                if len(faces) > 0:
                    # Use largest face
                    largest_face = max(faces, key=lambda f: f[2] * f[3])
                    x, y, w, h = largest_face
                    face_center_x = x + w // 2
                    
                    command, status, intensity, error = self.calculate_motor_command(face_center_x)
                    faces = [largest_face]  # Only show the tracked face
                    
                    # Reset no-face timeout
                    self.no_face_timeout = 0
                else:
                    # Handle no face detected - KEEP ROTATING to find face
                    self.no_face_timeout += 1
                    
                    if self.no_face_timeout < self.max_no_face_frames and self.rotation_active:
                        # AGGRESSIVELY continue rotating to find face
                        command = self.last_direction
                        remaining = self.max_no_face_frames - self.no_face_timeout
                        status = f"🔍🔄 ROTATING {self.last_direction} TO FIND FACE ({remaining} frames left)"
                        intensity = 3  # Keep rotating at good speed
                        error = 0
                    elif self.no_face_timeout < 30:  # Extended search time
                        # If still no face, try opposite direction
                        opposite_dir = 'L' if self.last_direction == 'R' else 'R'
                        command = opposite_dir
                        status = f"🔄 SEARCHING OPPOSITE DIRECTION: {opposite_dir}"
                        intensity = 3
                        error = 0
                        if self.no_face_timeout == self.max_no_face_frames:
                            self.last_direction = opposite_dir  # Switch direction
                    else:
                        # Finally stop after extended search
                        command = 'S'
                        status = "❌ NO FACE FOUND - STOPPED"
                        intensity = 0
                        error = 0
                        self.continuous_movement = False
                        self.rotation_active = False
                        self.last_direction = 'S'
                    
                    # Clear history when no face detected
                    self.face_history.clear()
                
                # Send motor command
                self.send_motor_command(command)
                
                # Update performance metrics
                self.update_fps()
                
                # Draw UI
                self.draw_enhanced_ui(frame, faces, command, status, intensity, error)
                
                # Display frame
                cv2.imshow('Enhanced Face Motor Controller', frame)
                
                # Handle user input
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    break
                elif key == ord('r'):
                    self.face_history.clear()
                    print("Face tracking reset")
                elif key == ord('h'):
                    self.send_motor_command('H')
                    print("Homing motor...")
                elif key == ord('i'):
                    self.send_motor_command('I')
                    print("Requesting motor info...")
                elif key == ord('c'):
                    self.frame_center_x = self.frame_width // 2
                    print(f"Center recalibrated: {self.frame_center_x}")
        
        except KeyboardInterrupt:
            print("\nController interrupted by user")
        
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Clean up resources"""
        print("Cleaning up...")
        
        # Stop motor
        if self.arduino and self.arduino.is_open:
            self.send_motor_command('S')
            time.sleep(0.1)
        
        # Close resources
        if self.cap:
            self.cap.release()
        if self.arduino and self.arduino.is_open:
            self.arduino.close()
        cv2.destroyAllWindows()
        
        print("Cleanup completed")

def main():
    controller = EnhancedFaceMotorController()
    controller.run()

if __name__ == "__main__":
    main()