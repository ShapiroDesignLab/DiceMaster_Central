"""
U-M Shapiro Design Lab
Daniel Hou @2024

ROS2 node for IMU pose estimation using Kalman filtering.
Subscribes to ros2_mpu6050_driver and publishes filtered pose data.
"""
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Pose, Quaternion, Point
from sensor_msgs.msg import Imu
from std_msgs.msg import String
import threading
import time
from math import sin, cos, sqrt
import numpy as np
from scipy.spatial.transform import Rotation

from .constants import IMU_POLLING_RATE, IMU_HIST_SIZE
from .utils import RingBufferNP

class KalmanFilter:
    def __init__(self, process_noise=0.01, measurement_noise=0.1):
        # State: [qw, qx, qy, qz, wx, wy, wz]
        self.state = np.array([1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], dtype=np.float64)
        self.P = np.eye(7, dtype=np.float64) * 0.1  # Covariance matrix
        self.Q = np.eye(7, dtype=np.float64) * process_noise  # Process noise
        self.R = np.eye(6, dtype=np.float64) * measurement_noise  # Measurement noise (3 accel + 3 gyro)
        
    def predict(self, dt):
        """Predict step of Kalman filter"""
        if dt <= 0:
            return
            
        # Extract quaternion and angular velocity
        q = self.state[:4].copy()
        w = self.state[4:].copy()
        
        # Normalize quaternion
        q_norm = np.linalg.norm(q)
        if q_norm > 0:
            q = q / q_norm
        
        # Quaternion integration using angular velocity
        omega_norm = np.linalg.norm(w)
        if omega_norm > 1e-8:
            axis = w / omega_norm
            angle = omega_norm * dt
            half_angle = angle / 2.0
            dq = np.array([cos(half_angle), 
                          axis[0] * sin(half_angle), 
                          axis[1] * sin(half_angle), 
                          axis[2] * sin(half_angle)])
            # Quaternion multiplication
            q_new = self.quaternion_multiply(q, dq)
        else:
            q_new = q
            
        # Normalize and update state
        q_new_norm = np.linalg.norm(q_new)
        if q_new_norm > 0:
            self.state[:4] = q_new / q_new_norm
        
        # Update angular velocity (assume constant for now)
        self.state[4:] = w
        
        # Predict covariance with simplified Jacobian
        F = np.eye(7, dtype=np.float64)
        # Add some coupling between quaternion and angular velocity
        F[:4, 4:] = np.eye(4, 3) * dt * 0.5
        
        self.P = F @ self.P @ F.T + self.Q
        
    def update(self, accel, gyro):
        """Update step of Kalman filter"""
        # Measurement vector [ax, ay, az, gx, gy, gz]
        z = np.concatenate([accel, gyro])
        
        # Expected measurement
        h = self.measurement_model()
        
        # Innovation
        y = z - h
        
        # Measurement Jacobian (simplified)
        H = np.zeros((6, 7), dtype=np.float64)
        # Accelerometer measures gravity in body frame (depends on quaternion)
        H[:3, :4] = self.get_gravity_jacobian()
        # Gyroscope directly measures angular velocity
        H[3:, 4:] = np.eye(3)
        
        # Innovation covariance
        S = H @ self.P @ H.T + self.R
        
        # Kalman gain
        try:
            K = self.P @ H.T @ np.linalg.inv(S)
        except np.linalg.LinAlgError:
            # If S is singular, use pseudo-inverse
            K = self.P @ H.T @ np.linalg.pinv(S)
        
        # Update state
        self.state += K @ y
        
        # Normalize quaternion
        q_norm = np.linalg.norm(self.state[:4])
        if q_norm > 0:
            self.state[:4] = self.state[:4] / q_norm
        
        # Update covariance
        I = np.eye(7, dtype=np.float64)
        self.P = (I - K @ H) @ self.P
        
    def get_quaternion(self):
        """Get current quaternion estimate"""
        return self.state[:4].copy()
        
    def quaternion_multiply(self, q1, q2):
        """Multiply two quaternions"""
        w1, x1, y1, z1 = q1
        w2, x2, y2, z2 = q2
        return np.array([
            w1*w2 - x1*x2 - y1*y2 - z1*z2,
            w1*x2 + x1*w2 + y1*z2 - z1*y2,
            w1*y2 - x1*z2 + y1*w2 + z1*x2,
            w1*z2 + x1*y2 - y1*x2 + z1*w2
        ], dtype=np.float64)
        
    def measurement_model(self):
        """Expected measurement given current state"""
        # Expected accelerometer reading (gravity vector in body frame)
        q = self.state[:4]
        gravity_world = np.array([0.0, 0.0, -9.81])
        gravity_body = self.rotate_vector_by_quaternion(gravity_world, self.quaternion_inverse(q))
        
        # Expected gyroscope reading
        gyro_expected = self.state[4:]
        
        return np.concatenate([gravity_body, gyro_expected])
        
    def get_gravity_jacobian(self):
        """Jacobian of gravity measurement with respect to quaternion"""
        # Simplified gravity jacobian
        return np.eye(3, 4) * 0.1
        
    def quaternion_inverse(self, q):
        """Compute quaternion inverse"""
        w, x, y, z = q
        norm_sq = w*w + x*x + y*y + z*z
        if norm_sq > 0:
            return np.array([w, -x, -y, -z]) / norm_sq
        return np.array([1.0, 0.0, 0.0, 0.0])
        
    def rotate_vector_by_quaternion(self, v, q):
        """Rotate vector v by quaternion q"""
        w, x, y, z = q
        
        # Convert to rotation matrix approach for stability
        R = np.array([
            [1-2*(y*y+z*z), 2*(x*y-w*z), 2*(x*z+w*y)],
            [2*(x*y+w*z), 1-2*(x*x+z*z), 2*(y*z-w*x)],
            [2*(x*z-w*y), 2*(y*z+w*x), 1-2*(x*x+y*y)]
        ])
        
        return R @ v

