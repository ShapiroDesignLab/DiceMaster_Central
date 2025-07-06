"""
U-M Shapiro Design Lab
Daniel Hou @2024

ROS2 node for IMU pose estimation using advanced Kalman filtering.
Implements quaternion-based Kalman filter with motion detection capabilities.
Publishes to /imu/* namespace with custom message types for enhanced functionality.
"""
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Pose, Quaternion, Point, Vector3
from sensor_msgs.msg import Imu
from std_msgs.msg import String, Bool
import threading
import time
from math import sin, cos, sqrt, atan2, asin, pi
import numpy as np
from scipy.spatial.transform import Rotation
from collections import deque

from DiceMaster_Central.config.constants import IMU_POLLING_RATE, IMU_HIST_SIZE
from DiceMaster_Central.utils import RingBufferNP

# Import custom message types
try:
    from dicemaster_central.msg import RawIMU, IMUPose, MotionDetection, IMUCalibration
except ImportError:
    # Fallback for development - create dummy classes
    class RawIMU:
        def __init__(self):
            self.header = None
            self.accel_x = 0.0
            self.accel_y = 0.0
            self.accel_z = 0.0
            self.gyro_x = 0.0
            self.gyro_y = 0.0
            self.gyro_z = 0.0
            self.temperature = 0.0
    
    class IMUPose:
        def __init__(self):
            self.header = None
            self.orientation = None
            self.roll = 0.0
            self.pitch = 0.0
            self.yaw = 0.0
            self.linear_acceleration = None
            self.angular_velocity = None
            self.orientation_covariance = [0.0] * 9
            self.acceleration_covariance = [0.0] * 9
            self.angular_velocity_covariance = [0.0] * 9
    
    class MotionDetection:
        def __init__(self):
            self.header = None
            self.rotation_x_positive = False
            self.rotation_x_negative = False
            self.rotation_y_positive = False
            self.rotation_y_negative = False
            self.rotation_z_positive = False
            self.rotation_z_negative = False
            self.shaking = False
            self.rotation_intensity = 0.0
            self.shake_intensity = 0.0
            self.stillness_factor = 1.0
    
    class IMUCalibration:
        def __init__(self):
            self.header = None
            self.status = ""
            self.progress = 0.0
            self.calibration_duration = 0.0
            self.accelerometer_bias = None
            self.gyroscope_bias = None
            self.accelerometer_std = 0.0
            self.gyroscope_std = 0.0
            self.sample_count = 0


