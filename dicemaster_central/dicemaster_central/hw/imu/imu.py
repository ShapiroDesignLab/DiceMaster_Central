"""
U-M Shapiro Design Lab
Daniel Hou @2024
"""
import threading
import time
from math import sin, cos, sqrt, atan2, asin, pi
import numpy as np
import smbus2

class IMUHardware:
    """Base class for IMU hardware interface"""
    
    def __init__(self, i2c_bus=6, i2c_address=0x68):
        self.i2c_bus = i2c_bus
        self.i2c_address = i2c_address
        self.bus = None
        
        # MPU6050 register addresses
        self.PWR_MGMT_1 = 0x6B
        self.SMPLRT_DIV = 0x19
        self.CONFIG = 0x1A
        self.GYRO_CONFIG = 0x1B
        self.ACCEL_CONFIG = 0x1C
        self.ACCEL_XOUT_H = 0x3B
        self.ACCEL_YOUT_H = 0x3D
        self.ACCEL_ZOUT_H = 0x3F
        self.TEMP_OUT_H = 0x41
        self.GYRO_XOUT_H = 0x43
        self.GYRO_YOUT_H = 0x45
        self.GYRO_ZOUT_H = 0x47
        
        # Scaling factors
        self.accel_scale = 16384.0  # ±2g range
        self.gyro_scale = 131.0     # ±250°/s range
        
        self._initialize_imu()
    
    def _initialize_imu(self):
        """Initialize I2C connection and configure MPU6050"""
        if not I2C_AVAILABLE:
            print("Warning: I2C not available, using dummy data")
            return
            
        try:
            self.bus = smbus2.SMBus(self.i2c_bus)
            
            # Wake up the MPU6050
            self.bus.write_byte_data(self.i2c_address, self.PWR_MGMT_1, 0)
            time.sleep(0.1)
            
            # Set sample rate to 1000Hz
            self.bus.write_byte_data(self.i2c_address, self.SMPLRT_DIV, 7)
            # Set accelerometer configuration (±2g)
            self.bus.write_byte_data(self.i2c_address, self.ACCEL_CONFIG, 0)
            # Set gyroscope configuration (±250°/s)
            self.bus.write_byte_data(self.i2c_address, self.GYRO_CONFIG, 0)
            # Set DLPF (Digital Low Pass Filter)
            self.bus.write_byte_data(self.i2c_address, self.CONFIG, 0)
            print(f"IMU initialized successfully on I2C bus {self.i2c_bus} at address 0x{self.i2c_address:02X}")
            
        except Exception as e:
            print(f"Error initializing IMU: {e}")
            self.bus = None
    
    def _read_raw_data(self, register):
        """Read raw 16-bit signed data from IMU register"""
        if self.bus is None:
            return 0
            
        try:
            high = self.bus.read_byte_data(self.i2c_address, register)
            low = self.bus.read_byte_data(self.i2c_address, register + 1)
            value = (high << 8) + low
            
            # Convert to signed 16-bit
            if value >= 32768:
                value = value - 65536
                
            return value
        except Exception as e:
            print(f"Error reading from register 0x{register:02X}: {e}")
            return 0
    
    def _poll_imu(self):
        """Read current IMU data and return as numpy array [ax, ay, az, gx, gy, gz]"""
        if self.bus is None:
            # Return dummy data if I2C not available
            return np.array([0.0, 0.0, -9.81, 0.0, 0.0, 0.0])
        
        try:
            # Read accelerometer data
            accel_x_raw = self._read_raw_data(self.ACCEL_XOUT_H)
            accel_y_raw = self._read_raw_data(self.ACCEL_YOUT_H)
            accel_z_raw = self._read_raw_data(self.ACCEL_ZOUT_H)
            
            # Read gyroscope data
            gyro_x_raw = self._read_raw_data(self.GYRO_XOUT_H)
            gyro_y_raw = self._read_raw_data(self.GYRO_YOUT_H)
            gyro_z_raw = self._read_raw_data(self.GYRO_ZOUT_H)
            
            # Convert to physical units
            accel_x = accel_x_raw / self.accel_scale * 9.81  # m/s²
            accel_y = accel_y_raw / self.accel_scale * 9.81
            accel_z = accel_z_raw / self.accel_scale * 9.81
            
            gyro_x = gyro_x_raw / self.gyro_scale * pi / 180  # rad/s
            gyro_y = gyro_y_raw / self.gyro_scale * pi / 180
            gyro_z = gyro_z_raw / self.gyro_scale * pi / 180
            
            return np.array([accel_x, accel_y, accel_z, gyro_x, gyro_y, gyro_z])
            
        except Exception as e:
            print(f"Error polling IMU: {e}")
            return np.array([0.0, 0.0, -9.81, 0.0, 0.0, 0.0])
    
    def get_imu_data(self):
        """Public method to get IMU data as numpy array [ax, ay, az, gx, gy, gz]"""
        return self._poll_imu()
    
    def get_temperature(self):
        """Get temperature reading in Celsius"""
        if self.bus is None:
            return 25.0
            
        try:
            temp_raw = self._read_raw_data(self.TEMP_OUT_H)
            return temp_raw / 340.0 + 36.53  # °C
        except Exception as e:
            print(f"Error reading temperature: {e}")
            return 25.0
    
    def close(self):
        """Close I2C connection"""
        if self.bus is not None:
            self.bus.close()
            self.bus = None
