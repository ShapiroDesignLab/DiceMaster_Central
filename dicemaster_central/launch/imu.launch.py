#!/usr/bin/env python3
"""
Complete IMU launch file with hardware, filter, and motion detection

This launch file starts the complete IMU pipeline:
1. IMU Hardware Node - reads raw data from MPU6050, publishes to /imu/data_raw
2. Madgwick Filter - processes raw data, publishes filtered data to /imu/data  
3. Motion Detector Node - analyzes filtered data for motion patterns

Usage:
  ros2 launch dicemaster_central imu_complete.launch.py

Topics:
  - /imu/data_raw - Raw IMU data from hardware
  - /imu/data - Filtered IMU data with orientation
  - /imu/motion - Motion detection results
  - /imu/motion/* - Individual motion flags
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
    
    # IMU Hardware Node
    imu_hardware_node = Node(
        package='dicemaster_central',
        executable='imu_hardware.py',
        name='imu_hardware',
        output='screen',
        parameters=[{
            # Parameters loaded from dice_config automatically
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
            'publish_tf': True,
            'fixed_frame': 'odom',
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
    
    # Motion Detector Node (commented out for now)
    motion_detector_node = Node(
        package='dicemaster_central',
        executable='motion_detector.py',
        name='motion_detector',
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
        motion_detector_node,  # Uncomment when motion detector is ready
    ])
