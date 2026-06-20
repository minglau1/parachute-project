import time
import struct

class BMP280:
    def __init__(self, i2c, addr=None):
        self.i2c = i2c
        
        # Auto-detect I2C address if not provided
        if addr is None:
            devices = i2c.scan()
            if 0x76 in devices:
                self.addr = 0x76
            elif 0x77 in devices:
                self.addr = 0x77
            else:
                raise RuntimeError("BMP280 not found on I2C bus!")
        else:
            self.addr = addr
            
        self._t_fine = 0
        
        # Read factory calibration data from registers 0x88 to 0xA1 (24 bytes)
        calib = self.i2c.readfrom_mem(self.addr, 0x88, 24)
        
        # Unpack calibration coefficients
        self.T1, self.T2, self.T3, self.P1, self.P2, self.P3, self.P4, self.P5, self.P6, self.P7, self.P8, self.P9 = struct.unpack("<HhhHhhhhhhhh", calib)
        
        self.init_sensor()

    def init_sensor(self):
        """Initializes the sensor registers. Call this at boot or if sensor resets."""
        # Turn on the sensor: Normal mode, 16x oversampling for Pressure, 2x for Temp
        self.i2c.writeto_mem(self.addr, 0xF4, b'\x57') 
        # Config: 0.5ms standby time (fast updates), IIR filter coefficient 16 (smooths data)
        self.i2c.writeto_mem(self.addr, 0xF5, b'\x10') 
        time.sleep(0.1)

    def read_data(self):
        """Reads raw data, applies compensation, and returns (temp_C, pressure_Pa)."""
        # Read raw temp and pressure from 0xF7 to 0xFC
        try:
            data = self.i2c.readfrom_mem(self.addr, 0xF7, 6)
        except OSError:
            self.init_sensor()
            return None, None # Return None to indicate invalid reading
            
        # If the sensor lost power and reset to sleep mode, it may return zeros, 0xFF, or 0x800000 (factory default)
        if data in (b'\x00\x00\x00\x00\x00\x00', b'\xff\xff\xff\xff\xff\xff', b'\x80\x00\x00\x80\x00\x00'):
            self.init_sensor()
            return None, None
            
        raw_p = (data[0] << 12) | (data[1] << 4) | (data[2] >> 4)
        raw_t = (data[3] << 12) | (data[4] << 4) | (data[5] >> 4)
        
        # --- Temperature Compensation ---
        var1 = ((raw_t / 16384.0) - (self.T1 / 1024.0)) * self.T2
        var2 = (((raw_t / 131072.0) - (self.T1 / 8192.0)) * ((raw_t / 131072.0) - (self.T1 / 8192.0))) * self.T3
        self._t_fine = var1 + var2
        temp = (var1 + var2) / 5120.0
        
        # --- Pressure Compensation ---
        var1 = (self._t_fine / 2.0) - 64000.0
        var2 = var1 * var1 * (self.P6 / 32768.0)
        var2 = var2 + var1 * (self.P5 * 2.0)
        var2 = (var2 / 4.0) + (self.P4 * 65536.0)
        var1 = (self.P3 * var1 * var1 / 524288.0 + self.P2 * var1) / 524288.0
        var1 = (1.0 + var1 / 32768.0) * self.P1
        
        if var1 == 0:
            pressure = 0 # Avoid divide by zero
        else:
            p = 1048576.0 - raw_p
            p = ((p - (var2 / 4096.0)) * 6250.0) / var1
            var1 = self.P9 * p * p / 2147483648.0
            var2 = p * self.P8 / 32768.0
            pressure = p + (var1 + var2 + self.P7) / 16.0
            
        return temp, pressure