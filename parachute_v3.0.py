import machine
import time
import gc
import network
import socket
import os
from mpu6050.mpu6050 import init_mpu6050, get_mpu6050_data
from bmp180.bmp180 import BMP180
from servo.servo import Servo

# ==========================================
# 1. HARDWARE SETUP (ADJUST WHEN NEEDED!)
# ==========================================
# Initialize I2C for Sensors
i2c = machine.I2C(0, sda=machine.Pin(4), scl=machine.Pin(5), freq=100000)

# Initialize LEDs
green_led = machine.Pin(16, machine.Pin.OUT)
red_led = machine.Pin(17, machine.Pin.OUT)
green_led.value(0)
red_led.value(0)

# Initialize Servo
parachute_servo = Servo(15)

# ==========================================
# 2. SENSOR INITIALIZATION
# ==========================================
print("Checking components connections...")
red_led.value(1)

# Loop until all components initialize successfully
while True:
    mpu_ok = False
    bmp_ok = False
    
    # Check if the servo moves successfully (can add button if needed to show success)
    parachute_servo.move(10)
    time.sleep(0.2)
    parachute_servo.move(0)

    try:
        init_mpu6050(i2c)
        mpu_ok = True
    except Exception as e:
        print("ERROR DETECTED: MPU6050 failed to initialize.")
        
    try:
        altimeter = BMP180(i2c)
        bmp_ok = True
    except Exception as e:
        print("ERROR DETECTED: BMP180 failed to initialize.")
        
    if mpu_ok and bmp_ok:
        print("All components initialized successfully!")
        break # Exit the loop, sensors are ready!
    else:
        print("Retrying in 2 seconds...")
        time.sleep(2)

# Set initial servo state to LOCKED (holding the rubber band)
parachute_servo.move(0)
print("Servo Locked. Parachute Secured.")
print("Warming up sensors and flushing noise filters...")
for _ in range(60): # Loop 40 times over 2 seconds to flush out the software IIR filter
    try:
        altimeter.read_data()
        altimeter.read_altitude()
    except Exception:
        pass
    time.sleep(0.1)
print("Sensors stabilized and ready!")

# ==========================================
# 3. FLIGHT VARIABLES & THRESHOLDS
# ==========================================
SEA_LEVEL_PRESSURE = 101325.0
max_altitude = -9999.0

# SENSOR SENSITIVITY SETTINGS (ADJUST WHEN NEEDED!):
FREEFALL_THRESHOLD = 0.5   
FALL_DISTANCE = 2.0        
MAX_ALTITUDE_JUMP = 15.0 # Max meters allowed to jump per reading (noise filter)
MAX_DATA_POINTS = 50   

red_led.value(0) # Turn off RED LED if all components work well
print("System Armed. Awaiting Launch...")
green_led.value(1) # Turn on GREEN LED to show the code is running successfully
print("-" * 40)

# ==========================================
# 4. MAIN FLIGHT LOOP
# ==========================================
# Ensure the data directory exists
data_dir = "flight data collection"
try:
    os.mkdir(data_dir)
except OSError:
    pass # Directory already exists

# Initialize the CSV file with headers before launch
current_csv_file = f"{data_dir}/flight_data_1.csv"
try:
    file_index = 1
    while True:
        current_csv_file = f"{data_dir}/flight_data_{file_index}.csv"
        try:
            os.stat(current_csv_file)
            file_index += 1
        except OSError:
            break
            
    print(f"Creating new flight log: {current_csv_file}")
    with open(current_csv_file, "w") as f:
        f.write("Time(s),Altitude(m),G-Force(G),Accel_X,Accel_Y,Accel_Z,Temp(C),Event\n")
except Exception as e:
    print("Warning: Could not initialize CSV file:", e)

# Helper function to append data to the CSV
def save_flight_data_chunk(data_list):
    gc.collect() # FORCE garbage collection to free up contiguous memory for the 4KB file buffer!
    try:
        with open(current_csv_file, "a") as f:
            for d in data_list:
                f.write(f"{d[0]:.3f},{d[1]:.2f},{d[2]:.2f},{d[3]:.2f},{d[4]:.2f},{d[5]:.2f},{d[6]:.2f},{d[7]}\n")
    except Exception as e:
        print("Failed to save data:", e)

flight_data = []
start_time = time.ticks_ms()
apogee_detect_count = 0

