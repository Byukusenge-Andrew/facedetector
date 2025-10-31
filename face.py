import cv2
import numpy as np
import time

# Initialize face detector
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

# Start webcam
cap = cv2.VideoCapture(0)

# Variables to track movement
prev_center = None
prev_time = time.time()

while True:
    ret, frame = cap.read()
    if not ret:
        break

    # Convert to grayscale
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # Detect faces
    faces = face_cascade.detectMultiScale(gray, scaleFactor=1.3, minNeighbors=5)

    for (x, y, w, h) in faces:
        # Draw bounding box
        cv2.rectangle(frame, (x, y), (x + w, y + h), (255, 0, 0), 2)

        # Calculate center of face
        center = (x + w // 2, y + h // 2)
        cv2.circle(frame, center, 5, (0, 255, 0), -1)

        # Calculate movement direction and speed
        if prev_center is not None:
            dx = center[0] - prev_center[0]
            dy = center[1] - prev_center[1]
            direction = ""

            if abs(dx) > 10:
                direction += "Right" if dx > 0 else "Left"
            if abs(dy) > 10:
                direction += " Down" if dy > 0 else " Up"

            # Calculate speed based on pixel movement per second
            current_time = time.time()
            dt = current_time - prev_time
            speed = np.sqrt(dx**2 + dy**2) / dt

            # Display direction and speed
            cv2.putText(frame, f"Direction: {direction}", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            cv2.putText(frame, f"Speed: {speed:.2f} px/s", (10, 60),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

            prev_time = current_time

        prev_center = center
        break  # Only track the first detected face

    # Display the frame
    cv2.imshow('Face Tracker', frame)

    # Exit on 'q' key
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# Cleanup
cap.release()
cv2.destroyAllWindows()