import machine
import time
import gc
import network
import socket
import os
from mpu6050.mpu6050 import init_mpu6050, get_mpu6050_data
from bmp280.bmp280 import BMP280
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
        altimeter = BMP280(i2c)
        bmp_ok = True
    except Exception as e:
        print("ERROR DETECTED: BMP280 failed to initialize.")
        
    if mpu_ok and bmp_ok:
        print("All components initialized successfully!")
        break # Exit the loop, sensors are ready!
    else:
        print("Retrying in 2 seconds...")
        time.sleep(2)

# Set initial servo state to LOCKED (holding the rubber band)
parachute_servo.move(0)
print("Servo Locked. Parachute Secured.")
print("Waiting 2 seconds for power to stabilize after servo movement...")
time.sleep(2.0)

print("Warming up sensors and calibrating ground baseline...")
ground_alt_sum = 0.0
valid_readings = 0
for _ in range(60): # Loop over 6 seconds to flush IIR filter and get solid baseline
    try:
        altimeter.read_data()
        alt = altimeter.read_altitude()
        if alt != 0.0:
            ground_alt_sum += alt
            valid_readings += 1
    except Exception:
        pass
    time.sleep(0.1)

if valid_readings == 0:
    print("CRITICAL ERROR: Failed to get a valid ground baseline! Please check sensor connections and restart.")
    while True:
        red_led.value(not red_led.value())
        time.sleep(0.2)

ground_zero_altitude = ground_alt_sum / valid_readings
print(f"Sensors stabilized! Ground Zero Baseline: {ground_zero_altitude:.2f}m")

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