try:
    while True:
        try:
            # LED status
            green_led.value(1)
            red_led.value(0)

            # --- Read Sensors ---
            # 1. Accelerometer (G-Force)
            mpu_data = get_mpu6050_data(i2c)
            total_g = mpu_data['total_g']
            accel_x = mpu_data['accel']['x']
            accel_y = mpu_data['accel']['y']
            accel_z = mpu_data['accel']['z']
            
            # 2. Altimeter (Altitude & Temp)
            temp, pressure = altimeter.read_data()
            current_altitude = 0.0
            if pressure is not None and pressure > 0:
                current_altitude = 44330.0 * (1.0 - (pressure / SEA_LEVEL_PRESSURE) ** 0.1903)
            if temp is None:
                temp = 0.0
            
            # --- Update Flight Data ---
            if current_altitude > max_altitude:
                # Filter out sudden noise spikes (e.g. glitch saying we jumped 1000m instantly)
                if max_altitude == -9999.0 or (current_altitude - max_altitude) < MAX_ALTITUDE_JUMP:
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

            # Conditions of the rocket
            if is_falling: 
                print("Trigger: Altitude Drop")
                event_log += "Altitude Drop "
            if is_weightless: 
                print("Trigger: Freefall G-Force")
                event_log += "Freefall "

            # Conditions of the apogee
            if is_falling and is_weightless:
                apogee_detect_count += 1
                print(f"\n!!! APOGEE DETECTED ({apogee_detect_count}/3) !!!")
                event_log += f"| APOGEE ({apogee_detect_count}/3) "
    
                if apogee_detect_count >= 3:
                    # TRIGGER SERVO RELEASE
                    parachute_servo.move(90) # Turn servo 90 degrees to slip the rubber band (change as needed)
                    print("PARACHUTE DEPLOYED!")
                    event_log += "| DEPLOYED!"
                    green_led.value(0) # Turn off green
                    red_led.value(1)   # Turn on red to indicate the active flight has ended
                    
                    # Store final data
                    flight_data.append((elapsed_time, current_altitude, total_g, accel_x, accel_y, accel_z, temp, event_log.strip()))
                    time.sleep(1) # Give the servo time to physically move
                    break 
            else:
                apogee_detect_count = 0
    
            # Store data for collection
            flight_data.append((elapsed_time, current_altitude, total_g, accel_x, accel_y, accel_z, temp, event_log.strip()))
            
            # Memory Leak Fix: Save in batches to ensure infinite data without crashing RAM
            if len(flight_data) >= MAX_DATA_POINTS:
                save_flight_data_chunk(flight_data)
                flight_data = []
                gc.collect() # Instantly clear the old list from RAM
                
            print(f"Time: {elapsed_time:.2f}s | Alt: {current_altitude:.2f}m (Max: {max_altitude:.2f}m) | G-Force: {total_g:.2f}G")
            time.sleep(0.05) 
    
        except Exception as e:
            error_msg = "Sensor Error: " + str(e)
            print(error_msg)
            green_led.value(0)
            red_led.value(1)
            
            # Prevent spamming the same error
            if len(flight_data) == 0 or flight_data[-1][7] != error_msg:
                elapsed_time = time.ticks_diff(time.ticks_ms(), start_time) / 1000.0
                flight_data.append((elapsed_time, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, error_msg))
                
                # Memory Leak Fix
                if len(flight_data) >= MAX_DATA_POINTS:
                    save_flight_data_chunk(flight_data)
                    flight_data = []
                
            time.sleep(0.1)

except KeyboardInterrupt:
    print("\nFlight computer manually aborted (Ctrl+C).")
    green_led.value(0)
    red_led.value(1)
    
# ==========================================
# 6. POST-FLIGHT DATA SAVING
# ==========================================
# Save the remaining data after breaking the while loop
if len(flight_data) > 0:
    print(f"\nSaving {len(flight_data)} data points to '{current_csv_file}'...")
    save_flight_data_chunk(flight_data)
    print("Final data saved successfully.")

