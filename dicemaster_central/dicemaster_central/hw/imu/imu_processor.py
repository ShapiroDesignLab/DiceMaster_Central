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
   from dicemaster_central_msgs.msg import MotionDetection
   
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
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Pose, Quaternion, Point, Vector3
from sensor_msgs.msg import Imu
from std_msgs.msg import String, Bool, Header
from std_srvs.srv import Empty
import threading
import time
from math import sin, cos, sqrt, atan2, asin, pi
import numpy as np


from dicemaster_central.config.constants import IMU_POLLING_RATE, IMU_HIST_SIZE
from dicemaster_central.utils import QuaternionKalmanFilter
from dicemaster_central.hw.motion_detector import MotionDetector

from dicemaster_central_msgs.msg import RawIMU, MotionDetection, IMUCalibration, NotificationRequest

from .imu import BaseIMU

class IMUProcessorNode(Node):
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
        
        # Publishers - using custom message types and standard Pose
        self.pose_pub = self.create_publisher(Pose, '/dice_hw/imu/pose', 10)
        self.raw_imu_pub = self.create_publisher(RawIMU, '/dice_hw/imu/raw', 10)
        self.motion_pub = self.create_publisher(MotionDetection, '/dice_hw/imu/motion', 10)
        self.calibration_pub = self.create_publisher(IMUCalibration, '/dice_hw/imu/calibration', 10)
        
        # Legacy publishers for compatibility
        self.legacy_pose_pub = self.create_publisher(Pose, '/imu/pose_legacy', 10)
        self.accel_pub = self.create_publisher(Vector3, '/dice_hw/imu/accel', 10)
        self.angvel_pub = self.create_publisher(Vector3, '/dice_hw/imu/angvel', 10)
        self.status_pub = self.create_publisher(String, '/imu/status', 10)
        
        # Individual motion detection publishers (for backward compatibility)
        self.rotation_x_pos_pub = self.create_publisher(Bool, '/imu/motion/rotation_x_pos', 10)
        self.rotation_x_neg_pub = self.create_publisher(Bool, '/imu/motion/rotation_x_neg', 10)
        self.rotation_y_pos_pub = self.create_publisher(Bool, '/imu/motion/rotation_y_pos', 10)
        self.rotation_y_neg_pub = self.create_publisher(Bool, '/imu/motion/rotation_y_neg', 10)
        self.rotation_z_pos_pub = self.create_publisher(Bool, '/imu/motion/rotation_z_pos', 10)
        self.rotation_z_neg_pub = self.create_publisher(Bool, '/imu/motion/rotation_z_neg', 10)
        self.shaking_pub = self.create_publisher(Bool, '/imu/motion/shaking', 10)

        # Notification publisher for sending notifications to screens
        self.notification_pub = self.create_publisher(NotificationRequest, '/dice_system/notifications', 10)

        # Calibration service
        self.calibration_service = self.create_service(
            Empty,
            '/dice_hw/imu/calibrate',
            self.calibrate_service_callback
        )
        
        # Subscriber to raw IMU data (custom message format)
        self.imu_sub = self.create_subscription(
            RawIMU,
            self.raw_imu_topic,
            self.raw_imu_callback,
            10
        )
        
        # Initialize Kalman filter and motion detector
        self.kalman_filter = QuaternionKalmanFilter(process_noise, measurement_noise)
        self.motion_detector = MotionDetector(history_size=50)
        
        # Calibration state
        self.is_calibrated = False
        self.calibration_requested = False
        self.calib_samples = []
        self.calib_start_time = None
        self.calibration_timer = None
        
        # Sensor biases (will be set during calibration)
        self.acc_bias = np.zeros(3)
        self.gyro_bias = np.zeros(3)
        
        # Timing
        self.last_time = None
        
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
        
        # Don't start calibration automatically - wait for service call
        self.get_logger().info("Dice IMU node initialized - call /dice_hw/imu/calibrate service to start calibration")
        
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
        if self.calibration_requested and not self.is_calibrated:
            self._handle_calibration(accel, gyro, current_time)
            return
            
        # Skip processing if not calibrated
        if not self.is_calibrated:
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
        
        # Publish main Pose message for robot state
        pose_msg = Pose()
        pose_msg.position = Point(x=0.0, y=0.0, z=0.0)  # IMU provides orientation only
        pose_msg.orientation = Quaternion(
            x=quaternion[1],
            y=quaternion[2],
            z=quaternion[3],
            w=quaternion[0]
        )
        self.pose_pub.publish(pose_msg)
        
        # Publish RawIMU message with corrected sensor data
        raw_imu_msg = RawIMU()
        raw_imu_msg.header.stamp = header
        raw_imu_msg.header.frame_id = 'imu_link'
        raw_imu_msg.accel_x = accel[0]
        raw_imu_msg.accel_y = accel[1]
        raw_imu_msg.accel_z = accel[2]
        raw_imu_msg.gyro_x = gyro[0]
        raw_imu_msg.gyro_y = gyro[1]
        raw_imu_msg.gyro_z = gyro[2]
        raw_imu_msg.temperature = temperature
        
        self.raw_imu_pub.publish(raw_imu_msg)
        
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
            self.get_logger().info(f"Starting calibration data collection for {self.calib_duration} seconds...")
            self._send_notification_to_all_screens("info", "Calibration data collection started", 2.0)
            
        # Calculate progress
        elapsed = current_time - self.calib_start_time
        progress = min(elapsed / self.calib_duration, 1.0)
        
        # Collect calibration data
        if elapsed < self.calib_duration:
            self.calib_samples.append((accel.copy(), gyro.copy()))
            self.publish_calibration_status("CALIBRATING", progress)
            
            # Send progress notifications every second
            if len(self.calib_samples) % 30 == 0:  # Assuming ~30Hz data rate
                remaining = int(self.calib_duration - elapsed)
                if remaining > 0:
                    self._send_notification_to_all_screens("info", 
                        f"Calibrating... {remaining}s remaining", 1.5)
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
                self.calibration_requested = False
                
            # Calculate calibration quality metrics
            acc_std = np.std(acc_samples, axis=0)
            gyro_std = np.std(gyro_samples, axis=0)
            
            self.get_logger().info("Calibration complete")
            self.get_logger().info(f"Accelerometer bias: {self.acc_bias}")
            self.get_logger().info(f"Gyroscope bias: {self.gyro_bias}")
            self.get_logger().info(f"Accelerometer std: {acc_std}")
            self.get_logger().info(f"Gyroscope std: {gyro_std}")
            
            self.publish_calibration_status("READY", 1.0, acc_std, gyro_std)
            
            # Send completion notification
            quality = "good" if np.mean(acc_std) < 0.5 and np.mean(gyro_std) < 0.1 else "moderate"
            self._send_notification_to_all_screens("info", 
                f"IMU Calibration Complete! Quality: {quality}", 4.0)
            
            # Clear calibration data
            self.calib_samples.clear()
        else:
            self.get_logger().error("Calibration failed - no data collected")
            self.publish_calibration_status("CALIBRATION_FAILED", 0.0)
            self._send_notification_to_all_screens("error", 
                "IMU Calibration Failed - No data collected", 4.0)
            self.calibration_requested = False
            
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
        
    def calibrate_service_callback(self, request, response):
        """Service callback to start IMU calibration"""
        if self.calibration_requested:
            self.get_logger().warn("Calibration already in progress")
            return response
            
        self.get_logger().info("Calibration service called - starting calibration process")
        
        # Reset calibration state
        with self.lock:
            self.is_calibrated = False
            self.calibration_requested = True
            self.calib_samples.clear()
            self.calib_start_time = None
            
        # Send initial notification to all screens
        self._send_notification_to_all_screens("info", 
            f"IMU Calibration Starting - Keep dice perfectly still for {int(self.calib_duration)} seconds")
        
        # Start countdown notifications
        self._start_calibration_countdown()
        
        return response
    
    def _send_notification_to_all_screens(self, level, content, duration=3.0):
        """Send notification to all screens (screen IDs 0-7)"""
        for screen_id in range(8):  # Assuming up to 8 screens
            notification = NotificationRequest()
            notification.screen_id = screen_id
            notification.level = level
            notification.content = content
            notification.duration = duration
            self.notification_pub.publish(notification)
    
    def _start_calibration_countdown(self):
        """Start countdown timer for calibration notifications"""
        # Cancel any existing timer
        if self.calibration_timer is not None:
            self.calibration_timer.cancel()
            
        # Send countdown notifications every second
        countdown_duration = int(self.calib_duration)
        self._calibration_countdown_step(countdown_duration)
    
    def _calibration_countdown_step(self, remaining_seconds):
        """Step function for calibration countdown"""
        if not self.calibration_requested:
            return
            
        if remaining_seconds > 0:
            # Send countdown notification
            self._send_notification_to_all_screens("info", 
                f"Calibration starts in {remaining_seconds} seconds - Keep dice still!", 2.0)
            
            # Schedule next countdown step
            self.calibration_timer = self.create_timer(1.0, 
                lambda: self._calibration_countdown_step(remaining_seconds - 1))
            self.calibration_timer.cancel()  # Cancel immediately to make it one-shot
            self.calibration_timer = threading.Timer(1.0, 
                lambda: self._calibration_countdown_step(remaining_seconds - 1))
            self.calibration_timer.start()
        else:
            # Start actual calibration
            self._send_notification_to_all_screens("info", 
                f"Calibration in progress... {int(self.calib_duration)}s remaining", 1.0)
            self.get_logger().info("Starting calibration data collection")
    
    def destroy_node(self):
        """Clean shutdown"""
        self.running = False
        
        # Cancel calibration timer if active
        if self.calibration_timer is not None:
            self.calibration_timer.cancel()
            
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    
    node = IMUNode()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
