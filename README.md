# Parachute Deployment System (v3.0)
This repository contains the MicroPython code for a flight computer designed to automatically deploy a parachute. It detects apogee (the highest point of flight) using an accelerometer (MPU6050) and an altimeter (BMP180), and triggers a servo motor to release the parachute.

## Hardware Components
* **Microcontroller:** Raspberry Pi Pico 2 W
* **IMU (Accelerometer/Gyroscope):** MPU6050 (I2C)
* **Altimeter (Pressure & Temp Sensor):** BMP180 (I2C)
* **Actuator:** SG90 Servo Motor
* **Status Indicators:** 2x LEDs (Green and Red)

## New Features (v3.0)
* **Wireless Data Transfer (Wi-Fi Server):** After a flight, the Pico hosts a custom Wi-Fi Access Point (`Pico_Rocket`). Connect your phone to download the flight data from a stylised web page (with a custom `images.jpg` background).
* **Auto-Incrementing Flight Logs:** Flight data is automatically saved into a dedicated `flight data collection` folder on the Pico. It auto-increments the file name (e.g., `flight_data_1.csv`, `flight_data_2.csv`) every boot so you never accidentally overwrite old flights.
* **Dual Apogee Detection ("AND" Gate):** Triggers parachute deployment only when two conditions are met simultaneously over 3 consecutive checks (Debouncing):
  * **Freefall Detection:** Senses when G-forces drop below the `FREEFALL_THRESHOLD`.
  * **Altitude Drop Detection:** Senses when the altitude drops a certain distance from the maximum recorded altitude (`FALL_DISTANCE`).
* **Desktop Companion Tool (`plot_data.py`):** An interactive graphing tool for your PC. It lets you use a file-picker to select any downloaded CSV flight data, graphs the physics of the flight, and auto-saves a high-res PNG report to `flight data collection/png folder`.

## Wiring (v3.0 Configuration)
* **I2C0 (Sensors):** SDA on GP4, SCL on GP5
* **Servo:** PWM on GP15
* **Green LED:** GP16
* **Red LED:** GP17

## Usage
1. Use Thonny IDE to upload `parachute_v3.0.py` and the `lib` folder to the Pico.
2. Run `parachute_v3.0.py`. The system will arm, lock the servo, and wait for deployment conditions. Note: The servo will only deploy the parachute when the two conditions are met simultaneously over 3 consecutive checks (Debouncing).
3. After the flight, connect to the `Pico_Rocket` Wi-Fi with password `flightdata123` and navigate to `http://192.168.4.1` to download your data.
4. On your PC, run `python plot_data.py` to analyze the downloaded CSV files and save the report (which is saved in `flight data collection/png folder`).
