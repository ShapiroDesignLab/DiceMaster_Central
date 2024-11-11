"""
U-M Shapiro Design Lab
Daniel Hou @2024

This module hosts all drivers for sensors and interfaces with strategies. 
"""
from abc import ABC, abstractmethod
import threading
import time
from math import atan, degrees

import smbus2 as smbus
# from smbus2 import I2C, Pin
import numpy as np

from .config import IMU_POLLING_RATE, IMU_HIST_SIZE
from .utils import RingBufferNP



class BaseSensor(ABC):
    def __init__(self):
        # Calibration
        self.lock = threading.Lock()
        self.calibrated = False
        self.calibration_thread = threading.Thread(target=self.__calibrate)

        self.running = False
        self.poll_thread = threading.Thread(target=self.__poll)

    @abstractmethod
    def __calibrate(self):
        pass

    def start_calibrate(self):
        self.calibration_thread.start()

    def is_done_calibration(self):
        if self.calibrated is False:        # If still calibrating
            return False
        if self.running:                    # If running already
            return True
        self.calibration_thread.join()      # Otherwise, just finished calibration
        self.start_poll()
        return True

    @abstractmethod
    def __poll(self):
        pass

    def start_poll(self):
        """Start the polling thread"""
        self.running = True
        self.poll_thread.start()

    def stop(self):
        """stop the """
        try:
            self.calibration_thread.join()
        finally:
            self.poll_thread.join()
        self.running = False

    def __del__(self):
        self.stop()

    

class KalmanFilter:
    def __init__(self, KalmanState, KalmanUncertainity):
        self.KalmanState = KalmanState
        self.KalmanUncertainity = KalmanUncertainity

    def update(self, Gyro, Acc, dt):
        self.KalmanState = self.KalmanState + dt*Gyro
        self.KalmanUncertainity = self.KalmanUncertainity + dt*dt*4*4
        KalmanGain = self.KalmanUncertainity * \
            (1/1*self.KalmanUncertainity + 3*3)
        self.KalmanState = self.KalmanState + KalmanGain*(Acc-self.KalmanState)
        self.KalmanUncertainity = (1-KalmanGain)*self.KalmanUncertainity
        return self.KalmanState
    

"""
CREDIT:https://github.com/jk-aero/MPU6050/
"""
class MPU6050(BaseSensor):
    def __init__(self, busid, SDA, SCL, led=25):
        self.PWR_MGMT_1 = 0x6B
        self.SMPLRT_DIV = 0x19
        self.CONFIG = 0x1A
        self.GYRO_CONFIG = 0x1B
        self.ACCEL_YOUT_H = 0x3D
        self.ACCEL_ZOUT_H = 0x3F
        self.GYRO_XOUT_H = 0x43
        self.GYRO_YOUT_H = 0x45
        self.GYRO_ZOUT_H = 0x47
        self.mpu6050_addr = 0x68

        self.z_gyro_bias = 0
        self.y_gyro_bias = 0
        self.z_gyro_bias = 0

        self.x_acc_bias = 0
        self.y_acc_bias = 0

        self.KalmanStateX = 0
        self.KalmanUncertainityX = 0
        self.pitchAngle = KalmanFilter(
            self.KalmanStateX, self.KalmanUncertainityX)

        self.KalmanStateY = 0
        self.KalmanUncertainityY = 0
        self.rollAngle = KalmanFilter(
            self.KalmanStateY, self.KalmanUncertainityY)

        self.LED = Pin(led, Pin.OUT)

        self.i2c = I2C(busid, sda=Pin(SDA), scl=Pin(SCL))
        self.i2c.writeto_mem(self.mpu6050_addr, self.PWR_MGMT_1, b'\x01')

    def _combine_register_values_(self, h, l):
        if not h[0] & 0x80:
            return h[0] << 8 | l[0]
        return -((h[0] ^ 255) << 8) | (l[0] ^ 255) + 1

    def _read_raw_data_(self, addr):
        high = self.i2c.readfrom_mem(self.mpu6050_addr, addr, 1)
        low = self.i2c.readfrom_mem(self.mpu6050_addr, addr+1, 1)
        val = self._combine_register_values_(high, low)
        return (val)

    def read_acc(self):
        return (self._read_raw_data_(0x3B)/16384, 
                self._read_raw_data_(0x3D)/16384, 
                self._read_raw_data_(0x3F)/16384
            )

    def read_gyro(self):
        return (self._read_raw_data_(0x43)/131-1.01747575, 
                self._read_raw_data_(0x45)/131+1.31162225, 
                self._read_raw_data_(0x47)/131-1.91204825
            )

    def blink(self, t):
        for i in range(6):
            self.LED.toggle()
            time.sleep(t)

    def calculate_acc_angles(self):
        x, y, z = [], [], []
        for i in range(3):
            acc_data = self.read_acc()
            x.append(acc_data[0])
            y.append(acc_data[1])
            z.append(acc_data[2])
        ax = sum(x)/3
        ay = sum(y)/3
        az = sum(z)/3
        x_angles = degrees(atan(ay/((ax**2 + az**2)**0.5)))
        y_angles = degrees(atan(ax/((ay**2 + az**2)**0.5)))-5.18
        return (x_angles-self.x_acc_bias, y_angles-self.y_acc_bias)

    def callibrate_gyro(self):
        GX_bias, GY_bias, GZ_bias = [], [], []
        for i in range(100):
            g_x, g_y, g_z = self.read_gyro()
            GX_bias.append(g_x)
            GY_bias.append(g_y)
            GZ_bias.append(g_z)
        self.z_gyro_bias = sum(GX_bias)/100
        self.y_gyro_bias = sum(GY_bias)/100
        self.z_gyro_bias = sum(GZ_bias)/100
        del GX_bias, GY_bias, GZ_bias
        self.blink(0.1)
        time.sleep(2)

    def callibrate_acc(self):
        lstX, lstY = [], []
        for i in range(100):
            a_x, a_y, a_z = self.read_acc()
            x_angle, y_angle = self.calculate_acc_angles()
            lstX.append(x_angle)
            lstY.append(y_angle)

        self.x_acc_bias = (sum(lstX)/100)
        self.y_acc_bias = (sum(lstY)/100)
        del lstX, lstY
        self.blink(0.1)
        time.sleep(2)

    def return_angles(self):
        start = time.time_ns()*1000
        gX, gY = self.read_gyro()[:-1]
        Acc_X, Acc_Y = self.calculate_acc_angles()
        dt = (time.time_ns()*1000 - start)/10**6
        return self.pitchAngle.update(gY, Acc_Y, dt), self.rollAngle.update(gX, Acc_X, dt), dt
    