class DiceIMUNode(Node):
    """ROS2 node for IMU pose estimation using Kalman filtering"""
    
    def __init__(self):
        super().__init__('dice_imu_node')
        
        # Declare parameters
        self.declare_parameter('calibration_duration', 3.0)
        self.declare_parameter('roll_offset', 0.0)
        self.declare_parameter('pitch_offset', 0.0)
        self.declare_parameter('yaw_offset', 0.0)
        self.declare_parameter('mpu6050_topic', '/imu')
        self.declare_parameter('process_noise', 0.01)
        self.declare_parameter('measurement_noise', 0.1)
        
        # Get parameters
        self.calib_duration = self.get_parameter('calibration_duration').get_parameter_value().double_value
        self.roll_offset = self.get_parameter('roll_offset').get_parameter_value().double_value
        self.pitch_offset = self.get_parameter('pitch_offset').get_parameter_value().double_value
        self.yaw_offset = self.get_parameter('yaw_offset').get_parameter_value().double_value
        self.mpu6050_topic = self.get_parameter('mpu6050_topic').get_parameter_value().string_value
        process_noise = self.get_parameter('process_noise').get_parameter_value().double_value
        measurement_noise = self.get_parameter('measurement_noise').get_parameter_value().double_value
        
        # Create orientation offset quaternion
        self.orientation_offset = Rotation.from_euler('xyz', [
            self.roll_offset, self.pitch_offset, self.yaw_offset
        ]).as_quat()  # Returns [x, y, z, w]
        
        # Publishers
        self.status_pub = self.create_publisher(String, 'dice_imu/status', 10)
        self.pose_pub = self.create_publisher(Pose, 'dice_imu/pose', 10)
        
        # Subscriber to MPU6050 driver
        self.imu_sub = self.create_subscription(
            Imu,
            self.mpu6050_topic,
            self.imu_callback,
            10
        )
        
        # State variables
        self.kalman_filter = KalmanFilter(process_noise, measurement_noise)
        self.is_calibrated = False
        self.acc_bias = np.zeros(3)
        self.gyro_bias = np.zeros(3)
        self.last_time = None
        
        # History buffers
        self.quat_hist = RingBufferNP((IMU_HIST_SIZE, 4))
        self.acc_hist = RingBufferNP((IMU_HIST_SIZE, 3))
        self.gyro_hist = RingBufferNP((IMU_HIST_SIZE, 3))
        
        # Calibration data
        self.calib_samples = []
        self.calib_start_time = None
        
        # Threading
        self.lock = threading.Lock()
        self.running = True
        
        # Start calibration
        self.publish_status("STARTING")
        self.get_logger().info("Dice IMU node initialized - waiting for IMU data")
        
    def imu_callback(self, msg):
        """Callback for IMU data from ros2_mpu6050_driver"""
        current_time = time.time()
        
        # Extract accelerometer and gyroscope data
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
        
        # Handle calibration
        if not self.is_calibrated:
            self._handle_calibration(accel, gyro, current_time)
            return
            
        # Apply bias correction
        with self.lock:
            accel_corrected = accel - self.acc_bias
            gyro_corrected = gyro - self.gyro_bias
            
        # Update Kalman filter
        if self.last_time is None:
          self.last_time = current_time
          return

        dt = current_time - self.last_time
		if dt < 0 or dt > 0.1: 
			return
		
		self.kalman_filter.predict(dt)
		self.kalman_filter.update(accel_corrected, gyro_corrected)
		
		# Get quaternion from Kalman filter
		quat_raw = self.kalman_filter.get_quaternion()
		
		# Apply orientation offset
		quat_offset = Rotation.from_quat(self.orientation_offset)
		quat_sensor = Rotation.from_quat([quat_raw[1], quat_raw[2], quat_raw[3], quat_raw[0]])  # Convert w,x,y,z to x,y,z,w
		quat_final = quat_offset * quat_sensor
		quat_final_xyzw = quat_final.as_quat()
		
		# Store in history
		with self.lock:
			self.quat_hist.push_front(quat_final_xyzw)
			self.acc_hist.push_front(accel_corrected)
			self.gyro_hist.push_front(gyro_corrected)
		
		# Publish pose
		pose_msg = Pose()
		pose_msg.position = Point(x=0.0, y=0.0, z=0.0)  # No position estimation
		pose_msg.orientation = Quaternion(
			x=quat_final_xyzw[0],
			y=quat_final_xyzw[1], 
			z=quat_final_xyzw[2],
			w=quat_final_xyzw[3]
		)
		self.pose_pub.publish(pose_msg)
			
	
    def _handle_calibration(self, accel, gyro, current_time):
        """Handle calibration process"""
        if self.calib_start_time is None:
            self.calib_start_time = current_time
            self.publish_status("CALIBRATING")
            self.get_logger().info(f"Starting calibration for {self.calib_duration} seconds...")
            
        # Collect calibration data
        if current_time - self.calib_start_time < self.calib_duration:
            self.calib_samples.append((accel.copy(), gyro.copy()))
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
				
			self.get_logger().info("Calibration complete")
			self.get_logger().info(f"Accelerometer bias: {self.acc_bias}")
			self.get_logger().info(f"Gyroscope bias: {self.gyro_bias}")
			self.publish_status("READY")
			
			# Clear calibration data
			self.calib_samples.clear()
			return
		# Otherwise, error
		self.get_logger().error("Calibration failed - no data collected")
		self.publish_status("CALIBRATION_FAILED")
            
    def publish_status(self, status):
        """Publish status message"""
        msg = String()
        msg.data = status
        self.status_pub.publish(msg)
        
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
