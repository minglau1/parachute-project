# Parachute Deployment System

This repository contains the MicroPython code for a flight computer designed to automatically deploy a parachute. It detects apogee (the highest point of flight) using an accelerometer and an altimeter, and then triggers a servo motor to release the parachute.

## Hardware Components
* **Microcontroller:** Raspberry Pi Pico (or similar MicroPython compatible board)
* **IMU (Accelerometer/Gyroscope):** MPU6050 (I2C)
* **Altimeter (Pressure Sensor):** BMP280 (I2C)
* **Actuator:** Standard 50Hz Servo Motor

## Features
* **Dual Apogee Detection:** Triggers parachute deployment based on two conditions (OR gate):
  * **Freefall Detection:** Senses when G-forces drop below a specific threshold.
  * **Altitude Drop Detection:** Senses when the altitude drops a certain distance from the maximum recorded altitude.
* **Flight Data Logging:** Records elapsed time, altitude, and G-force during the flight and saves the data to a `flight_data.csv` file on the microcontroller after the flight.
* **Servo Locking Mechanism:** Starts by holding the servo in a locked position (0 degrees) to secure a rubber band, and turns 90 degrees to release it upon deployment.

## Wiring (Default Configuration)
* **MPU6050 (I2C1):** SDA on GP14, SCL on GP15
* **BMP280 (I2C0):** SDA on GP4, SCL on GP5
* **Servo:** PWM on GP0

## Configuration
Inside `Parachute_sensor_test.py`, you can tweak the thresholds depending on your testing environment:
* `FREEFALL_THRESHOLD`: The G-force threshold for freefall detection.
* `FALL_DISTANCE`: The distance in meters the altitude must drop from max altitude to trigger deployment.

## Usage
1. Flash the code to your MicroPython board.
2. Ensure you have the `mpu6050.py` and `bmp280.py` driver files uploaded to the board.
3. Run `Parachute_sensor_test.py`.
4. The system will arm, lock the servo, and wait for the deployment conditions to be met.
