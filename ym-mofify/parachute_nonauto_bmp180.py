import machine
import time
from mpu6050 import init_mpu6050, get_mpu6050_data
from bmp180 import BMP180

# ==========================================
# 1. HARDWARE SETUP
# ==========================================
# Initialize I2C for Sensors (Lowered to 100kHz for MPU6050 stability)
i2c = machine.I2C(0, sda=machine.Pin(4), scl=machine.Pin(5), freq=100000)

# Initialize PWM for Servo on GP15
servo_pin = machine.Pin(15)
servo = machine.PWM(servo_pin)
servo.freq(50) # Standard servo frequency is 50Hz

# Helper function to move the servo
def set_servo_angle(angle):
    # Map an angle (0 to 180) to a PWM duty cycle (1638 to 8192 for SG90)
    min_duty = 1638
    max_duty = 8192
    duty = int(min_duty + (angle / 180.0) * (max_duty - min_duty))
    servo.duty_u16(duty)

# ==========================================
# 2. SENSOR INITIALIZATION
# ==========================================
print("Booting Flight Computer...")
time.sleep(0.5) # Give sensors a half-second to power up fully
init_mpu6050(i2c)
try:
    altimeter = BMP180(i2c)
except:
    print("BMP180 failed to initialize.")

# Set initial servo state to LOCKED (holding the rubber band)
set_servo_angle(0)
print("Servo Locked. Parachute Secured.")
time.sleep(2) # Give sensors time to stabilize

# ==========================================
# 3. FLIGHT VARIABLES & THRESHOLDS
# ==========================================
SEA_LEVEL_PRESSURE = 101325.0
max_altitude = -9999.0

# ⚠️ INDOOR TEST SETTINGS:
FREEFALL_THRESHOLD = 0.5   # Gs (Standard flight is 0.2)
FALL_DISTANCE = 0.5        # Meters (Standard flight is 2.0)

print("System Armed. Awaiting Launch...")
print("-" * 40)

# ==========================================
# 4. MAIN FLIGHT LOOP
# ==========================================
altitude_history = []

while True:
    try:
        # --- Read Sensors ---
        # 1. Accelerometer (G-Force)
        mpu_data = get_mpu6050_data(i2c)
        ax = mpu_data['accel']['x']
        ay = mpu_data['accel']['y']
        az = mpu_data['accel']['z']
        total_g = (ax**2 + ay**2 + az**2)**0.5
        
        # 2. Altimeter (Altitude)
        temp, pressure = altimeter.read_data()
        if pressure is None:
            continue # Skip this loop if the sensor lost connection
            
        raw_altitude = 44330.0 * (1.0 - (pressure / SEA_LEVEL_PRESSURE) ** 0.1903)
        
        # --- Apply Moving Average Filter (Smooths out 30cm noise) ---
        altitude_history.append(raw_altitude)
        if len(altitude_history) > 10:
            altitude_history.pop(0) # Keep only the last 10 readings
            
        current_altitude = sum(altitude_history) / len(altitude_history)
        
        # --- Update Flight Data ---
        if current_altitude > max_altitude:
            max_altitude = current_altitude
            
        print(f"Alt: {current_altitude:.2f}m (Max: {max_altitude:.2f}m) | G-Force: {total_g:.2f}G")
        
        # ==========================================
        # 5. PARACHUTE DEPLOYMENT LOGIC (The "OR" Gate)
        # ==========================================
        is_falling = current_altitude < (max_altitude - FALL_DISTANCE)
        is_weightless = total_g < FREEFALL_THRESHOLD
        
        if is_falling or is_weightless:
            print("\n!!! APOGEE DETECTED !!!")
            if is_falling: print("Trigger: Altitude Drop")
            if is_weightless: print("Trigger: Freefall G-Force")
            
            # TRIGGER SERVO RELEASE
            set_servo_angle(90) # Turn servo 90 degrees to slip the rubber band
            print("PARACHUTE DEPLOYED!")
            break # Exit the loop, mission accomplished!

        # Fast polling rate for quick reaction
        time.sleep(0.1) 

    except KeyboardInterrupt:
        print("\nFlight computer manually aborted.")
        break
    except Exception as e:
        print("Sensor Error:", e)
        time.sleep(0.1)
