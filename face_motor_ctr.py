import cv2
import serial
import time

arduino = serial.Serial('COM8', 9600, timeout=1)
time.sleep(2)

face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
cap = cv2.VideoCapture(0)
frame_center_x = cap.get(3) // 2

while True:
    ret, frame = cap.read()
    if not ret:
        break

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, scaleFactor=1.3, minNeighbors=5)

    direction = "No face detected"
    command = 'S'

    for (x, y, w, h) in faces:
        face_center_x = x + w // 2
        cv2.rectangle(frame, (x, y), (x + w, y + h), (255, 0, 0), 2)

        if face_center_x < frame_center_x - 50:
            direction = "Left"
            command = 'L'
        elif face_center_x > frame_center_x + 50:
            direction = "Right"
            command = 'R'
        else:
            direction = "Centered"
            command = 'S'

        break

    arduino.write(command.encode())

    cv2.putText(frame, f"Direction: {direction}", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

    cv2.imshow('Face Tracker', frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
arduino.close()
cv2.destroyAllWindows()