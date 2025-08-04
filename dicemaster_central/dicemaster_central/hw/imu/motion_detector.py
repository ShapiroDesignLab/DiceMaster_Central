"""
DiceMaster Motion Detection Node

This ROS2 node subscribes to filtered IMU data from the Madgwick filter
and detects motion patterns including rotations and shaking.

Topics:
- Subscribes to: /imu/data (sensor_msgs/Imu) - filtered IMU data from Madgwick
- Publishes to: /dice_hw/imu/motion (MotionDetection) - motion detection results
- Publishes to: /dice_hw/imu/motion/* (Bool) - individual motion flags

USAGE:
======
ros2 run dicemaster_central motion_detector_node

MOTION TYPES DETECTED:
=====================
- Axis rotations: +/- 90° around X, Y, Z axes
- Shaking: High-frequency oscillations
- Rotation intensity: Overall rotation magnitude
- Shake intensity: Overall shake magnitude  
- Stillness factor: How still the device is (1.0 = perfectly still)
"""

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Imu
from std_msgs.msg import Bool, Header

import numpy as np
from collections import deque

from dicemaster_central_msgs.msg import MotionDetection


class MotionDetector:
    """Detects various motion patterns from IMU data"""
    
    def __init__(self, history_size=50):
        self.history_size = history_size
        self.accel_history = deque(maxlen=history_size)
        self.gyro_history = deque(maxlen=history_size)
        
        # Detection thresholds
        self.rotation_threshold = 1.5  # rad/s
        self.shake_threshold = 15.0    # m/s²
        self.stillness_threshold = 0.5  # Combined motion threshold for stillness
        
    def update(self, accel, gyro):
        """Update motion detector with new data (no quaternion needed)"""
        self.accel_history.append(accel.copy())
        self.gyro_history.append(gyro.copy())
        
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


class MotionDetectorNode(Node):
    """ROS2 Node that detects motion patterns from filtered IMU data"""
    
    def __init__(self):
        super().__init__('motion_detector')
        
        # Initialize motion detector
        self.motion_detector = MotionDetector(history_size=50)
        
        # Publishers
        self.motion_pub = self.create_publisher(MotionDetection, '/dice_hw/imu/motion', 10)
        
        # Individual motion detection publishers
        self.rotation_x_pos_pub = self.create_publisher(Bool, '/dice_hw/imu/motion/rotation_x_pos', 10)
        self.rotation_x_neg_pub = self.create_publisher(Bool, '/dice_hw/imu/motion/rotation_x_neg', 10)
        self.rotation_y_pos_pub = self.create_publisher(Bool, '/dice_hw/imu/motion/rotation_y_pos', 10)
        self.rotation_y_neg_pub = self.create_publisher(Bool, '/dice_hw/imu/motion/rotation_y_neg', 10)
        self.rotation_z_pos_pub = self.create_publisher(Bool, '/dice_hw/imu/motion/rotation_z_pos', 10)
        self.rotation_z_neg_pub = self.create_publisher(Bool, '/dice_hw/imu/motion/rotation_z_neg', 10)
        self.shaking_pub = self.create_publisher(Bool, '/dice_hw/imu/motion/shaking', 10)
        
        # Subscriber to filtered IMU data from Madgwick filter
        self.imu_sub = self.create_subscription(
            Imu,
            '/imu/data',  # Filtered data from Madgwick filter
            self.imu_callback,
            10
        )
        
        self.get_logger().info("Motion Detector Node initialized - listening to /imu/data")
    
    def imu_callback(self, msg):
        """Callback for filtered IMU data from Madgwick filter"""
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
        
        # Update motion detector
        self.motion_detector.update(accel, gyro)
        
        # Get motion detection results and publish
        self._publish_motion_detection(msg.header)
    
    def _publish_motion_detection(self, original_header):
        """Publish motion detection results"""
        motion_summary = self.motion_detector.get_motion_summary()
        
        # Create motion detection message
        motion_msg = MotionDetection()
        motion_msg.header = Header()
        motion_msg.header.stamp = self.get_clock().now().to_msg()
        motion_msg.header.frame_id = original_header.frame_id
        
        motion_msg.rotation_x_positive = motion_summary['rotation_x_pos']
        motion_msg.rotation_x_negative = motion_summary['rotation_x_neg']
        motion_msg.rotation_y_positive = motion_summary['rotation_y_pos']
        motion_msg.rotation_y_negative = motion_summary['rotation_y_neg']
        motion_msg.rotation_z_positive = motion_summary['rotation_z_pos']
        motion_msg.rotation_z_negative = motion_summary['rotation_z_neg']
        motion_msg.shaking = motion_summary['shaking']
        motion_msg.rotation_intensity = motion_summary['rotation_intensity']
        motion_msg.shake_intensity = motion_summary['shake_intensity']
        motion_msg.stillness_factor = motion_summary['stillness_factor']
        
        self.motion_pub.publish(motion_msg)
        
        # Publish individual motion flags
        self.rotation_x_pos_pub.publish(Bool(data=motion_summary['rotation_x_pos']))
        self.rotation_x_neg_pub.publish(Bool(data=motion_summary['rotation_x_neg']))
        self.rotation_y_pos_pub.publish(Bool(data=motion_summary['rotation_y_pos']))
        self.rotation_y_neg_pub.publish(Bool(data=motion_summary['rotation_y_neg']))
        self.rotation_z_pos_pub.publish(Bool(data=motion_summary['rotation_z_pos']))
        self.rotation_z_neg_pub.publish(Bool(data=motion_summary['rotation_z_neg']))
        self.shaking_pub.publish(Bool(data=motion_summary['shaking']))


def main(args=None):
    rclpy.init(args=args)
    
    node = MotionDetectorNode()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
