"""
U-M Shapiro Design Lab
Daniel Hou @2024

ROS2 node for IMU pose estimation using advanced Kalman filtering.
Implements quaternion-based Kalman filter with motion detection capabilities.
Publishes to /imu/* namespace with custom message types for enhanced functionality.

USAGE IN ROS2:
==============

1. Launch the IMU Node:
   ros2 run dicemaster_central imu_node
   
   # Or with custom parameters
   ros2 run dicemaster_central imu_node --ros-args \
     -p calibration_duration:=5.0 \
     -p process_noise:=0.01 \
     -p measurement_noise:=0.5 \
     -p publishing_rate:=50.0

2. Data Topics (Published):
   - /dice_hw/imu/pose (Pose): Pose estimation with quaternion orientation and position
   - /dice_hw/imu/raw (RawIMU): Raw IMU sensor data
   - /dice_hw/imu/motion (MotionDetection): Motion detection results (rotations, shaking, intensities)
   - /dice_hw/imu/calibration (IMUCalibration): Calibration status and quality metrics
   - /dice_hw/imu/accel, /dice_hw/imu/angvel (Vector3): Individual sensor data
   - /dice_hw/imu/motion/* (Bool): Individual motion detection flags

3. Services:
   - /dice_hw/imu/calibrate (Empty): Start IMU calibration process
     Usage: ros2 service call /dice_hw/imu/calibrate std_srvs/srv/Empty

4. Integration Example:
   import rclpy
   from geometry_msgs.msg import Pose
   from dicemaster_central.msg import MotionDetection
   
   class MyNode(Node):
       def __init__(self):
           super().__init__('my_node')
           self.pose_sub = self.create_subscription(
               Pose, '/dice_hw/imu/pose', self.pose_callback, 10)
           self.motion_sub = self.create_subscription(
               MotionDetection, '/dice_hw/imu/motion', self.motion_callback, 10)
               
       def pose_callback(self, msg):
           # Use pose data: msg.orientation.{w,x,y,z}
           # Position is always (0,0,0) for IMU-only pose
           pass
           
       def motion_callback(self, msg):
           if msg.shaking:
               self.get_logger().info("Dice is being shaken!")
           if msg.rotation_x_pos:
               self.get_logger().info("Dice rolled +X!")

5. Hardware Requirements:
   - MPU6050 or compatible IMU on I2C bus
   - Default I2C address: 0x68
   - Default I2C bus: 1

6. Calibration Process:
   - Keep dice perfectly still during calibration countdown
   - Calibration removes bias from accelerometer and gyroscope
   - Status published on /dice_hw/imu/calibration topic

IMPORTANT: Keep the dice completely still during calibration!
"""
import threading
import time
from math import sin, cos, sqrt, atan2, asin, pi
import numpy as np

# I2C communication
try:
    import smbus2
    I2C_AVAILABLE = True
except ImportError:
    I2C_AVAILABLE = False
    print("Warning: smbus2 not available. IMU I2C communication disabled.")

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


