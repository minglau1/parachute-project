from ustruct import unpack

class BMP280:
    def __init__(self, i2c, addr=0x76):
        self.i2c = i2c
        self.addr = addr
        # Read factory calibration data (24 bytes)
        self.tb = unpack('<HhhHhhhhhhhh', self.i2c.readfrom_mem(self.addr, 0x88, 24))
        self.i2c.writeto_mem(self.addr, 0xF4, b'\x2F') 
        self.i2c.writeto_mem(self.addr, 0xF5, b'\x0C') 

    def read_data(self):
        data = self.i2c.readfrom_mem(self.addr, 0xF7, 6)
        up = (data[0] << 12) | (data[1] << 4) | (data[2] >> 4)
        ut = (data[3] << 12) | (data[4] << 4) | (data[5] >> 4)

        v1 = ((ut / 16384.0) - (self.tb[0] / 1024.0)) * self.tb[1]
        v2 = (((ut / 131072.0) - (self.tb[0] / 8192.0)) * ((ut / 131072.0) - (self.tb[0] / 8192.0))) * self.tb[2]
        t_fine = v1 + v2
        temp_c = t_fine / 5120.0

        v1 = (t_fine / 2.0) - 64000.0
        v2 = v1 * v1 * self.tb[8] / 32768.0
        v2 = v2 + v1 * self.tb[7] * 2.0
        v2 = (v2 / 4.0) + (self.tb[6] * 65536.0)
        v1 = (self.tb[5] * v1 * v1 / 524288.0 + self.tb[4] * v1) / 524288.0
        v1 = (1.0 + v1 / 32768.0) * self.tb[3]
        
        if v1 == 0:
            return temp_c, 0 
            
        p = 1048576.0 - up
        p = ((p - v2 / 4096.0) * 6250.0) / v1
        v1 = self.tb[11] * p * p / 2147483648.0
        v2 = p * self.tb[10] / 32768.0
        pressure_pa = p + (v1 + v2 + self.tb[9]) / 16.0

        return temp_c, pressure_pa

    def read_altitude(self, sea_level_pressure=101325.0):
        # Read the current pressure and calculate altitude
        temp_c, pressure_pa = self.read_data()
        altitude = 44330.0 * (1.0 - (pressure_pa / sea_level_pressure) ** 0.1903)
        return altitude