class MPU60502(BaseSensor):
    """MPU 6050 Wrapper for Dice"""
    def __init__(self, bus=1, address=0x68, calibration_duration=3):
        # Set Args
        self.bus = smbus.SMBus(bus)
        self.address = address
        self.calib_duration_seconds = calibration_duration
        self.polling_rate = IMU_POLLING_RATE         # Poll sensor at 200Hz
        self.sleep_time = 1/self.polling_rate
        self.initial_orientation = [1, 0, 0, 0]  # Initial quaternion

        # History Buffers
        self.quat_hist = RingBufferNP(shape=(IMU_HIST_SIZE, 4))
        self.acc_hist = RingBufferNP(shape=(IMU_HIST_SIZE, 3))
        self.gyro_hist = RingBufferNP(shape=(IMU_HIST_SIZE, 3))

        # Bias Terms
        self.acc_bias = np.zeros(3, dtype=np.float32)
        self.gyro_bias = np.zeros(3, dtype=np.float32)

        # Wake up IMU
        self.bus.write_byte_data(self.address, 0x6B, 0)  # Wake up the MPU-6050
        # Configure accelerometer and gyroscope settings here if necessary

    def __calibrate(self):
        """
        Calibrate IMU: collect raw data, assuming no movement, then records the average of raw values as bias
        """
        start_time = time.time()
        calib_acc_buffer = RingBufferNP((self.calib_duration_seconds*self.polling_rate, 3))
        calib_gyro_buffer = RingBufferNP((self.calib_duration_seconds*self.polling_rate, 3))
        while time.time() - start_time <= self.calib_duration_seconds:
            acc_data, gyro_data, _ = self.__poll_cycle()
            calib_acc_buffer.push_front(acc_data)
            calib_gyro_buffer.push_front(gyro_data)
            time.sleep(1/self.polling_rate)
        with self.lock:
            self.acc_bias = np.average(calib_acc_buffer.get_items(), axis=0)
            self.acc_bias = np.average(calib_acc_buffer.get_items(), axis=0)
        return

    def kalman_filter(self, accel, gyro):
        # Dummy implementation of Kalman filter to calculate quaternion
        # This should be replaced with actual Kalman filter code
        raise NotImplementedError()

    # READ WORKS
    def __poll(self):
        while True:
            self.__poll_cycle()
            time.sleep(self.sleep_time)

    def __poll_cycle(self):
        accel_data, gyro_data = self.__read_vals()
        with self.lock:
            accel_data = accel_data - self.acc_bias
            gyro_data = gyro_data - self.gyro_bias
        quaternion = self.kalman_filter(accel_data, gyro_data)
        with self.lock:
            self.quaternion = quaternion
            self.quat_hist.push_front(self.quaternion)
        return accel_data, gyro_data, quaternion

    def __read_vals(self):
        # Reads raw data from the MPU6050
        accel_x = self.__read_word_2c(0x3B)
        accel_y = self.__read_word_2c(0x3D)
        accel_z = self.__read_word_2c(0x3F)
        gyro_x = self.__read_word_2c(0x43)
        gyro_y = self.__read_word_2c(0x45)
        gyro_z = self.__read_word_2c(0x47)
        return np.array([accel_x, accel_y, accel_z]), np.array([gyro_x, gyro_y, gyro_z])

    def __read_word_2c(self, addr):
        high = self.bus.read_byte_data(self.address, addr)
        low = self.bus.read_byte_data(self.address, addr+1)
        val = (high << 8) + low
        if val >= 0x8000:
            return -((65535 - val) + 1)
        else:
            return val


class SensorCollection(dict):
    """
    SensorCollection class stores all the sensors
    """
    def __init__(self):
        self["IMU"] = MPU6050()

        for sensor in self.values():
            sensor.start()
            sensor.calibrate()
        self.all_sensors_ready = False
        self.sensors_not_ready = list(self.values())

    def is_all_sensors_ready(self):
        """See whether all sensors are ready"""
        if self.all_sensors_ready:
            return True
        for sensor in self.sensors_not_ready:
            if sensor.is_done_calibration():
                self.sensors_not_ready.remove(sensor)
        if len(self.sensors_not_ready) == 0:
            self.all_sensors_ready = True
        return self.all_sensors_ready

if __name__ == "__main__":
    print("Error, calling module comm directly!")