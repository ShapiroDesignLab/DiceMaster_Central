#!/usr/bin/env python3
"""Launch file for DiceMaster Chassis node (TF2-free)."""
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument(
            'publish_to_topics',
            default_value='true',
            description='Enable publishing to topics'
        ),
        DeclareLaunchArgument(
            'orientation_rate',
            default_value='10.0',
            description='Orientation detection rate in Hz'
        ),
        Node(
            package='dicemaster_central',
            executable='chassis.py',
            name='dice_chassis_node',
            parameters=[{
                'publish_to_topics': LaunchConfiguration('publish_to_topics'),
                'orientation_rate': LaunchConfiguration('orientation_rate'),
            }],
        ),
    ])
