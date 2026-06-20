import machine
import time
from mpu6050 import init_mpu6050, get_mpu6050_data
from bmp280 import BMP280

# ==========================================
# 1. HARDWARE SETUP
# ==========================================
# Initialize I2C for Sensors
i2c_gyro = machine.I2C(1, sda=machine.Pin(14), scl=machine.Pin(15), freq=400000)
i2c_pressure = machine.I2C(0, sda=machine.Pin(4), scl=machine.Pin(5), freq=400000)

# Initialize PWM for Servo on GP15
servo_pin = machine.Pin(0)
servo = machine.PWM(servo_pin)
servo.freq(50) # Standard servo frequency is 50Hz

# Helper function to move the servo
def set_servo_angle(angle):
    # Map an angle (0 to 180) to a PWM duty cycle (1000 to 9000)
    min_duty = 1638
    max_duty = 8192
    duty = int(min_duty + (angle / 180.0) * (max_duty - min_duty))
    servo.duty_u16(duty)

# ==========================================
# 2. SENSOR INITIALIZATION
# ==========================================
print("Booting Flight Computer...")
init_mpu6050(i2c_gyro)
try:
    altimeter = BMP280(i2c_pressure)
except:
    print("BMP280 failed to initialize.")

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
flight_data = []
start_time = time.ticks_ms()

while True:
    try:
        # --- Read Sensors ---
        # 1. Accelerometer (G-Force)
        mpu_data = get_mpu6050_data(i2c_gyro)
        ax = mpu_data['accel']['x']
        ay = mpu_data['accel']['y']
        az = mpu_data['accel']['z']
        total_g = (ax**2 + ay**2 + az**2)**0.5
        
        # 2. Altimeter (Altitude)
        temp, pressure = altimeter.read_data()
        current_altitude = 44330.0 * (1.0 - (pressure / SEA_LEVEL_PRESSURE) ** 0.1903)
        
        # --- Update Flight Data ---
        if current_altitude > max_altitude:
            max_altitude = current_altitude
            
        # Calculate elapsed time in seconds
        elapsed_time = time.ticks_diff(time.ticks_ms(), start_time) / 1000.0
        
        # Store data for collection
        flight_data.append((elapsed_time, current_altitude, total_g))
        
        print(f"Time: {elapsed_time:.2f}s | Alt: {current_altitude:.2f}m (Max: {max_altitude:.2f}m) | G-Force: {total_g:.2f}G")
        
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
            time.sleep(1) # Give the servo time to physically move
            break # Exit the loop, mission accomplished!

        # Fast polling rate for quick reaction
        time.sleep(0.05) 

    except KeyboardInterrupt:
        print("\nFlight computer manually aborted (Ctrl+C).")
        break
    except Exception as e:
        print("Sensor Error:", e)
        elapsed_time = time.ticks_diff(time.ticks_ms(), start_time) / 1000.0
        flight_data.append((elapsed_time, str(e), "ERROR"))
        time.sleep(0.1)

# ==========================================
# 6. POST-FLIGHT DATA SAVING
# ==========================================
if len(flight_data) > 0:
    print(f"\nSaving {len(flight_data)} data points to 'flight_data.csv'...")
    try:
        with open("flight_data.csv", "w") as f:
            f.write("Time(s),Altitude(m),G-Force(G)\n")
            for d in flight_data:
                if isinstance(d[1], str):
                    f.write(f"{d[0]:.3f},{d[1]},{d[2]}\n")
                else:
                    f.write(f"{d[0]:.3f},{d[1]:.2f},{d[2]:.2f}\n")
        print("Data saved successfully.")
    except Exception as e:
        print("Failed to save data:", e)