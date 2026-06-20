import struct

import time

def init_mpu6050(i2c, addr=0x68):
    """Wakes up the MPU6050 by writing to the Power Management register."""
    # Write 0 to PWR_MGMT_1 register (0x6B) to wake up the sensor
    for attempt in range(5):
        try:
            # Use direct writeto instead of writeto_mem for better compatibility
            i2c.writeto(addr, bytearray([0x6B, 0x00]))
            return  # Success
        except OSError as e:
            if attempt == 4:
                raise e
            time.sleep(0.1)

def get_mpu6050_data(i2c, addr=0x68):
    """Reads accelerometer data and returns it scaled to Gs."""
    # Read 6 bytes of accelerometer data starting from ACCEL_XOUT_H (0x3B)
    data = None
    for attempt in range(5):
        try:
            i2c.writeto(addr, bytearray([0x3B]))
            data = i2c.readfrom(addr, 6)
            break
        except OSError as e:
            if attempt == 4:
                raise e
            time.sleep(0.05)
    
    # Unpack as signed 16-bit big-endian integers
    ax, ay, az = struct.unpack(">hhh", data)
    
    # Convert raw data to Gs (Default full scale range is +/- 2g = 16384 LSB/g)
    accel_x = ax / 16384.0
    accel_y = ay / 16384.0
    accel_z = az / 16384.0
    
    return {
        'accel': {
            'x': accel_x,
            'y': accel_y,
            'z': accel_z
        }
    }