class QuaternionKalmanFilter:
    """Advanced Kalman filter for quaternion-based pose estimation"""
    
    def __init__(self, process_noise=0.001, measurement_noise=1.0):
        # State: [q0, q1, q2, q3] (quaternion w, x, y, z)
        self.state = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float64)
        self.P = np.eye(4, dtype=np.float64) * 0.1  # Covariance matrix
        self.Q = np.eye(4, dtype=np.float64) * process_noise  # Process noise
        self.R = np.eye(4, dtype=np.float64) * measurement_noise  # Measurement noise
        self.I = np.eye(4, dtype=np.float64)  # Identity matrix
        
        # Angular velocity for state prediction
        self.omega = np.zeros(3, dtype=np.float64)
        
    def predict(self, dt, gyro):
        """Predict step using gyroscope data"""
        if dt <= 0:
            return
            
        # Update angular velocity
        self.omega = gyro
        
        # State transition matrix A based on angular velocity
        A = self._get_state_transition_matrix(dt)
        
        # Predict state
        self.state = A @ self.state
        
        # Normalize quaternion
        q_norm = np.linalg.norm(self.state)
        if q_norm > 0:
            self.state = self.state / q_norm
        
        # Predict covariance
        self.P = A @ self.P @ A.T + self.Q
        
    def update(self, accel_measurement):
        """Update step using accelerometer data"""
        # Convert accelerometer to quaternion measurement
        z = self._accel_to_quaternion(accel_measurement)
        
        # Measurement matrix H (identity since we're directly measuring quaternion)
        H = self.I
        
        # Innovation
        y = z - H @ self.state
        
        # Innovation covariance
        S = H @ self.P @ H.T + self.R
        
        # Kalman gain
        try:
            K = self.P @ H.T @ np.linalg.inv(S)
        except np.linalg.LinAlgError:
            K = self.P @ H.T @ np.linalg.pinv(S)
        
        # Update state
        self.state = self.state + K @ y
        
        # Normalize quaternion
        q_norm = np.linalg.norm(self.state)
        if q_norm > 0:
            self.state = self.state / q_norm
        
        # Update covariance
        self.P = (self.I - K @ H) @ self.P
        
    def _get_state_transition_matrix(self, dt):
        """Get state transition matrix for quaternion integration"""
        wx, wy, wz = self.omega
        
        # Quaternion integration matrix
        omega_matrix = np.array([
            [0.0, -wx, -wy, -wz],
            [wx,  0.0,  wz, -wy],
            [wy, -wz,  0.0,  wx],
            [wz,  wy, -wx,  0.0]
        ], dtype=np.float64)
        
        return self.I + 0.5 * dt * omega_matrix
        
    def _accel_to_quaternion(self, accel):
        """Convert accelerometer measurement to quaternion"""
        # Normalize accelerometer
        acc_norm = np.linalg.norm(accel)
        if acc_norm == 0:
            return np.array([1.0, 0.0, 0.0, 0.0])
        
        accel_normalized = accel / acc_norm
        
        # Calculate roll and pitch from accelerometer
        roll = atan2(accel_normalized[1], accel_normalized[2])
        pitch = atan2(-accel_normalized[0], 
                     sqrt(accel_normalized[1]**2 + accel_normalized[2]**2))
        yaw = 0.0  # Cannot determine yaw from accelerometer alone
        
        # Convert to quaternion
        return self._euler_to_quaternion(roll, pitch, yaw)
        
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
        
        return np.array([w, x, y, z], dtype=np.float64)
        
    def get_quaternion(self):
        """Get current quaternion estimate"""
        return self.state.copy()
        
    def get_euler_angles(self):
        """Convert quaternion to Euler angles"""
        w, x, y, z = self.state
        
        # Roll (x-axis rotation)
        sinr_cosp = 2 * (w * x + y * z)
        cosr_cosp = 1 - 2 * (x * x + y * y)
        roll = atan2(sinr_cosp, cosr_cosp)
        
        # Pitch (y-axis rotation)
        sinp = 2 * (w * y - z * x)
        if abs(sinp) >= 1:
            pitch = pi / 2 if sinp > 0 else -pi / 2
        else:
            pitch = asin(sinp)
        
        # Yaw (z-axis rotation)
        siny_cosp = 2 * (w * z + x * y)
        cosy_cosp = 1 - 2 * (y * y + z * z)
        yaw = atan2(siny_cosp, cosy_cosp)
        
        return roll, pitch, yaw


