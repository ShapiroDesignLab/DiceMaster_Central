"""
DiceMaster Motion Detection Node

This ROS2 node subscribes to filtered IMU data from the imu_tools filter
and detects shaking motion based on acceleration and angular velocity magnitudes.

The node combines motion detection algorithms directly into the ROS2 node class
for simplicity and better performance.

Topics:
- Subscribes to: /imu/data (sensor_msgs/Imu) - filtered IMU data from imu_tools
- Publishes to: /imu/motion (MotionDetection) - motion detection results

USAGE:
======
ros2 run dicemaster_central motion_detector_node

MOTION TYPES DETECTED:
=====================
- Shaking: High-frequency oscillations in acceleration and angular velocity
- Shake intensity: Overall shake magnitude  
- Stillness factor: How still the device is (1.0 = perfectly still)
"""

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Imu
from std_msgs.msg import Header

import numpy as np
from collections import deque

from dicemaster_central_msgs.msg import MotionDetection


class MotionDetectorNode(Node):
    """ROS2 Node that detects motion patterns from filtered IMU data"""
    
    def __init__(self):
        super().__init__('motion_detector')
        
        # Motion detection parameters
        self.history_size = 50
        self.accel_magnitude_history = deque(maxlen=self.history_size)
        self.gyro_magnitude_history = deque(maxlen=self.history_size)
        
        # Detection thresholds
        self.shake_accel_threshold = 13.0    # m/s² above gravity
        self.shake_gyro_threshold = 5.0      # rad/s
        self.shake_variance_threshold = 5.0  # variance threshold for detecting oscillations
        
        # Publishers
        self.motion_pub = self.create_publisher(MotionDetection, '/imu/motion', 10)
        
        # Subscriber to filtered IMU data from imu_tools filter
        self.imu_sub = self.create_subscription(
            Imu,
            '/imu/data',  # Filtered data from imu_tools filter
            self.imu_callback,
            10
        )
        
        self.get_logger().info("Motion Detector Node initialized - listening to /imu/data for shaking detection")
    
    def update_motion_data(self, accel, gyro):
        """Update motion detector with new data - calculate and store magnitudes"""
        # Calculate magnitudes
        accel_magnitude = np.linalg.norm(accel)
        gyro_magnitude = np.linalg.norm(gyro)
        
        self.accel_magnitude_history.append(accel_magnitude)
        self.gyro_magnitude_history.append(gyro_magnitude)
        
    def detect_shaking(self):
        """Detect shaking motion based on magnitude variations"""
        # Need sufficient history
        if len(self.accel_magnitude_history) < 20 or len(self.gyro_magnitude_history) < 20:
            return False
            
        # Get recent magnitude data
        recent_accel_magnitudes = list(self.accel_magnitude_history)[-20:]
        recent_gyro_magnitudes = list(self.gyro_magnitude_history)[-20:]
        
        # For acceleration, remove gravity effect by looking at variance
        accel_std = np.std(recent_accel_magnitudes)
        
        # Check for high variation in acceleration (indicating shaking)
        accel_shake = accel_std > self.shake_variance_threshold
        
        # Check for sustained angular velocity (indicating rapid motion)
        gyro_mean = np.mean(recent_gyro_magnitudes)
        gyro_shake = gyro_mean > self.shake_gyro_threshold
        
        print("Shake vals:", gyro_shake, accel_shake)
        # Shaking detected if either acceleration variance is high or gyro activity is high
        return bool(accel_shake or gyro_shake)
    
    def get_shake_intensity(self):
        """Calculate shake intensity (0.0 to 1.0)"""
        if len(self.accel_magnitude_history) < 10 or len(self.gyro_magnitude_history) < 10:
            return 0.0
            
        # Get recent magnitude data
        recent_accel = list(self.accel_magnitude_history)[-10:]
        recent_gyro = list(self.gyro_magnitude_history)[-10:]
        
        # Calculate acceleration variation (shake indicator)
        accel_std = np.std(recent_accel)
        accel_intensity = min(accel_std / 10.0, 1.0)  # Normalize to 0-1
        
        # Calculate gyro activity (motion indicator)
        gyro_mean = np.mean(recent_gyro)
        gyro_intensity = min(gyro_mean / 5.0, 1.0)  # Normalize to 0-1
        
        # Combine both metrics
        return (accel_intensity + gyro_intensity) / 2.0
        
    def get_stillness_factor(self):
        """Calculate stillness factor (1.0 = perfectly still, 0.0 = very active)"""
        shake_intensity = self.get_shake_intensity()
        
        # Return inverse (1.0 - motion)
        return max(0.0, 1.0 - shake_intensity)
        
    def get_motion_summary(self):
        """Get summary of all detected motions"""
        return {
            'rotation_x_pos': False,  # Future feature - currently disabled
            'rotation_x_neg': False,  # Future feature - currently disabled
            'rotation_y_pos': False,  # Future feature - currently disabled
            'rotation_y_neg': False,  # Future feature - currently disabled
            'rotation_z_pos': False,  # Future feature - currently disabled
            'rotation_z_neg': False,  # Future feature - currently disabled
            'shaking': self.detect_shaking(),
            'rotation_intensity': 0.0,  # Future feature - currently disabled
            'shake_intensity': self.get_shake_intensity(),
            'stillness_factor': self.get_stillness_factor()
        }
    
    def imu_callback(self, msg):
        """Callback for filtered IMU data from imu_tools filter"""
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
        
        # Update motion data
        self.update_motion_data(accel, gyro)
        
        # Get motion detection results and publish
        self._publish_motion_detection(msg.header)
    
    def _publish_motion_detection(self, original_header):
        """Publish motion detection results"""
        motion_summary = self.get_motion_summary()
        
        # Create motion detection message
        motion_msg = MotionDetection()
        motion_msg.header = Header()
        motion_msg.header.stamp = self.get_clock().now().to_msg()
        motion_msg.header.frame_id = original_header.frame_id
        
        # Set all rotation fields to False (future feature)
        motion_msg.rotation_x_positive = motion_summary['rotation_x_pos']
        motion_msg.rotation_x_negative = motion_summary['rotation_x_neg']
        motion_msg.rotation_y_positive = motion_summary['rotation_y_pos']
        motion_msg.rotation_y_negative = motion_summary['rotation_y_neg']
        motion_msg.rotation_z_positive = motion_summary['rotation_z_pos']
        motion_msg.rotation_z_negative = motion_summary['rotation_z_neg']
        
        # Set shaking detection and intensity values
        motion_msg.shaking = motion_summary['shaking']
        motion_msg.rotation_intensity = motion_summary['rotation_intensity']
        motion_msg.shake_intensity = motion_summary['shake_intensity']
        motion_msg.stillness_factor = motion_summary['stillness_factor']

        # if motion_summary['shaking']:
        #     self.get_logger().info("Shaking dice!!!")
        
        self.motion_pub.publish(motion_msg)


def main(args=None):
    from rclpy.executors import MultiThreadedExecutor
    
    rclpy.init(args=args)
    
    node = None
    executor = None
    try:
        node = MotionDetectorNode()
        
        # Use multithreaded executor
        executor = MultiThreadedExecutor()
        executor.add_node(node)
        executor.spin()
        
    except KeyboardInterrupt:
        pass
    finally:
        if node is not None:
            node.destroy_node()
        if executor is not None:
            executor.shutdown()


if __name__ == '__main__':
    main()
