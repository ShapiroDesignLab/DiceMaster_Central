"""
U-M Shapiro Design Lab
Daniel Hou @2024

This module hosts all drivers for sensors and interfaces with strategies. 
"""

import threading
import time
from math import sqrt

import smbus2 as smbus


class MPU6050:
    """MPU 6050 Wrapper for Dice"""
    def __init__(self, bus=1, address=0x68):
        self.bus = smbus.SMBus(bus)
        self.address = address
        self.polling_rate = 200         # Poll sensor at 200Hz
        self.initialize_sensor()

        self.lock = threading.Lock()
        self.quaternion = [1, 0, 0, 0]  # Initial quaternion

        self.running = True
        self.thread = threading.Thread(target=self.poll_sensor)
        self.thread.start()

    def __del__(self):
        self.stop()

    def initialize_sensor(self):
        self.bus.write_byte_data(self.address, 0x6B, 0)  # Wake up the MPU-6050
        # Configure accelerometer and gyroscope settings here if necessary

    def calibrate(self, duration_seconds=3):
        start_time = time.time()
        while time.time() - start_time <= duration_seconds:
            self.poll_sensor()

    def read_sensor_data(self):
        # Reads raw data from the MPU6050
        accel_x = self.read_word_2c(0x3B)
        accel_y = self.read_word_2c(0x3D)
        accel_z = self.read_word_2c(0x3F)
        gyro_x = self.read_word_2c(0x43)
        gyro_y = self.read_word_2c(0x45)
        gyro_z = self.read_word_2c(0x47)
        return accel_x, accel_y, accel_z, gyro_x, gyro_y, gyro_z

    def read_word_2c(self, addr):
        high = self.bus.read_byte_data(self.address, addr)
        low = self.bus.read_byte_data(self.address, addr+1)
        val = (high << 8) + low
        if val >= 0x8000:
            return -((65535 - val) + 1)
        else:
            return val

    def kalman_filter(self, accel, gyro):
        # Dummy implementation of Kalman filter to calculate quaternion
        # This should be replaced with actual Kalman filter code
        ax, ay, az, gx, gy, gz = accel + gyro
        qw = sqrt(1 + ax + ay + az) / 2
        qx = (ay - az) / (4 * qw)
        qy = (az - ax) / (4 * qw)
        qz = (ax - ay) / (4 * qw)
        return [qw, qx, qy, qz]


    # READ WORKS
    def poll_sensor(self):
        while self.running:
            accel_data = self.read_sensor_data()[:3]
            gyro_data = self.read_sensor_data()[3:]
            quaternion = self.kalman_filter(accel_data, gyro_data)

            with self.lock:
                self.quaternion = quaternion

            time.sleep(1/self.polling_rate)

    def get_quaternion(self):
        with self.lock:
            return self.quaternion
        
    def upper_screen(self):
        self
        
    def determine_motion(self):
        pass
        
    def is_shaken_left(self):
        pass

    def is_shaken_right(self):
        pass
    
    def is_rolled(self):
        pass
    
    def stop(self):
        self.running = False
        self.thread.join()


class MPU6050Dummy:
    def __init__(self, bus=1, address=0x68):
        self.bus = smbus.SMBus(bus)
        self.address = address
        self.initialize_sensor()

        self.lock = threading.Lock()
        self.quaternion = [1, 0, 0, 0]  # Initial quaternion

        self.running = True
        self.thread = threading.Thread(target=self.poll_sensor)
        self.thread.start()

    def __del__(self):
        self.stop()

    def initialize_sensor(self):
        self.bus.write_byte_data(self.address, 0x6B, 0)  # Wake up the MPU-6050
        # Configure accelerometer and gyroscope settings here if necessary

    def calibrate(self, duration_seconds=3):
        start_time = time.time()
        while time.time() - start_time <= duration_seconds:
            self.poll_sensor()

    def read_sensor_data(self):
        # Reads raw data from the MPU6050
        accel_x = self.read_word_2c(0x3B)
        accel_y = self.read_word_2c(0x3D)
        accel_z = self.read_word_2c(0x3F)
        gyro_x = self.read_word_2c(0x43)
        gyro_y = self.read_word_2c(0x45)
        gyro_z = self.read_word_2c(0x47)
        return accel_x, accel_y, accel_z, gyro_x, gyro_y, gyro_z

    def read_word_2c(self, addr):
        high = self.bus.read_byte_data(self.address, addr)
        low = self.bus.read_byte_data(self.address, addr+1)
        val = (high << 8) + low
        if val >= 0x8000:
            return -((65535 - val) + 1)
        else:
            return val

    def kalman_filter(self, accel, gyro):
        # Dummy implementation of Kalman filter to calculate quaternion
        # This should be replaced with actual Kalman filter code
        ax, ay, az, gx, gy, gz = accel + gyro
        qw = sqrt(1 + ax + ay + az) / 2
        qx = (ay - az) / (4 * qw)
        qy = (az - ax) / (4 * qw)
        qz = (ax - ay) / (4 * qw)
        return [qw, qx, qy, qz]

    def poll_sensor(self):
        while self.running:
            accel_data = self.read_sensor_data()[:3]
            gyro_data = self.read_sensor_data()[3:]
            quaternion = self.kalman_filter(accel_data, gyro_data)

            with self.lock:
                self.quaternion = quaternion

            time.sleep(0.01)  # Polling frequency

    def get_quaternion(self):
        with self.lock:
            return self.quaternion

    def stop(self):
        self.running = False
        self.thread.join()

# Example usage:
# mpu = MPU6050()
# time.sleep(2)
# print(mpu.get_quaternion())
# mpu.stop()
