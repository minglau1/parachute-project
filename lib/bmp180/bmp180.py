import time
from ustruct import unpack

class BMP180:
    def __init__(self, i2c, address=0x77):
        self.i2c = i2c
        self.address = address
        self.oversample = 3 # Ultra high resolution
        
        # Read 22 bytes of calibration data from EEPROM
        b = self.i2c.readfrom_mem(self.address, 0xAA, 22)
        # Unpack: 3 signed short, 3 unsigned short, 5 signed short
        self.cal = unpack(">hhhHHHhhhhh", b)

    def read_raw_temp(self):
        self.i2c.writeto_mem(self.address, 0xF4, bytearray([0x2E]))
        time.sleep_ms(5)
        b = self.i2c.readfrom_mem(self.address, 0xF6, 2)
        return unpack(">h", b)[0]

    def read_raw_pressure(self):
        self.i2c.writeto_mem(self.address, 0xF4, bytearray([0x34 + (self.oversample << 6)]))
        time.sleep_ms(26) # wait for conversion
        b = self.i2c.readfrom_mem(self.address, 0xF6, 3)
        return ((b[0] << 16) + (b[1] << 8) + b[2]) >> (8 - self.oversample)

    def read_data(self):
        try:
            UT = self.read_raw_temp()
            UP = self.read_raw_pressure()
        except OSError:
            return None, None

        AC1, AC2, AC3, AC4, AC5, AC6, B1, B2, MB, MC, MD = self.cal

        # Temperature calculation
        X1 = ((UT - AC6) * AC5) >> 15
        X2 = (MC << 11) // (X1 + MD)
        B5 = X1 + X2
        T = ((B5 + 8) >> 4) / 10.0

        # Pressure calculation
        B6 = B5 - 4000
        X1 = (B2 * ((B6 * B6) >> 12)) >> 11
        X2 = (AC2 * B6) >> 11
        X3 = X1 + X2
        B3 = (((AC1 * 4 + X3) << self.oversample) + 2) >> 2
        X1 = (AC3 * B6) >> 13
        X2 = (B1 * ((B6 * B6) >> 12)) >> 16
        X3 = ((X1 + X2) + 2) >> 2
        B4 = (AC4 * (X3 + 32768)) >> 15
        B7 = (UP - B3) * (50000 >> self.oversample)
        if B7 < 0x80000000:
            p = (B7 * 2) // B4
        else:
            p = (B7 // B4) * 2
            
        X1 = (p >> 8) * (p >> 8)
        X1 = (X1 * 3038) >> 16
        X2 = (-7357 * p) >> 16
        P = p + ((X1 + X2 + 3791) >> 4)

        return T, float(P)

    def read_altitude(self, sea_level_pressure=101325.0):
        temp, pressure = self.read_data()
        if pressure is None:
            return 0.0
        # Calculate altitude from pressure
        altitude = 44330.0 * (1.0 - (pressure / sea_level_pressure) ** 0.1903)
        return altitude