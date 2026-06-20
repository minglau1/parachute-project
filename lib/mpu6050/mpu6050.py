import time

def init_mpu6050(i2c, addr=0x68):
    # Wake up the MPU6050 by writing 0 to the power management register
    try:
        i2c.writeto_mem(addr, 0x6B, b'\x00')
        time.sleep(0.1)
    except OSError:
        print("Error: Could not find MPU6050 at address", hex(addr))

def get_mpu6050_data(i2c, addr=0x68):
    # Read 14 bytes starting from register 0x3B (Accel, Temp, Gyro)
    data = i2c.readfrom_mem(addr, 0x3B, 14)
    
    # Unpack the bytes into integers
    ax = int.from_bytes(data[0:2], 'big')
    ay = int.from_bytes(data[2:4], 'big')
    az = int.from_bytes(data[4:6], 'big')
    
    gx = int.from_bytes(data[8:10], 'big')
    gy = int.from_bytes(data[10:12], 'big')
    gz = int.from_bytes(data[12:14], 'big')
    
    # Handle two's complement helper function
    def to_signed(val):
        return val - 65536 if val > 32767 else val

    ax, ay, az = to_signed(ax), to_signed(ay), to_signed(az)
    gx, gy, gz = to_signed(gx), to_signed(gy), to_signed(gz)
    
    # Convert raw accel to G-force (scale +/- 2g = 16384 LSB/g)
    accel_x = ax / 16384.0
    accel_y = ay / 16384.0
    accel_z = az / 16384.0
    total_g = (accel_x**2 + accel_y**2 + accel_z**2)**0.5
    
    # Convert raw gyro to deg/sec (scale +/- 250 dps = 131 LSB/dps)
    gyro_x = gx / 131.0
    gyro_y = gy / 131.0
    gyro_z = gz / 131.0
    
    return {
        'accel': {'x': accel_x, 'y': accel_y, 'z': accel_z},
        'gyro': {'x': gyro_x, 'y': gyro_y, 'z': gyro_z},
        'total_g': total_g
    }