class FilteredIMUHardware(IMUHardware):
    """IMU hardware with advanced filtering and calibration capabilities"""
    
    def __init__(self, i2c_bus=6, i2c_address=0x68, process_noise=0.001, measurement_noise=1.0):
        super().__init__(i2c_bus, i2c_address)
        
        # Import here to avoid circular dependency issues
        try:
            from DiceMaster_Central.utils.kalman_filter import QuaternionKalmanFilter
            self.kalman_filter = QuaternionKalmanFilter(process_noise, measurement_noise)
        except ImportError:
            print("Warning: QuaternionKalmanFilter not available, using basic filtering")
            self.kalman_filter = None
        
        # Calibration parameters
        self.is_calibrated = False
        self.calibration_requested = False
        self.calibration_duration = 3.0  # seconds
        self.calibration_samples = []
        self.calibration_start_time = None
        
        # Sensor biases (set during calibration)
        self.accel_bias = np.zeros(3)
        self.gyro_bias = np.zeros(3)
        
        # Current state
        self.current_quaternion = np.array([1.0, 0.0, 0.0, 0.0])  # w, x, y, z
        self.last_time = None
        
        # Threading lock for thread-safe operations
        self.lock = threading.Lock()
        
        print(f"FilteredIMUHardware initialized with Kalman filter: {self.kalman_filter is not None}")
    
    def start_calibration(self, duration=3.0):
        """Start calibration process
        
        Args:
            duration: Calibration duration in seconds
        """
        with self.lock:
            if self.calibration_requested:
                print("Warning: Calibration already in progress")
                return False
                
            self.calibration_duration = duration
            self.calibration_requested = True
            self.calibration_samples = []
            self.calibration_start_time = None
            self.is_calibrated = False
            
            print(f"Calibration started - keep IMU perfectly still for {duration} seconds")
            return True
    
    def _handle_calibration(self, imu_data):
        """Handle calibration data collection
        
        Args:
            imu_data: Raw IMU data array [ax, ay, az, gx, gy, gz]
        """
        current_time = time.time()
        
        if self.calibration_start_time is None:
            self.calibration_start_time = current_time
            print("Starting calibration data collection...")
        
        elapsed = current_time - self.calibration_start_time
        
        if elapsed < self.calibration_duration:
            # Collect calibration data
            self.calibration_samples.append(imu_data.copy())
            
            # Progress update every second (estimate based on sample count)
            if len(self.calibration_samples) % 25 == 0:  # Every 25 samples (roughly every 0.5 seconds)
                remaining = self.calibration_duration - elapsed
                print(f"Calibration progress: {elapsed:.1f}s / {self.calibration_duration:.1f}s (remaining: {remaining:.1f}s) - Samples: {len(self.calibration_samples)}")
            
            return None  # Return None during calibration
        else:
            # Finish calibration
            self._finish_calibration()
            return None
    
    def _finish_calibration(self):
        """Complete the calibration process"""
        if len(self.calibration_samples) == 0:
            print("Calibration failed: No data collected")
            self.calibration_requested = False
            return
        
        # Calculate biases
        samples = np.array(self.calibration_samples)
        
        # Accelerometer bias (subtract gravity from Z-axis)
        self.accel_bias = np.mean(samples[:, :3], axis=0)
        self.accel_bias[2] += 9.81  # Assume Z-axis should read -9.81 m/s² when upright
        
        # Gyroscope bias
        self.gyro_bias = np.mean(samples[:, 3:6], axis=0)
        
        # Calculate calibration quality
        accel_std = np.std(samples[:, :3], axis=0)
        gyro_std = np.std(samples[:, 3:6], axis=0)
        
        # Set calibration complete
        self.is_calibrated = True
        self.calibration_requested = False
        
        print("Calibration complete!")
        print(f"Accelerometer bias: [{self.accel_bias[0]:.3f}, {self.accel_bias[1]:.3f}, {self.accel_bias[2]:.3f}] m/s²")
        print(f"Gyroscope bias: [{self.gyro_bias[0]:.6f}, {self.gyro_bias[1]:.6f}, {self.gyro_bias[2]:.6f}] rad/s")
        print(f"Accelerometer std: [{accel_std[0]:.3f}, {accel_std[1]:.3f}, {accel_std[2]:.3f}] m/s²")
        print(f"Gyroscope std: [{gyro_std[0]:.6f}, {gyro_std[1]:.6f}, {gyro_std[2]:.6f}] rad/s")
        
        # Clear calibration data
        self.calibration_samples = []
        
        # Quality assessment
        if np.mean(accel_std) < 0.5 and np.mean(gyro_std) < 0.1:
            print("Calibration quality: GOOD")
        else:
            print("Calibration quality: MODERATE - consider recalibrating")
    
    def _poll_imu(self):
        """Read and process IMU data with calibration and filtering
        
        Returns:
            numpy array [ax, ay, az, gx, gy, gz] or None if in calibration
        """
        # Get raw data
        raw_data = super()._poll_imu()
        
        # Handle calibration if requested
        if self.calibration_requested:
            return self._handle_calibration(raw_data)
        
        # Skip processing if not calibrated
        if not self.is_calibrated:
            print("Warning: IMU not calibrated. Call start_calibration() first.")
            return raw_data
        
        # Apply bias correction FIRST
        with self.lock:
            corrected_data = raw_data.copy()
            corrected_data[:3] -= self.accel_bias
            corrected_data[3:6] -= self.gyro_bias
        
        # Apply Kalman filter to the bias-corrected data
        if self.kalman_filter is not None:
            current_time = time.time()
            
            if self.last_time is not None:
                dt = current_time - self.last_time
                if 0 < dt < 0.1:  # Reasonable time step
                    # Update Kalman filter with bias-corrected data
                    self.kalman_filter.predict(dt, corrected_data[3:6])  # bias-corrected gyro data
                    self.kalman_filter.update(corrected_data[:3])  # bias-corrected accel data
                    
                    # Get current quaternion from Kalman filter
                    with self.lock:
                        self.current_quaternion = self.kalman_filter.get_quaternion()
            
            self.last_time = current_time
        
        return corrected_data
    
    def get_quaternion(self):
        """Get current orientation quaternion [w, x, y, z]"""
        with self.lock:
            return self.current_quaternion.copy()
    
    def get_euler_angles(self):
        """Get current Euler angles (roll, pitch, yaw) in radians"""
        if self.kalman_filter is not None:
            return self.kalman_filter.get_euler_angles()
        else:
            # Simple conversion from accelerometer data
            data = self.get_imu_data()
            if data is None:
                return 0.0, 0.0, 0.0
            
            ax, ay, az = data[:3]
            
            # Calculate roll and pitch from accelerometer
            roll = atan2(ay, az)
            pitch = atan2(-ax, sqrt(ay*ay + az*az))
            yaw = 0.0  # Cannot determine yaw from accelerometer alone
            
            return roll, pitch, yaw
    
    def get_calibration_status(self):
        """Get current calibration status
        
        Returns:
            dict: Status information
        """
        with self.lock:
            status = {
                'is_calibrated': self.is_calibrated,
                'calibration_requested': self.calibration_requested,
                'accel_bias': self.accel_bias.copy() if self.is_calibrated else None,
                'gyro_bias': self.gyro_bias.copy() if self.is_calibrated else None,
                'samples_collected': len(self.calibration_samples),
                'calibration_duration': self.calibration_duration
            }
            
            if self.calibration_requested and self.calibration_start_time is not None:
                elapsed = time.time() - self.calibration_start_time
                status['calibration_progress'] = min(elapsed / self.calibration_duration, 1.0)
                status['calibration_remaining'] = max(0, self.calibration_duration - elapsed)
            
            return status
    
    def save_calibration(self, filename):
        """Save calibration data to file"""
        if not self.is_calibrated:
            print("Warning: Cannot save calibration - not calibrated")
            return False
        
        try:
            calibration_data = {
                'accel_bias': self.accel_bias.tolist(),
                'gyro_bias': self.gyro_bias.tolist(),
                'timestamp': time.time()
            }
            
            import json
            with open(filename, 'w') as f:
                json.dump(calibration_data, f, indent=2)
            
            print(f"Calibration saved to {filename}")
            return True
        except Exception as e:
            print(f"Error saving calibration: {e}")
            return False
    
    def load_calibration(self, filename):
        """Load calibration data from file"""
        try:
            import json
            with open(filename, 'r') as f:
                calibration_data = json.load(f)
            
            self.accel_bias = np.array(calibration_data['accel_bias'])
            self.gyro_bias = np.array(calibration_data['gyro_bias'])
            self.is_calibrated = True
            self.calibration_requested = False
            
            print(f"Calibration loaded from {filename}")
            print(f"Accelerometer bias: [{self.accel_bias[0]:.3f}, {self.accel_bias[1]:.3f}, {self.accel_bias[2]:.3f}] m/s²")
            print(f"Gyroscope bias: [{self.gyro_bias[0]:.6f}, {self.gyro_bias[1]:.6f}, {self.gyro_bias[2]:.6f}] rad/s")
            return True
        except Exception as e:
            print(f"Error loading calibration: {e}")
            return False
    
    def _euler_to_quaternion(self, roll, pitch, yaw):
        """Convert Euler angles to quaternion"""
        cr = cos(roll / 2.0)
        sr = sin(roll / 2.0)
        cp = cos(pitch / 2.0)
        sp = sin(pitch / 2.0)
        cy = cos(yaw / 2.0)
        sy = sin(yaw / 2.0)
        
        w = cr * cp * cy + sr * sp * sy
        x = sr * cp * cy - cr * sp * sy
        y = cr * sp * cy + sr * cp * sy
        z = cr * cp * sy - sr * sp * cy
        
        return np.array([w, x, y, z])