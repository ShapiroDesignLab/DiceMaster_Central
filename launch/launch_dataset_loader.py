#!/usr/bin/env python3
"""
Launch file for Dataset Loader Service
"""

import os
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        # Launch arguments
        DeclareLaunchArgument(
            'auto_load_on_usb_disconnect',
            default_value='true',
            description='Whether to automatically load datasets when USB is disconnected'
        ),
        
        DeclareLaunchArgument(
            'log_level',
            default_value='info',
            description='Log level for the dataset loader service'
        ),
        
        # Dataset Loader Service Node
        Node(
            package='dicemaster_central',
            executable='dataset_loader_service',
            name='dataset_loader_service',
            output='screen',
            parameters=[{
                'auto_load_on_usb_disconnect': LaunchConfiguration('auto_load_on_usb_disconnect'),
            }],
            arguments=['--ros-args', '--log-level', LaunchConfiguration('log_level')],
            remappings=[
                ('/datasets', '/dice_system/datasets'),
                ('/datasets/load', '/dice_system/datasets/load'),
                ('/datasets/reload', '/dice_system/datasets/reload'),
                ('/datasets/cleanup', '/dice_system/datasets/cleanup'),
                ('/datasets/info', '/dice_system/datasets/info'),
            ]
        ),
    ])
