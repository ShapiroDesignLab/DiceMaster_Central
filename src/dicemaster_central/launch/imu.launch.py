#!/usr/bin/env python3
"""
Complete IMU launch file with hardware and filter

This launch file starts the IMU pipeline:
1. IMU Hardware Node - reads raw data from MPU6050, publishes to /imu/data_raw
2. Madgwick Filter - processes raw data, publishes filtered data to /imu/data

Motion detection is now handled by the chassis node.

Usage:
  ros2 launch dicemaster_central imu_complete.launch.py

Topics:
  - /imu/data_raw - Raw IMU data from hardware
  - /imu/data - Filtered IMU data with orientation
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    
    # Declare launch arguments for Madgwick filter
    use_mag_arg = DeclareLaunchArgument(
        'use_mag',
        default_value='false',
        description='Use magnetometer data for orientation estimation'
    )
    
    gain_arg = DeclareLaunchArgument(
        'gain',
        default_value='0.1',
        description='Madgwick filter gain (higher = faster convergence, more noise)'
    )
    
    world_frame_arg = DeclareLaunchArgument(
        'world_frame',
        default_value='enu',
        description='World frame orientation (enu, ned, nwu)'
    )
    
    # IMU Hardware Node (C++)
    imu_hardware_node = Node(
        package='dicemaster_cpp',
        executable='imu_hardware_cpp',
        name='imu_hardware_cpp',
        output='screen',
        parameters=[{
            'i2c_bus': 6,
            'i2c_address': 0x68,
            'polling_rate': 50.0,
        }]
    )
    
    # Madgwick Filter Node
    imu_filter_node = Node(
        package='imu_filter_madgwick',
        executable='imu_filter_madgwick_node',
        name='imu_filter_madgwick',
        output='screen',
        parameters=[{
            'use_mag': LaunchConfiguration('use_mag'),
            'gain': LaunchConfiguration('gain'),
            'world_frame': LaunchConfiguration('world_frame'),
            'publish_tf': False,
            'publish_rate': 20.0,
            'fixed_frame': 'world',
            'stateless': False,
            'reverse_tf': False,
            'constant_dt': 0.0,  # Use IMU timestamp
            'publish_debug_topics': False,
            'remove_gravity_vector': False,
            'yaw_offset': 0.0,
            'declination': 0.0,
            'zeta': 0.0,  # Gyro drift bias gain
            'mag_bias_x': 0.0,
            'mag_bias_y': 0.0,
            'mag_bias_z': 0.0,
            'orientation_stddev': 0.0,
        }]
    )
    
    print("Launching IMU")

    return LaunchDescription([
        # Launch arguments
        use_mag_arg,
        gain_arg,
        world_frame_arg,

        # Nodes
        imu_hardware_node,
        imu_filter_node,
    ])
