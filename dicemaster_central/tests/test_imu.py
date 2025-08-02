#!/usr/bin/env python3
"""
Test script for the improved IMU implementation
"""
import time
import numpy as np
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Imu
from geometry_msgs.msg import Pose, Vector3
from std_msgs.msg import String, Bool

class IMUTestNode(Node):
    """Test node for IMU functionality"""
    
    def __init__(self):
        super().__init__('imu_test_node')
        
        # Publishers for test data
        self.imu_pub = self.create_publisher(Imu, '/sensor', 10)
        
        # Subscribers to IMU outputs
        self.pose_sub = self.create_subscription(
            Pose, '/imu/pose', self.pose_callback, 10)
        self.accel_sub = self.create_subscription(
            Vector3, '/imu/accel', self.accel_callback, 10)
        self.angvel_sub = self.create_subscription(
            Vector3, '/imu/angvel', self.angvel_callback, 10)
        self.status_sub = self.create_subscription(
            String, '/imu/status', self.status_callback, 10)
            
        # Motion detection subscribers
        self.rotation_x_pos_sub = self.create_subscription(
            Bool, '/imu/motion/rotation_x_pos', 
            lambda msg: self.motion_callback('rotation_x_pos', msg), 10)
        self.shaking_sub = self.create_subscription(
            Bool, '/imu/motion/shaking',
            lambda msg: self.motion_callback('shaking', msg), 10)
        
        # Timer for publishing test data
        self.timer = self.create_timer(0.05, self.timer_callback)  # 20 Hz
        
        # Test data generation
        self.time_counter = 0
        self.test_phase = 0  # 0: stationary, 1: rotation, 2: shaking
        
        self.get_logger().info("IMU Test Node started")
        
    def timer_callback(self):
        """Generate and publish test IMU data"""
        self.time_counter += 0.05
        
        # Generate different test patterns
        if self.time_counter < 5.0:
            # Phase 0: Stationary (for calibration)
            accel = [0.0, 0.0, -9.81]  # Gravity pointing down
            gyro = [0.0, 0.0, 0.0]
            
        elif self.time_counter < 10.0:
            # Phase 1: Rotation around X-axis
            gyro_x = 1.8  # Simulating +90 degree rotation
            accel = [0.0, 0.0, -9.81]
            gyro = [gyro_x, 0.0, 0.0]
            
        elif self.time_counter < 15.0:
            # Phase 2: Shaking simulation
            shake_freq = 5.0  # 5 Hz shaking
            shake_amplitude = 20.0
            shake_x = shake_amplitude * np.sin(2 * np.pi * shake_freq * self.time_counter)
            shake_y = shake_amplitude * np.cos(2 * np.pi * shake_freq * self.time_counter)
            
            accel = [shake_x, shake_y, -9.81]
            gyro = [0.0, 0.0, 0.0]
            
        else:
            # Phase 3: Back to stationary
            accel = [0.0, 0.0, -9.81]
            gyro = [0.0, 0.0, 0.0]
            
        # Add some noise
        accel = np.array(accel) + np.random.normal(0, 0.1, 3)
        gyro = np.array(gyro) + np.random.normal(0, 0.01, 3)
        
        # Create and publish IMU message
        imu_msg = Imu()
        imu_msg.header.stamp = self.get_clock().now().to_msg()
        imu_msg.header.frame_id = 'imu_link'
        
        imu_msg.linear_acceleration.x = accel[0]
        imu_msg.linear_acceleration.y = accel[1]
        imu_msg.linear_acceleration.z = accel[2]
        
        imu_msg.angular_velocity.x = gyro[0]
        imu_msg.angular_velocity.y = gyro[1]
        imu_msg.angular_velocity.z = gyro[2]
        
        self.imu_pub.publish(imu_msg)
        
    def pose_callback(self, msg):
        """Callback for pose data"""
        quat = msg.orientation
        self.get_logger().info(
            f"Pose - Quat: w={quat.w:.3f}, x={quat.x:.3f}, y={quat.y:.3f}, z={quat.z:.3f}",
            throttle_duration_sec=1.0
        )
        
    def accel_callback(self, msg):
        """Callback for acceleration data"""
        self.get_logger().debug(
            f"Accel: x={msg.x:.3f}, y={msg.y:.3f}, z={msg.z:.3f}"
        )
        
    def angvel_callback(self, msg):
        """Callback for angular velocity data"""
        self.get_logger().debug(
            f"Gyro: x={msg.x:.3f}, y={msg.y:.3f}, z={msg.z:.3f}"
        )
        
    def status_callback(self, msg):
        """Callback for status updates"""
        self.get_logger().info(f"IMU Status: {msg.data}")
        
    def motion_callback(self, motion_type, msg):
        """Callback for motion detection"""
        if msg.data:
            self.get_logger().info(f"Motion detected: {motion_type}")

def main(args=None):
    rclpy.init(args=args)
    
    test_node = IMUTestNode()
    
    try:
        rclpy.spin(test_node)
    except KeyboardInterrupt:
        pass
    finally:
        test_node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