# STATE MACHINE VARIABLES
LAUNCH_G_THRESHOLD = 2.0 # Minimum G-force spike to detect liftoff
has_launched = False     # False = On pad, True = In flight

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
        f.write("Time(s),R.Altitude(m),G-Force(G),Accel_X,Accel_Y,Accel_Z,Temp(C),Event\n")
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
            if temp is None:
                temp = 0.0
            
            # Use filtered altitude and subtract ground baseline for true relative altitude
            current_altitude = altimeter.read_altitude(SEA_LEVEL_PRESSURE) - ground_zero_altitude
            
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
            # 5. PARACHUTE DEPLOYMENT LOGIC (State Machine)
            # ==========================================
            # State 0: Detect Launch (Engine Fire)
            if not has_launched:
                if total_g > LAUNCH_G_THRESHOLD or current_altitude > 5.0:
                    has_launched = True
                    print(f"\n!!! LIFTOFF DETECTED @ {elapsed_time:.2f}s !!!")
                    event_log += "LIFTOFF! "

            # State 1: Active Flight (Looking for Apogee)
            if has_launched:
                is_falling = current_altitude < (max_altitude - FALL_DISTANCE)
                is_weightless = total_g < FREEFALL_THRESHOLD

                # Conditions of the rocket
                if is_falling: 
                    print("Trigger: Altitude Drop")
                    event_log += "Altitude Drop "
                if is_weightless: 
                    print("Trigger: Freefall G-Force")
                    event_log += "Freefall "

                # Conditions of the apogee (Strict AND gate)
                if is_falling and is_weightless:
                    apogee_detect_count += 1
                    print(f"\n!!! APOGEE DETECTED ({apogee_detect_count}/3) !!!")
                    event_log += f"| APOGEE ({apogee_detect_count}/3) "
        
                    if apogee_detect_count >= 2:
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

            # --- FALLBACK: SAFETY TIMEOUT ---
            if elapsed_time > 120:
                print("\n!!! SAFETY TIMEOUT REACHED (120s) !!!")
                event_log += "| TIMEOUT DEPLOY!"
                parachute_servo.move(90) # Deploy parachute for safety
                green_led.value(0)
                red_led.value(1)
                flight_data.append((elapsed_time, current_altitude, total_g, accel_x, accel_y, accel_z, temp, event_log.strip()))
                time.sleep(1)
                break
    
            # Store data for collection
            flight_data.append((elapsed_time, current_altitude, total_g, accel_x, accel_y, accel_z, temp, event_log.strip()))
            
            # Memory Leak Fix: Save in batches to ensure infinite data without crashing RAM
            if len(flight_data) >= MAX_DATA_POINTS:
                save_flight_data_chunk(flight_data)
                flight_data = []
                gc.collect() # Instantly clear the old list from RAM
                
            print(f"Time: {elapsed_time:.2f}s | R.Alt: {current_altitude:.2f}m (Max: {max_altitude:.2f}m) | G-Force: {total_g:.2f}G")
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
    ap.active(False)
    time.sleep(0.5)
    ap.active(True)
    
    try:
        ap.config(pm=0) # Disable Wi-Fi power management to prevent connection drops!
    except:
        pass

    # Different MicroPython versions use either ssid or essid. Try ssid first.
    try:
        ap.config(ssid='Pico_Rocket', password='flightdata123', channel=6)
    except:
        try:
            ap.config(essid='Pico_Rocket', password='flightdata123', channel=6)
        except:
            pass

    timeout = 20
    while ap.active() == False and timeout > 0:
        time.sleep(0.5)
        timeout -= 1
    if not ap.active():
        print('Wi-Fi chip wedged! Forcing hard reset...')
        import machine
        machine.reset()

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
    s.listen(5) # Increased backlog to handle multiple requests smoother

    while True:
        gc.collect() # Free memory before each request to prevent crashes
        try:
            conn, addr = s.accept()
            conn.settimeout(5.0) # Prevent server from hanging on inactive clients
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
                    
                html = "<html><head><title>Pico Flight Data</title><meta name='viewport' content='width=device-width, initial-scale=1'>"
                html += "<script>"
                html += "function confirmDelete() { if(confirm('Are you sure you want to delete ALL flight logs? This cannot be undone.')) { window.location.href = '/delete_all'; } }"
                html += "function confirmRestart() { if(confirm('Are you sure you want to restart the rocket and rearm the parachute?')) { fetch('/restart'); document.body.innerHTML='<div style=\"background:#333; color:white; text-align:center; padding:50px; font-family:sans-serif; height:100vh;\"><h2>Rocket is Armed!</h2><p>The system is restarting. Wi-Fi will turn OFF to save power.</p><p>It will turn back on automatically after the flight.</p></div>'; } }"
                html += "</script>"
                html += "</head>"
                html += "<body style=\"font-family:sans-serif; padding:20px; text-align:center; background-image:url('/images.jpg'); background-size:cover; background-position:center; margin:0;\">"
                html += "<div style='background:rgba(0,0,0,0.7); padding:30px; border-radius:15px; display:inline-block; margin-top:20px;'>"
                html += "<h2 style='color:#ffffff; text-shadow:1px 1px 2px #000; margin-top:0;'> Rocket Flight Logs</h2>"
                if not csv_files:
                    html += "<p style='color:white;'>No flight data found.</p>"
                else:
                    for f in sorted(csv_files):
                        html += f"<a href='/{f}' style='display:block; margin:15px auto; padding:15px; background:rgba(0,123,255,0.9); color:white; text-decoration:none; border-radius:8px; width:250px; font-weight:bold; font-size:18px; box-shadow:0px 4px 6px rgba(0,0,0,0.6);'>{f}</a>"
                    
                html += "<hr style='border-color:rgba(255,255,255,0.3); margin: 25px 0;'/>"
                html += "<button onclick='confirmRestart()' style='display:block; margin:0 auto 15px auto; padding:15px; background:rgba(40,167,69,0.9); color:white; border:none; border-radius:8px; width:250px; font-weight:bold; font-size:18px; box-shadow:0px 4px 6px rgba(0,0,0,0.6); cursor:pointer;'>Restart & Rearm</button>"
                if csv_files:
                    html += "<button onclick='confirmDelete()' style='display:block; margin:0 auto; padding:15px; background:rgba(220,53,69,0.9); color:white; border:none; border-radius:8px; width:250px; font-weight:bold; font-size:18px; box-shadow:0px 4px 6px rgba(0,0,0,0.6); cursor:pointer;'>Delete All Logs</button>"
                html += "</div></body></html>"
                
                conn.sendall(b'HTTP/1.1 200 OK\r\n')
                conn.sendall(b'Content-Type: text/html\r\n')
                conn.sendall(b'Connection: close\r\n\r\n')
                conn.sendall(html.encode('utf-8'))
                
            elif path == '/delete_all':
                try:
                    for f in os.listdir("flight data collection"):
                        if f.endswith('.csv'):
                            os.remove("flight data collection/" + f)
                    
                    html = "<html><head><meta http-equiv='refresh' content='2;url=/'></head><body style='background:#333; color:white; text-align:center; padding:50px; font-family:sans-serif;'><h2>All logs deleted successfully!</h2><p>Redirecting back...</p></body></html>"
                    conn.sendall(b'HTTP/1.1 200 OK\r\n')
                    conn.sendall(b'Content-Type: text/html\r\n')
                    conn.sendall(b'Connection: close\r\n\r\n')
                    conn.sendall(html.encode('utf-8'))
                except Exception as e:
                    conn.sendall(b'HTTP/1.1 500 Internal Server Error\r\n\r\n')
                    conn.sendall(f'Error deleting files: {e}'.encode('utf-8'))
                
            elif path == '/restart':
                html = "<html><head></head><body style='background:#333; color:white; text-align:center; padding:50px; font-family:sans-serif;'><h2>Rocket is Armed!</h2><p>The system has rebooted and is now calibrating. The Wi-Fi network will now turn OFF to save power.</p><p>It will turn back on automatically after the flight is completed.</p></body></html>"
                conn.sendall(b'HTTP/1.1 200 OK\r\n')
                conn.sendall(b'Content-Type: text/html\r\n')
                conn.sendall(b'Connection: close\r\n\r\n')
                conn.sendall(html.encode('utf-8'))
                conn.close()
                import machine
                machine.reset()
                
            elif path == '/images.jpg':
                # Serve the background image
                try:
                    os.stat('lib/images.jpg')
                    conn.sendall(b'HTTP/1.1 200 OK\r\n')
                    conn.sendall(b'Content-Type: image/jpeg\r\n')
                    conn.sendall(b'Connection: close\r\n\r\n')
                    
                    with open('lib/images.jpg', "rb") as f:
                        while True:
                            chunk = f.read(512)
                            if not chunk:
                                break
                            conn.sendall(chunk)
                except OSError:
                    conn.sendall(b'HTTP/1.1 404 Not Found\r\n\r\n')
                
            elif path.endswith('.csv'):
                # Serve the requested CSV file
                filename = path.strip('/')
                filepath = "flight data collection/" + filename
                try:
                    os.stat(filepath) # Check if file exists
                    conn.sendall(b'HTTP/1.1 200 OK\r\n')
                    conn.sendall(b'Content-Type: text/csv\r\n')
                    conn.sendall(f'Content-Disposition: attachment; filename="{filename}"\r\n'.encode('utf-8'))
                    conn.sendall(b'Connection: close\r\n\r\n')
                    
                    with open(filepath, "rb") as f:
                        while True:
                            chunk = f.read(512)
                            if not chunk:
                                break
                            conn.sendall(chunk)
                    print(f"{filename} successfully sent!")
                except OSError:
                    conn.sendall(b'HTTP/1.1 404 Not Found\r\n')
                    conn.sendall(b'Connection: close\r\n\r\n')
                    conn.sendall(b'File not found.')
            else:
                conn.sendall(b'HTTP/1.1 404 Not Found\r\n')
                conn.sendall(b'Connection: close\r\n\r\n')
                conn.sendall(b'Not found.')
                
            conn.close()
        except OSError as e:
            try:
                conn.close()
            except:
                pass
            print('Connection closed due to error:', e)

except Exception as e:
    print("Failed to start Wi-Fi AP or Server:", e)
    red_led.value(1), 