class MotionDetector:
    """Detects various motion patterns from IMU data"""
    
    def __init__(self, history_size=50):
        self.history_size = history_size
        self.accel_history = deque(maxlen=history_size)
        self.gyro_history = deque(maxlen=history_size)
        self.quat_history = deque(maxlen=history_size)
        
        # Detection thresholds
        self.rotation_threshold = 1.5  # rad/s
        self.shake_threshold = 15.0    # m/s²
        self.shake_frequency_min = 2.0  # Hz
        self.shake_frequency_max = 8.0  # Hz
        self.stillness_threshold = 0.5  # Combined motion threshold for stillness
        
    def update(self, accel, gyro, quaternion):
        """Update motion detector with new data"""
        self.accel_history.append(accel.copy())
        self.gyro_history.append(gyro.copy())
        self.quat_history.append(quaternion.copy())
        
    def detect_rotation_x_pos(self):
        """Detect +90 degree rotation around world X-axis (roll)"""
        return self._detect_axis_rotation(0, 1)
        
    def detect_rotation_x_neg(self):
        """Detect -90 degree rotation around world X-axis (roll)"""
        return self._detect_axis_rotation(0, -1)
        
    def detect_rotation_y_pos(self):
        """Detect +90 degree rotation around world Y-axis (pitch)"""
        return self._detect_axis_rotation(1, 1)
        
    def detect_rotation_y_neg(self):
        """Detect -90 degree rotation around world Y-axis (pitch)"""
        return self._detect_axis_rotation(1, -1)
        
    def detect_rotation_z_pos(self):
        """Detect +90 degree rotation around world Z-axis (yaw)"""
        return self._detect_axis_rotation(2, 1)
        
    def detect_rotation_z_neg(self):
        """Detect -90 degree rotation around world Z-axis (yaw)"""
        return self._detect_axis_rotation(2, -1)
        
    def _detect_axis_rotation(self, axis, direction):
        """Detect rotation around specific axis in specific direction"""
        if len(self.gyro_history) < 10:
            return False
            
        # Get recent angular velocity data
        recent_gyro = list(self.gyro_history)[-10:]
        
        # Check if there's sustained rotation around the specified axis
        axis_velocities = [gyro[axis] for gyro in recent_gyro]
        avg_velocity = np.mean(axis_velocities)
        
        # Check if rotation is in the correct direction and above threshold
        if direction > 0:
            return avg_velocity > self.rotation_threshold
        else:
            return avg_velocity < -self.rotation_threshold
            
    def detect_shaking(self):
        """Detect shaking motion"""
        if len(self.accel_history) < 20:
            return False
            
        # Get recent acceleration data
        recent_accel = np.array(list(self.accel_history)[-20:])
        
        # Calculate acceleration magnitude
        accel_magnitude = np.linalg.norm(recent_accel, axis=1)
        
        # Remove gravity component (approximate)
        accel_magnitude -= 9.81
        
        # Check for high-frequency, high-amplitude variations
        accel_std = np.std(accel_magnitude)
        accel_peak = np.max(np.abs(accel_magnitude))
        
        # Simple shake detection based on variation
        return accel_std > 3.0 and accel_peak > self.shake_threshold
        
    def get_rotation_intensity(self):
        """Calculate overall rotation intensity (0.0 to 1.0)"""
        if len(self.gyro_history) < 5:
            return 0.0
            
        recent_gyro = np.array(list(self.gyro_history)[-5:])
        gyro_magnitude = np.linalg.norm(recent_gyro, axis=1)
        avg_magnitude = np.mean(gyro_magnitude)
        
        # Normalize to 0-1 range (assume max meaningful rotation is 5 rad/s)
        return min(avg_magnitude / 5.0, 1.0)
        
    def get_shake_intensity(self):
        """Calculate shake intensity (0.0 to 1.0)"""
        if len(self.accel_history) < 10:
            return 0.0
            
        recent_accel = np.array(list(self.accel_history)[-10:])
        accel_magnitude = np.linalg.norm(recent_accel, axis=1)
        accel_std = np.std(accel_magnitude)
        
        # Normalize to 0-1 range (assume max meaningful shake std is 10)
        return min(accel_std / 10.0, 1.0)
        
    def get_stillness_factor(self):
        """Calculate stillness factor (1.0 = perfectly still, 0.0 = very active)"""
        rotation_intensity = self.get_rotation_intensity()
        shake_intensity = self.get_shake_intensity()
        
        # Combine both intensities
        combined_motion = (rotation_intensity + shake_intensity) / 2.0
        
        # Return inverse (1.0 - motion)
        return max(0.0, 1.0 - combined_motion)
        
    def get_motion_summary(self):
        """Get summary of all detected motions"""
        return {
            'rotation_x_pos': self.detect_rotation_x_pos(),
            'rotation_x_neg': self.detect_rotation_x_neg(),
            'rotation_y_pos': self.detect_rotation_y_pos(),
            'rotation_y_neg': self.detect_rotation_y_neg(),
            'rotation_z_pos': self.detect_rotation_z_pos(),
            'rotation_z_neg': self.detect_rotation_z_neg(),
            'shaking': self.detect_shaking(),
            'rotation_intensity': self.get_rotation_intensity(),
            'shake_intensity': self.get_shake_intensity(),
            'stillness_factor': self.get_stillness_factor()
        }


