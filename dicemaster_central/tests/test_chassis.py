#!/usr/bin/env python3
"""
Test script for DiceMaster Chassis Node
Tests the chassis functionality including pose subscription and screen orientation detection
"""

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Pose, Quaternion
from std_msgs.msg import String
import time
import math
from scipy.spatial.transform import Rotation as R
import sys


class ChassisTestNode(Node):
    """Test node for chassis functionality"""
    
    def __init__(self):
        super().__init__('chassis_test_node')
        
        # Publisher to simulate IMU pose
        self.pose_pub = self.create_publisher(Pose, '/dice_hw/imu/pose', 10)
        
        # Subscriber to robot description
        self.robot_description_sub = self.create_subscription(
            String, '/robot_description', self.robot_description_callback, 10)
        
        # Timer for publishing test poses
        self.timer = self.create_timer(2.0, self.publish_test_pose)
        
        # Test state
        self.test_count = 0
        self.robot_description_received = False
        
        self.get_logger().info('Chassis test node initialized')
        
    def robot_description_callback(self, msg):
        """Callback for robot description"""
        if not self.robot_description_received:
            self.robot_description_received = True
            self.get_logger().info(f'Received robot description: {len(msg.data)} characters')
            
            # Check if URDF contains expected content
            if 'dice_master' in msg.data and 'screen_1_link' in msg.data:
                self.get_logger().info('✓ Robot description contains expected dice model')
            else:
                self.get_logger().error('✗ Robot description missing expected content')
    
    def publish_test_pose(self):
        """Publish test poses to simulate different dice orientations"""
        poses = [
            # Identity (no rotation)
            {'name': 'Identity', 'euler': [0, 0, 0]},
            
            # Screen 1 facing up (top face)
            {'name': 'Screen 1 Up', 'euler': [0, 0, 0]},
            
            # Screen 2 facing up (right face) - rotate around X axis
            {'name': 'Screen 2 Up', 'euler': [math.pi/2, 0, 0]},
            
            # Screen 3 facing up (back face) - rotate around Y axis
            {'name': 'Screen 3 Up', 'euler': [0, -math.pi/2, 0]},
            
            # Screen 4 facing up (left face) - rotate around X axis
            {'name': 'Screen 4 Up', 'euler': [-math.pi/2, 0, 0]},
            
            # Screen 5 facing up (front face) - rotate around Y axis
            {'name': 'Screen 5 Up', 'euler': [0, math.pi/2, 0]},
            
            # Screen 6 facing up (bottom face) - rotate 180 around X axis
            {'name': 'Screen 6 Up', 'euler': [math.pi, 0, 0]},
        ]
        
        if self.test_count < len(poses):
            test_pose = poses[self.test_count]
            
            # Convert Euler angles to quaternion
            r = R.from_euler('xyz', test_pose['euler'])
            q = r.as_quat()  # [x, y, z, w]
            
            # Create and publish pose message
            pose_msg = Pose()
            pose_msg.position.x = 0.0
            pose_msg.position.y = 0.0
            pose_msg.position.z = 0.0
            pose_msg.orientation.x = q[0]
            pose_msg.orientation.y = q[1]
            pose_msg.orientation.z = q[2]
            pose_msg.orientation.w = q[3]
            
            self.pose_pub.publish(pose_msg)
            
            self.get_logger().info(f'Published test pose: {test_pose["name"]} '
                                 f'euler={test_pose["euler"]}, q=({q[3]:.3f}, {q[0]:.3f}, {q[1]:.3f}, {q[2]:.3f})')
            
            self.test_count += 1
        else:
            # Cycle through poses
            self.test_count = 0
    
    def destroy_node(self):
        """Clean shutdown"""
        self.get_logger().info('Shutting down chassis test node')
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    
    print("DiceMaster Chassis Test")
    print("=" * 50)
    print("This test will:")
    print("1. Check if robot description is published")
    print("2. Simulate different dice orientations")
    print("3. Test pose publishing to /dice_hw/imu/pose")
    print()
    print("Make sure to run the chassis node first:")
    print("  ros2 run dicemaster_central chassis_node")
    print()
    print("You can also visualize in RViz:")
    print("  ros2 launch dicemaster_central launch_chassis.py")
    print()
    
    node = ChassisTestNode()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
