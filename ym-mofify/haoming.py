import machine
import time
import math
from mpu6050 import init_mpu6050, get_mpu6050_data
from bmp280 import BMP280
from servo import Servo

# ==========================================
# 1. HARDWARE SETUP (ADJUST WHEN NEEDED!)
# ==========================================
# Initialize I2C for Sensors
i2c = machine.I2C(0, sda=machine.Pin(4), scl=machine.Pin(5), freq=100000)
# Initialize LEDs (Adjust pins to match your wiring!)
green_led = machine.Pin(19, machine.Pin.OUT)
red_led = machine.Pin(20, machine.Pin.OUT)
green_led.value(0)
red_led.value(0)

# Initialize Servo
parachute_servo = Servo(16)

# ==========================================
# 2. SENSOR INITIALIZATION
# ==========================================
print("Checking sensor connections...")
red_led.value(1)
# Loop until both sensors initialize successfully
while True:
    mpu_ok = False
    bmp_ok = False
    servo_ok = False
    
    try:
        init_mpu6050(i2c)
        mpu_ok = True
    except Exception as e:
        print("ERROR DETECTED: MPU6050 failed to initialize.")
        
    try:
        altimeter = BMP280(i2c)
        bmp_ok = True
    except Exception as e:
        print("ERROR DETECTED: BMP280 failed to initialize.")

    try:
        # Test the servo by moving it slightly
        parachute_servo.move(10)
        time.sleep(0.2)
        parachute_servo.move(0)
        servo_ok = True
    except Exception as e:
        print("ERROR DETECTED: Servo failed to move.")
        
    if mpu_ok and bmp_ok and servo_ok:
        print("All components initialized successfully!")
        break # Exit the loop, sensors are ready!
    else:
        print("Retrying in 2 seconds...")
        time.sleep(2)

# Set initial servo state to LOCKED (holding the rubber band)
parachute_servo.move(0)
print("Servo Locked. Parachute Secured.")
time.sleep(2) # Give sensors time to stabilize

# ==========================================
# 3. FLIGHT VARIABLES & THRESHOLDS
# ==========================================
SEA_LEVEL_PRESSURE = 101325.0
max_altitude = -9999.0

# SENSOR SENSITIVITY SETTINGS (ADJUST WHEN NEEDED!):
FREEFALL_THRESHOLD = 0.5   
FALL_DISTANCE = 0.5        # Lowered to 0.5m for shorter flights (like 7m)

red_led.value(0) # Turn off RED LED if all components work well
print("System Armed. Awaiting Launch...")
green_led.value(1) # Turn on GREEN LED to show the code is running successfully
print("-" * 40)

# ==========================================
# 4. MAIN FLIGHT LOOP
# ==========================================
try:
    log_file = open("flight_data.csv", "w")
    log_file.write("Time(s),Altitude(m),G-Force(G),Event\n")
except Exception as e:
    print("Failed to open log file:", e)
    log_file = None

apogee_detect_count = 0
start_time = time.ticks_ms()

while True:
    try:
        # --- Read Sensors ---
        # 1. Accelerometer (G-Force)
        mpu_data = get_mpu6050_data(i2c)
        accel = mpu_data['accel']
        total_g = math.sqrt(accel['x']**2 + accel['y']**2 + accel['z']**2)
        
        # 2. Altimeter (Altitude)
        temp, pressure = altimeter.read_data()
        current_altitude = 0.0
        if pressure is not None and pressure > 0:
            current_altitude = 44330.0 * (1.0 - (pressure / SEA_LEVEL_PRESSURE) ** 0.1903)
        
        # --- Update Flight Data ---
        if current_altitude > max_altitude:
            max_altitude = current_altitude
        
        # store events
        event_log = ""

        # Calculate elapsed time in seconds
        elapsed_time = time.ticks_diff(time.ticks_ms(), start_time) / 1000.0
        
        # ==========================================
        # 5. PARACHUTE DEPLOYMENT LOGIC (The "AND" Gate with Debounce)
        # ==========================================
        is_falling = current_altitude < (max_altitude - FALL_DISTANCE)
        is_weightless = total_g < FREEFALL_THRESHOLD
        if is_falling: 
            print("Trigger: Altitude Drop")
            event_log += "Altitude Drop "
        if is_weightless: 
            print("Trigger: Freefall G-Force")
            event_log += "Freefall "

        if is_falling and is_weightless:
            apogee_detect_count += 1
            print(f"\n!!! APOGEE DETECTED ({apogee_detect_count}/2) !!!")
            event_log += f"| APOGEE ({apogee_detect_count}/2) "

            if apogee_detect_count >= 2:
                # TRIGGER SERVO RELEASE
                parachute_servo.move(90) # Turn servo 90 degrees to slip the rubber band
                print("PARACHUTE DEPLOYED!")
                event_log += "| DEPLOYED!"
                green_led.value(0) # Turn off green
                red_led.value(1)   # Turn on red to indicate the active flight has ended
                
                # Store final data point before breaking
                if log_file:
                    log_file.write(f"{elapsed_time:.3f},{current_altitude:.2f},{total_g:.2f},{event_log.strip()}\n")
                    log_file.flush()
                time.sleep(1) # Give the servo time to physically move
                break # Exit the loop, mission accomplished!
        else:
            apogee_detect_count = 0

        # Store data for collection
        if log_file:
            log_file.write(f"{elapsed_time:.3f},{current_altitude:.2f},{total_g:.2f},{event_log.strip()}\n")
            log_file.flush()
        
        print(f"Time: {elapsed_time:.2f}s | Alt: {current_altitude:.2f}m (Max: {max_altitude:.2f}m) | G-Force: {total_g:.2f}G")

        time.sleep(0.05) 

    except KeyboardInterrupt:
        print("\nFlight computer manually aborted (Ctrl+C).")
        green_led.value(0)
        red_led.value(1)
        break
    except Exception as e:
        print("Sensor Error:", e)
        green_led.value(0)
        red_led.value(1)
        elapsed_time = time.ticks_diff(time.ticks_ms(), start_time) / 1000.0
        if log_file:
            log_file.write(f"{elapsed_time:.3f},{str(e)},0.0,ERROR\n")
            log_file.flush()
        time.sleep(0.1)
        break

# ==========================================
# 6. POST-FLIGHT DATA SAVING
# ==========================================
if log_file:
    log_file.close()
    print("\nData saved successfully to 'flight_data.csv'.")