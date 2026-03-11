#!/usr/bin/env python3
"""Launch file for DiceMaster Chassis node (C++, TF2-free)."""
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument(
            'orientation_rate',
            default_value='10.0',
            description='Orientation detection rate in Hz'
        ),
        Node(
            package='dicemaster_cpp',
            executable='chassis_cpp',
            name='dice_chassis_cpp',
            output='screen',
            parameters=[{
                'orientation_rate': LaunchConfiguration('orientation_rate'),
                'edge_detection_frames': 2,
            }],
        ),
    ])