# ==========================================
# 7. WIRELESS DATA TRANSFER (WIFI AP)
# ==========================================
print("\nStarting Wi-Fi Access Point for data download...")
try:
    ap = network.WLAN(network.AP_IF)
    ap.active(True)
    # Different MicroPython versions use either ssid or essid. Try ssid first.
    try:
        ap.config(ssid='Pico_Rocket', password='flightdata123')
    except:
        ap.config(essid='Pico_Rocket', password='flightdata123')

    while ap.active() == False:
        pass

    print("AP Mode Active!")
    print("SSID: Pico_Rocket")
    print("Password: flightdata123")
    print("IP Address: " + ap.ifconfig()[0])
    print("Connect your device to this Wi-Fi and open http://" + ap.ifconfig()[0] + " in a browser.")

    # Blink Green LED to show server is ready
    for _ in range(5):
        green_led.value(1)
        time.sleep(0.1)
        green_led.value(0)
        time.sleep(0.1)
    green_led.value(1) # Leave green on

    # Setup simple HTTP Server
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(('', 80))
    s.listen(1)

    while True:
        try:
            conn, addr = s.accept()
            print('Got a connection from %s' % str(addr))
            request_bytes = conn.recv(1024)
            
            try:
                req_str = request_bytes.decode('utf-8')
            except Exception:
                req_str = str(request_bytes)
                
            lines = req_str.replace('\r', '').split('\n')
            req_line = lines[0] if lines else ""
            
            path = '/'
            parts = req_line.split(' ')
            if len(parts) > 1:
                path = parts[1]
                
            if path == '/' or path == '/index.html':
                # Generate HTML list of CSV files
                try:
                    csv_files = [f for f in os.listdir("flight data collection") if f.endswith('.csv')]
                except Exception:
                    csv_files = []
                    
                html = "<html><head><title>Pico Flight Data</title><meta name='viewport' content='width=device-width, initial-scale=1'></head>"
                html += "<body style=\"font-family:sans-serif; padding:20px; text-align:center; background-image:url('/images.jpg'); background-size:cover; background-position:center; margin:0;\">"
                html += "<div style='background:rgba(0,0,0,0.7); padding:30px; border-radius:15px; display:inline-block; margin-top:20px;'>"
                html += "<h2 style='color:#ffffff; text-shadow:1px 1px 2px #000; margin-top:0;'> Rocket Flight Logs</h2>"
                if not csv_files:
                    html += "<p style='color:white;'>No flight data found.</p>"
                else:
                    for f in sorted(csv_files):
                        html += f"<a href='/{f}' style='display:block; margin:15px auto; padding:15px; background:rgba(0,123,255,0.9); color:white; text-decoration:none; border-radius:8px; width:250px; font-weight:bold; font-size:18px; box-shadow:0px 4px 6px rgba(0,0,0,0.6);'>{f}</a>"
                html += "</div></body></html>"
                
                conn.send('HTTP/1.1 200 OK\n')
                conn.send('Content-Type: text/html\n')
                conn.send('Connection: close\n\n')
                conn.send(html)
                
            elif path == '/images.jpg':
                # Serve the background image
                try:
                    os.stat('lib/images.jpg')
                    conn.send('HTTP/1.1 200 OK\n')
                    conn.send('Content-Type: image/jpeg\n')
                    conn.send('Connection: close\n\n')
                    
                    with open('lib/images.jpg', "rb") as f:
                        while True:
                            chunk = f.read(512)
                            if not chunk:
                                break
                            conn.sendall(chunk)
                except OSError:
                    conn.send('HTTP/1.1 404 Not Found\n\n')
                
            elif path.endswith('.csv'):
                # Serve the requested CSV file
                filename = path.strip('/')
                filepath = "flight data collection/" + filename
                try:
                    os.stat(filepath) # Check if file exists
                    conn.send('HTTP/1.1 200 OK\n')
                    conn.send('Content-Type: text/csv\n')
                    conn.send(f'Content-Disposition: attachment; filename="{filename}"\n')
                    conn.send('Connection: close\n\n')
                    
                    with open(filepath, "r") as f:
                        while True:
                            chunk = f.read(512)
                            if not chunk:
                                break
                            conn.sendall(chunk)
                    print(f"{filename} successfully sent!")
                except OSError:
                    conn.send('HTTP/1.1 404 Not Found\n')
                    conn.send('Connection: close\n\n')
                    conn.send('File not found.')
            else:
                conn.send('HTTP/1.1 404 Not Found\n')
                conn.send('Connection: close\n\n')
                conn.send('Not found.')
                
            conn.close()
        except OSError as e:
            try:
                conn.close()
            except:
                pass
            print('Connection closed due to error:', e)

except Exception as e:
    print("Failed to start Wi-Fi AP or Server:", e)
    red_led.value(1)