class DiceIMUNode(Node):
    """ROS2 node for IMU pose estimation with motion detection"""
    
    def __init__(self):
        super().__init__('dice_imu_node')
        
        # Declare parameters
        self.declare_parameter('calibration_duration', 3.0)
        self.declare_parameter('raw_imu_topic', '/imu/raw')
        self.declare_parameter('process_noise', 0.001)
        self.declare_parameter('measurement_noise', 1.0)
        self.declare_parameter('publishing_rate', 30.0)
        
        # Get parameters
        self.calib_duration = self.get_parameter('calibration_duration').get_parameter_value().double_value
        self.raw_imu_topic = self.get_parameter('raw_imu_topic').get_parameter_value().string_value
        process_noise = self.get_parameter('process_noise').get_parameter_value().double_value
        measurement_noise = self.get_parameter('measurement_noise').get_parameter_value().double_value
        self.publishing_rate = self.get_parameter('publishing_rate').get_parameter_value().double_value
        
        # Publishers - using custom message types
        self.pose_pub = self.create_publisher(IMUPose, '/imu/pose', 10)
        self.motion_pub = self.create_publisher(MotionDetection, '/imu/motion', 10)
        self.calibration_pub = self.create_publisher(IMUCalibration, '/imu/calibration', 10)
        
        # Legacy publishers for compatibility
        self.legacy_pose_pub = self.create_publisher(Pose, '/imu/pose_legacy', 10)
        self.accel_pub = self.create_publisher(Vector3, '/imu/accel', 10)
        self.angvel_pub = self.create_publisher(Vector3, '/imu/angvel', 10)
        self.status_pub = self.create_publisher(String, '/imu/status', 10)
        
        # Individual motion detection publishers (for backward compatibility)
        self.rotation_x_pos_pub = self.create_publisher(Bool, '/imu/motion/rotation_x_pos', 10)
        self.rotation_x_neg_pub = self.create_publisher(Bool, '/imu/motion/rotation_x_neg', 10)
        self.rotation_y_pos_pub = self.create_publisher(Bool, '/imu/motion/rotation_y_pos', 10)
        self.rotation_y_neg_pub = self.create_publisher(Bool, '/imu/motion/rotation_y_neg', 10)
        self.rotation_z_pos_pub = self.create_publisher(Bool, '/imu/motion/rotation_z_pos', 10)
        self.rotation_z_neg_pub = self.create_publisher(Bool, '/imu/motion/rotation_z_neg', 10)
        self.shaking_pub = self.create_publisher(Bool, '/imu/motion/shaking', 10)
        
        # Subscriber to raw IMU data (custom message format)
        self.imu_sub = self.create_subscription(
            RawIMU,
            self.raw_imu_topic,
            self.raw_imu_callback,
            10
        )
        
        # Fallback subscriber for standard IMU messages
        self.standard_imu_sub = self.create_subscription(
            Imu,
            '/sensor',
            self.standard_imu_callback,
            10
        )
        
        # State variables
        self.kalman_filter = QuaternionKalmanFilter(process_noise, measurement_noise)
        self.motion_detector = MotionDetector()
        self.is_calibrated = False
        self.acc_bias = np.zeros(3)
        self.gyro_bias = np.zeros(3)
        self.last_time = None
        
        # Calibration data
        self.calib_samples = []
        self.calib_start_time = None
        
        # Threading
        self.lock = threading.Lock()
        self.running = True
        
        # Publishing timer
        self.timer = self.create_timer(1.0/self.publishing_rate, self.timer_callback)
        
        # Current sensor data
        self.current_accel = np.zeros(3)
        self.current_gyro = np.zeros(3)
        self.current_quaternion = np.array([1.0, 0.0, 0.0, 0.0])
        self.current_temperature = 0.0
        
        # Start calibration
        self.publish_calibration_status("STARTING", 0.0)
        self.get_logger().info("Dice IMU node initialized - waiting for IMU data")
        
    def raw_imu_callback(self, msg):
        """Callback for custom RawIMU data"""
        current_time = time.time()
        
        # Extract accelerometer and gyroscope data from custom message
        accel = np.array([msg.accel_x, msg.accel_y, msg.accel_z])
        gyro = np.array([msg.gyro_x, msg.gyro_y, msg.gyro_z])
        
        with self.lock:
            self.current_temperature = msg.temperature
            
        self._process_imu_data(accel, gyro, current_time)
        
    def standard_imu_callback(self, msg):
        """Callback for standard sensor_msgs/Imu data (fallback)"""
        current_time = time.time()
        
        # Extract accelerometer and gyroscope data from standard message
        accel = np.array([
            msg.linear_acceleration.x,
            msg.linear_acceleration.y,
            msg.linear_acceleration.z
        ])
        
        gyro = np.array([
            msg.angular_velocity.x,
            msg.angular_velocity.y,
            msg.angular_velocity.z
        ])
        
        self._process_imu_data(accel, gyro, current_time)
        
    def _process_imu_data(self, accel, gyro, current_time):
        """Common processing for both message types"""
        # Handle calibration
        if not self.is_calibrated:
            self._handle_calibration(accel, gyro, current_time)
            return
            
        # Apply bias correction
        with self.lock:
            accel_corrected = accel - self.acc_bias
            gyro_corrected = gyro - self.gyro_bias
            
            # Update current sensor data
            self.current_accel = accel_corrected
            self.current_gyro = gyro_corrected
            
        # Update Kalman filter
        if self.last_time is not None:
            dt = current_time - self.last_time
            if 0 < dt < 0.1:  # Reasonable time step
                self.kalman_filter.predict(dt, gyro_corrected)
                self.kalman_filter.update(accel_corrected)
                
                # Get quaternion from Kalman filter
                with self.lock:
                    self.current_quaternion = self.kalman_filter.get_quaternion()
                    
                # Update motion detector
                self.motion_detector.update(accel_corrected, gyro_corrected, self.current_quaternion)
                
        self.last_time = current_time
        
    def timer_callback(self):
        """Timer callback for publishing data"""
        if not self.is_calibrated:
            return
            
        with self.lock:
            accel = self.current_accel.copy()
            gyro = self.current_gyro.copy()
            quaternion = self.current_quaternion.copy()
            temperature = self.current_temperature
            
        # Get Euler angles
        roll, pitch, yaw = self.kalman_filter.get_euler_angles()
        
        # Create header
        header = self.get_clock().now().to_msg()
        
        # Publish custom IMU pose message
        pose_msg = IMUPose()
        pose_msg.header.stamp = header
        pose_msg.header.frame_id = 'imu_link'
        
        # Set orientation
        pose_msg.orientation = Quaternion(
            x=quaternion[1],
            y=quaternion[2],
            z=quaternion[3],
            w=quaternion[0]
        )
        
        # Set Euler angles
        pose_msg.roll = roll
        pose_msg.pitch = pitch
        pose_msg.yaw = yaw
        
        # Set corrected acceleration and angular velocity
        pose_msg.linear_acceleration = Vector3(x=accel[0], y=accel[1], z=accel[2])
        pose_msg.angular_velocity = Vector3(x=gyro[0], y=gyro[1], z=gyro[2])
        
        # Set covariance matrices (simplified - could be computed from Kalman filter)
        pose_msg.orientation_covariance = [0.01] * 9
        pose_msg.acceleration_covariance = [0.1] * 9
        pose_msg.angular_velocity_covariance = [0.01] * 9
        
        self.pose_pub.publish(pose_msg)
        
        # Publish motion detection results
        motions = self.motion_detector.get_motion_summary()
        
        motion_msg = MotionDetection()
        motion_msg.header.stamp = header
        motion_msg.header.frame_id = 'imu_link'
        
        motion_msg.rotation_x_positive = motions['rotation_x_pos']
        motion_msg.rotation_x_negative = motions['rotation_x_neg']
        motion_msg.rotation_y_positive = motions['rotation_y_pos']
        motion_msg.rotation_y_negative = motions['rotation_y_neg']
        motion_msg.rotation_z_positive = motions['rotation_z_pos']
        motion_msg.rotation_z_negative = motions['rotation_z_neg']
        motion_msg.shaking = motions['shaking']
        motion_msg.rotation_intensity = motions['rotation_intensity']
        motion_msg.shake_intensity = motions['shake_intensity']
        motion_msg.stillness_factor = motions['stillness_factor']
        
        self.motion_pub.publish(motion_msg)
        
        # Publish legacy/compatibility messages
        legacy_pose_msg = Pose()
        legacy_pose_msg.position = Point(x=0.0, y=0.0, z=0.0)
        legacy_pose_msg.orientation = Quaternion(
            x=quaternion[1],
            y=quaternion[2],
            z=quaternion[3],
            w=quaternion[0]
        )
        self.legacy_pose_pub.publish(legacy_pose_msg)
        
        # Publish individual sensor data
        accel_msg = Vector3(x=accel[0], y=accel[1], z=accel[2])
        angvel_msg = Vector3(x=gyro[0], y=gyro[1], z=gyro[2])
        
        self.accel_pub.publish(accel_msg)
        self.angvel_pub.publish(angvel_msg)
        
        # Publish individual motion detection results for backward compatibility
        self.rotation_x_pos_pub.publish(Bool(data=motions['rotation_x_pos']))
        self.rotation_x_neg_pub.publish(Bool(data=motions['rotation_x_neg']))
        self.rotation_y_pos_pub.publish(Bool(data=motions['rotation_y_pos']))
        self.rotation_y_neg_pub.publish(Bool(data=motions['rotation_y_neg']))
        self.rotation_z_pos_pub.publish(Bool(data=motions['rotation_z_pos']))
        self.rotation_z_neg_pub.publish(Bool(data=motions['rotation_z_neg']))
        self.shaking_pub.publish(Bool(data=motions['shaking']))
        
    def _handle_calibration(self, accel, gyro, current_time):
        """Handle calibration process"""
        if self.calib_start_time is None:
            self.calib_start_time = current_time
            self.publish_calibration_status("CALIBRATING", 0.0)
            self.get_logger().info(f"Starting calibration for {self.calib_duration} seconds...")
            
        # Calculate progress
        elapsed = current_time - self.calib_start_time
        progress = min(elapsed / self.calib_duration, 1.0)
        
        # Collect calibration data
        if elapsed < self.calib_duration:
            self.calib_samples.append((accel.copy(), gyro.copy()))
            self.publish_calibration_status("CALIBRATING", progress)
            return
            
        # Finish calibration
        if len(self.calib_samples) > 0:
            acc_samples = np.array([s[0] for s in self.calib_samples])
            gyro_samples = np.array([s[1] for s in self.calib_samples])
            
            with self.lock:
                self.acc_bias = np.mean(acc_samples, axis=0)
                self.gyro_bias = np.mean(gyro_samples, axis=0)
                # Assume Z-axis should read -9.81 m/s² when upright
                self.acc_bias[2] += 9.81
                self.is_calibrated = True
                
            # Calculate calibration quality metrics
            acc_std = np.std(acc_samples, axis=0)
            gyro_std = np.std(gyro_samples, axis=0)
            
            self.get_logger().info("Calibration complete")
            self.get_logger().info(f"Accelerometer bias: {self.acc_bias}")
            self.get_logger().info(f"Gyroscope bias: {self.gyro_bias}")
            self.get_logger().info(f"Accelerometer std: {acc_std}")
            self.get_logger().info(f"Gyroscope std: {gyro_std}")
            
            self.publish_calibration_status("READY", 1.0, acc_std, gyro_std)
            
            # Clear calibration data
            self.calib_samples.clear()
        else:
            self.get_logger().error("Calibration failed - no data collected")
            self.publish_calibration_status("CALIBRATION_FAILED", 0.0)
            
    def publish_calibration_status(self, status, progress, acc_std=None, gyro_std=None):
        """Publish calibration status using custom message"""
        # Legacy status message
        status_msg = String()
        status_msg.data = status
        self.status_pub.publish(status_msg)
        
        # Custom calibration message
        calib_msg = IMUCalibration()
        calib_msg.header.stamp = self.get_clock().now().to_msg()
        calib_msg.header.frame_id = 'imu_link'
        calib_msg.status = status
        calib_msg.progress = progress
        calib_msg.calibration_duration = self.calib_duration
        calib_msg.sample_count = len(self.calib_samples)
        
        if self.is_calibrated:
            calib_msg.accelerometer_bias = Vector3(
                x=self.acc_bias[0], y=self.acc_bias[1], z=self.acc_bias[2]
            )
            calib_msg.gyroscope_bias = Vector3(
                x=self.gyro_bias[0], y=self.gyro_bias[1], z=self.gyro_bias[2]
            )
            
        if acc_std is not None:
            calib_msg.accelerometer_std = float(np.mean(acc_std))
        if gyro_std is not None:
            calib_msg.gyroscope_std = float(np.mean(gyro_std))
            
        self.calibration_pub.publish(calib_msg)
        
    def publish_status(self, status):
        """Legacy method for backward compatibility"""
        self.publish_calibration_status(status, 0.0)
        
    def destroy_node(self):
        """Clean shutdown"""
        self.running = False
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    
    node = DiceIMUNode()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
