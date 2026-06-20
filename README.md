# Parachute Deployment System

This repository contains the MicroPython code for a flight computer designed to automatically deploy a parachute. It detects apogee (the highest point of flight) using an accelerometer (MPU6050) and an altimeter (BMP280), and then triggers a servo motor to release the parachute.

## Hardware Components
* **Microcontroller:** Raspberry Pi Pico 2 W/H (or similar MicroPython compatible board)
* **IMU (Accelerometer/Gyroscope):** MPU6050 (I2C)
* **Altimeter (Pressure Sensor):** BMP280 (I2C)
* **Actuator:** SG90 Servo Motor
* **Status Indicators:** 2x LEDs (Green and Red)

## Features
* **Dual Apogee Detection ("AND" Gate):** Triggers parachute deployment only when two conditions are met simultaneously over 3 consecutive checks (Debouncing):
  * **Freefall Detection:** Senses when G-forces drop below the `FREEFALL_THRESHOLD`.
  * **Altitude Drop Detection:** Senses when the altitude drops a certain distance from the maximum recorded altitude (`FALL_DISTANCE`).
* **Flight Data Logging (CSV):** Records elapsed time, altitude, G-force, and specific text events (e.g., "Altitude Drop", "Freefall", "DEPLOYED!") to a `flight_data.csv` file for post-flight graphing and analysis.
* **Hardware Self-Check & Wiggle Test:** Automatically checks all sensor I2C connections on boot. Performs a physical "wiggle" test on the servo to visually confirm it is receiving power and signals before locking into the armed position.
* **LED Status Indicators:** 
  * **Red LED:** Error initializing sensors, or the flight has concluded.
  * **Green LED:** Sensors passed self-check and the system is actively armed and flying.

## Wiring (Default Configuration)
* **MPU6050 (I2C1):** SDA on GP14, SCL on GP15
* **BMP280 (I2C0):** SDA on GP4, SCL on GP5
* **Servo:** PWM on GP16
* **Green LED:** GP19
* **Red LED:** GP20

## Configuration
Inside `parachute_v0.1.py`, you can tweak the thresholds depending on your testing environment:
* `FREEFALL_THRESHOLD`: The G-force threshold for freefall detection.
* `FALL_DISTANCE`: The distance in meters the altitude must drop from max altitude to trigger deployment.

## Usage
1. Use relevant interpreter such as Thonny IDE to upload all the files to the board.
2. Ensure you have the `lib` folder uploaded to the board.
3. Run `parachute_v0.1.py`.
4. The system will arm, lock the servo, and wait for the deployment conditions to be met.
