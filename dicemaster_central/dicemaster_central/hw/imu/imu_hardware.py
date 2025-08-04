"""
U-M Shapiro Design Lab
Daniel Hou @2024

IMU Hardware Interface
Publishes raw IMU data to /imu/data_raw for Madgwick filter processing.
"""
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Imu
from std_msgs.msg import Header
from std_srvs.srv import Empty

import time
import numpy as np
import threading
import smbus2
import json
import os
from datetime import datetime
from pathlib import Path
from typing import List
from pydantic import BaseModel, ValidationError

from dicemaster_central.config import dice_config


class IMUCalibrationData(BaseModel):
    """Pydantic model for IMU calibration data validation"""
    timestamp: str
    accelerometer_bias: List[float]
    gyroscope_bias: List[float]
    sample_count: int
    calibration_duration: float
    
    class Config:
        # Allow extra fields for future compatibility
        extra = "ignore"
    
    def to_numpy(self):
        """Convert lists to numpy arrays for use in IMU node"""
        return {
            'acc_bias': np.array(self.accelerometer_bias),
            'gyro_bias': np.array(self.gyroscope_bias),
            'timestamp': self.timestamp,
            'sample_count': self.sample_count
        }

class IMUHardwareNode(Node):
    """IMU Hardware interface that publishes raw data for Madgwick filter"""
    
    def __init__(self, i2c_bus=6, i2c_address=0x68):
        super().__init__('imu_hardware')
        
        # Hardware parameters
        self.i2c_bus = i2c_bus
        self.i2c_address = i2c_address
        self.bus = None
        
        # Declare ROS parameters
        self.imu_config = dice_config.imu_config
        self.i2c_bus = self.imu_config.i2c_bus
        self.i2c_address = self.imu_config.i2c_address
        self.calibration_duration = self.imu_config.calibration_duration
        self.polling_rate = self.imu_config.polling_rate

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
        
        # Publisher for raw IMU data (for Madgwick filter)
        self.imu_raw_pub = self.create_publisher(Imu, '/imu/data_raw', 10)
        
        # Calibration service
        self.calibration_service = self.create_service(
            Empty,
            '/dice_hw/imu/calibrate',
            self.calibrate_service_callback
        )
        
        # Calibration state
        self.is_calibrated = False
        self.calibrating = False
        self.calib_samples = []
        self.calib_start_time = None
        
        # Sensor biases (set during calibration)
        self.acc_bias = np.zeros(3)
        self.gyro_bias = np.zeros(3)
        
        # Threading
        self.lock = threading.Lock()
        
        # Calibration directory setup
        self.calibration_dir = Path.home() / ".dicemaster" / "imu_calibration"
        self.calibration_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize hardware
        self._initialize_imu()
        
        # Load existing calibration or start auto-calibration
        self._load_or_start_calibration()
        
        # Publishing timer
        self.timer = self.create_timer(1.0/self.polling_rate, self.timer_callback)
        
        self.get_logger().info("IMU Hardware node initialized")
    
    def _load_or_start_calibration(self):
        """Load existing calibration or start automatic calibration"""
        calibration_data = self._load_latest_calibration()
        
        if calibration_data:
            # Load existing calibration
            data = calibration_data.to_numpy()
            self.acc_bias = data['acc_bias']
            self.gyro_bias = data['gyro_bias']
            self.is_calibrated = True
            
            self.get_logger().info(f"Loaded calibration from {calibration_data.timestamp}")
            self.get_logger().info(f"Accel bias: {self.acc_bias}")
            self.get_logger().info(f"Gyro bias: {self.gyro_bias}")
        else:
            # No valid calibration found, start automatic calibration
            self.get_logger().warn("No valid calibration found, starting automatic calibration")
            self.get_logger().warn("Keep IMU stationary for calibration (any orientation is fine)")
            
            # Start calibration automatically
            with self.lock:
                self.calibrating = True
                self.is_calibrated = False
                self.calib_start_time = None
    
    def _load_latest_calibration(self):
        """Load the latest valid calibration file"""
        try:
            # Get all JSON files in calibration directory
            json_files = list(self.calibration_dir.glob("*.json"))
            
            if not json_files:
                return None
            
            # Sort by modification time (newest first)
            json_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            
            # Try to load and validate each file until we find a valid one
            for json_file in json_files:
                try:
                    with open(json_file, 'r') as f:
                        data = json.load(f)
                    
                    # Validate using Pydantic model
                    calibration_data = IMUCalibrationData(**data)
                    
                    self.get_logger().info(f"Successfully loaded calibration from {json_file.name}")
                    return calibration_data
                    
                except (json.JSONDecodeError, ValidationError, FileNotFoundError) as e:
                    self.get_logger().warn(f"Invalid calibration file {json_file.name}: {e}")
                    continue
                except Exception as e:
                    self.get_logger().error(f"Error reading calibration file {json_file.name}: {e}")
                    continue
            
            self.get_logger().warn("No valid calibration files found")
            return None
            
        except Exception as e:
            self.get_logger().error(f"Error loading calibration files: {e}")
            return None
    
    def _save_calibration(self, acc_bias, gyro_bias, sample_count):
        """Save calibration data to JSON file"""
        try:
            # Clean up old files first (keep last 30)
            self._cleanup_old_calibrations()
            
            # Create calibration data
            timestamp = datetime.now().isoformat()
            calibration_data = IMUCalibrationData(
                timestamp=timestamp,
                accelerometer_bias=acc_bias.tolist(),
                gyroscope_bias=gyro_bias.tolist(),
                sample_count=sample_count,
                calibration_duration=self.calibration_duration
            )
            
            # Generate filename with timestamp
            filename = f"imu_calibration_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            filepath = self.calibration_dir / filename
            
            # Save to file
            with open(filepath, 'w') as f:
                json.dump(calibration_data.dict(), f, indent=2)
            
            self.get_logger().info(f"Calibration saved to {filename}")
            
        except Exception as e:
            self.get_logger().error(f"Error saving calibration: {e}")
    
    def _cleanup_old_calibrations(self):
        """Keep only the latest 30 calibration files"""
        try:
            json_files = list(self.calibration_dir.glob("*.json"))
            
            if len(json_files) <= 30:
                return
            
            # Sort by modification time (oldest first)
            json_files.sort(key=lambda x: x.stat().st_mtime)
            
            # Delete oldest files
            files_to_delete = json_files[:-30]  # Keep last 30
            
            for file_to_delete in files_to_delete:
                try:
                    file_to_delete.unlink()
                    self.get_logger().debug(f"Deleted old calibration file: {file_to_delete.name}")
                except Exception as e:
                    self.get_logger().warn(f"Failed to delete {file_to_delete.name}: {e}")
                    
        except Exception as e:
            self.get_logger().error(f"Error cleaning up calibration files: {e}")
    
    def _initialize_imu(self):
        """Initialize I2C connection and configure MPU6050"""
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
            
            self.get_logger().info(f"IMU initialized successfully on I2C bus {self.i2c_bus} at address 0x{self.i2c_address:02X}")
            
        except Exception as e:
            self.get_logger().error(f"Error initializing IMU: {e}")
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
        """Read current IMU data"""
        if self.bus is None:
            # Return dummy data if I2C not available
            accel = np.array([0.0, 0.0, 9.81])
            gyro = np.array([0.0, 0.0, 0.0])
            return accel, gyro, 25.0
        
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
            
            gyro_x = gyro_x_raw / self.gyro_scale * np.pi / 180  # rad/s
            gyro_y = gyro_y_raw / self.gyro_scale * np.pi / 180
            gyro_z = gyro_z_raw / self.gyro_scale * np.pi / 180
            
            accel = np.array([accel_x, accel_y, accel_z])
            gyro = np.array([gyro_x, gyro_y, gyro_z])
            
            # Read temperature
            temp_raw = self._read_raw_data(self.TEMP_OUT_H)
            temperature = temp_raw / 340.0 + 36.53  # °C
            
            return accel, gyro, temperature
            
        except Exception as e:
            self.get_logger().error(f"Error polling IMU: {e}")
            return np.array([0.0, 0.0, 9.81]), np.array([0.0, 0.0, 0.0]), 25.0
    
    def timer_callback(self):
        """Main timer callback - polls IMU and publishes data"""
        # Poll IMU data
        accel, gyro, _ = self._poll_imu()  # temperature not needed here
        
        with self.lock:
            # Apply calibration if available
            if self.is_calibrated:
                accel = accel - self.acc_bias
                gyro = gyro - self.gyro_bias
            
            # Handle calibration process
            if self.calibrating:
                self._handle_calibration(accel, gyro)
        
        # Publish raw IMU data (for Madgwick filter)
        self._publish_raw_imu(accel, gyro)
    
    def _publish_raw_imu(self, accel, gyro):
        """Publish raw IMU data in sensor_msgs/Imu format for Madgwick filter"""
        imu_msg = Imu()
        
        # Header
        imu_msg.header = Header()
        imu_msg.header.stamp = self.get_clock().now().to_msg()
        imu_msg.header.frame_id = "imu_link"
        
        # Linear acceleration
        imu_msg.linear_acceleration.x = float(accel[0])
        imu_msg.linear_acceleration.y = float(accel[1])
        imu_msg.linear_acceleration.z = float(accel[2])
        
        # Angular velocity
        imu_msg.angular_velocity.x = float(gyro[0])
        imu_msg.angular_velocity.y = float(gyro[1])
        imu_msg.angular_velocity.z = float(gyro[2])
        
        # Orientation is unknown for raw data
        imu_msg.orientation.w = 0.0
        imu_msg.orientation.x = 0.0
        imu_msg.orientation.y = 0.0
        imu_msg.orientation.z = 0.0
        
        # Covariance matrices (use -1 to indicate unknown)
        imu_msg.orientation_covariance[0] = -1.0
        imu_msg.angular_velocity_covariance[0] = 0.01  # Small variance for gyro
        imu_msg.linear_acceleration_covariance[0] = 0.1  # Small variance for accel
        
        # Publish
        self.imu_raw_pub.publish(imu_msg)
    
    def _handle_calibration(self, accel, gyro):
        """Handle calibration process with improved gravity compensation"""
        if self.calib_start_time is None:
            self.calib_start_time = time.time()
            self.calib_samples = []
            self.get_logger().info(f"Starting calibration - keep IMU still for {self.calibration_duration} seconds")
        
        elapsed = time.time() - self.calib_start_time
        
        if elapsed < self.calibration_duration:
            # Collect calibration samples
            self.calib_samples.append({
                'accel': accel.copy(),
                'gyro': gyro.copy()
            })
        else:
            # Calibration complete - compute biases
            if len(self.calib_samples) > 10:
                accels = np.array([s['accel'] for s in self.calib_samples])
                gyros = np.array([s['gyro'] for s in self.calib_samples])
                
                # Gyro bias is the mean (should be zero when still)
                self.gyro_bias = np.mean(gyros, axis=0)
                
                # Improved accelerometer bias calculation
                # Don't assume orientation - find gravity vector and compensate properly
                accel_mean = np.mean(accels, axis=0)
                
                # Calculate the magnitude of the mean acceleration
                gravity_magnitude = np.linalg.norm(accel_mean)
                
                # If the magnitude is close to 9.81, we can compute proper bias
                if abs(gravity_magnitude - 9.81) < 2.0:  # Allow some tolerance
                    # Calculate the unit vector in the direction of measured gravity
                    gravity_direction = accel_mean / gravity_magnitude
                    
                    # The bias is the difference between measured and expected gravity
                    expected_gravity = gravity_direction * 9.81
                    self.acc_bias = accel_mean - expected_gravity
                    
                    self.get_logger().info(f"Gravity magnitude: {gravity_magnitude:.2f} m/s²")
                    self.get_logger().info(f"Gravity direction: [{gravity_direction[0]:.3f}, {gravity_direction[1]:.3f}, {gravity_direction[2]:.3f}]")
                else:
                    # If gravity magnitude is way off, something might be wrong
                    self.get_logger().warn(f"Unexpected gravity magnitude: {gravity_magnitude:.2f} m/s² (expected ~9.81)")
                    # Still compute bias but warn user
                    self.acc_bias = accel_mean - (accel_mean / gravity_magnitude * 9.81)
                
                self.is_calibrated = True
                
                # Save calibration to file
                self._save_calibration(self.acc_bias, self.gyro_bias, len(self.calib_samples))
                
                self.get_logger().info(f"Calibration complete! Samples: {len(self.calib_samples)}")
                self.get_logger().info(f"Gyro bias: [{self.gyro_bias[0]:.4f}, {self.gyro_bias[1]:.4f}, {self.gyro_bias[2]:.4f}] rad/s")
                self.get_logger().info(f"Accel bias: [{self.acc_bias[0]:.4f}, {self.acc_bias[1]:.4f}, {self.acc_bias[2]:.4f}] m/s²")
            else:
                self.get_logger().warn("Not enough calibration samples collected")
            
            self.calibrating = False
            self.calib_start_time = None
            self.calib_samples = []
    
    def calibrate_service_callback(self, request, response):
        """Handle calibration service request - force new calibration"""
        _ = request  # unused parameter
        with self.lock:
            if self.calibrating:
                self.get_logger().warn("Calibration already in progress")
            else:
                self.calibrating = True
                self.is_calibrated = False
                self.calib_start_time = None
                self.get_logger().info("Manual calibration requested - keep IMU perfectly still!")
                self.get_logger().info("Calibration will be saved and replace any existing calibration")
        
        return response
    
    def close(self):
        """Close I2C connection"""
        if self.bus is not None:
            self.bus.close()
            self.bus = None


def main(args=None):
    rclpy.init(args=args)
    
    node = IMUHardwareNode()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.close()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
