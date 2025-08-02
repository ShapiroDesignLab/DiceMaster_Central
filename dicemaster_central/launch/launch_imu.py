#!/usr/bin/env python3
"""
Launch file for DiceMaster IMU node
"""
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

def generate_launch_description():
    # Declare launch arguments
    calibration_duration_arg = DeclareLaunchArgument(
        'calibration_duration',
        default_value='3.0',
        description='Calibration duration in seconds'
    )
    
    process_noise_arg = DeclareLaunchArgument(
        'process_noise',
        default_value='0.001',
        description='Process noise for Kalman filter'
    )
    
    measurement_noise_arg = DeclareLaunchArgument(
        'measurement_noise',
        default_value='1.0',
        description='Measurement noise for Kalman filter'
    )
    
    raw_imu_topic_arg = DeclareLaunchArgument(
        'raw_imu_topic',
        default_value='/imu/raw',
        description='Topic name for raw IMU data (custom message)'
    )
    
    publishing_rate_arg = DeclareLaunchArgument(
        'publishing_rate',
        default_value='30.0',
        description='Publishing rate in Hz'
    )
    
    # Define the IMU node
    imu_node = Node(
        package='dicemaster_central',
        executable='imu_node',
        name='dice_imu_node',
        parameters=[{
            'calibration_duration': LaunchConfiguration('calibration_duration'),
            'process_noise': LaunchConfiguration('process_noise'),
            'measurement_noise': LaunchConfiguration('measurement_noise'),
            'raw_imu_topic': LaunchConfiguration('raw_imu_topic'),
            'publishing_rate': LaunchConfiguration('publishing_rate'),
        }],
        output='screen'
    )
    
    return LaunchDescription([
        calibration_duration_arg,
        process_noise_arg,
        measurement_noise_arg,
        raw_imu_topic_arg,
        publishing_rate_arg,
        imu_node
    ])
