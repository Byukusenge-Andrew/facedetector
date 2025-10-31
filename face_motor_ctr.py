import cv2
import serial
import time

# Connect to Arduino (adjust COM port)
arduino = serial.Serial('COM3', 9600, timeout=1)
time.sleep(2)

# Load face detector
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
cap = cv2.VideoCapture(0)
frame_center_x = cap.get(3) // 2

while True:
    ret, frame = cap.read()
    if not ret:
        break

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, scaleFactor=1.3, minNeighbors=5)

    for (x, y, w, h) in faces:
        face_center_x = x + w // 2
        cv2.rectangle(frame, (x, y), (x + w, y + h), (255, 0, 0), 2)

        if face_center_x < frame_center_x - 50:
            arduino.write(b'L\n')
        elif face_center_x > frame_center_x + 50:
            arduino.write(b'R\n')
        else:
            arduino.write(b'S\n')

        break

    cv2.imshow('Face Tracker', frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
arduino.close()
cv2.destroyAllWindows()