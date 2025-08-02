#!/usr/bin/env python3
"""
Launch file for Screen Media Service testing
Launches both the service and test publisher nodes
"""

from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import ExecuteProcess, TimerAction
import os


def generate_launch_description():
    """Generate launch description for screen media service test"""
    
    return LaunchDescription([
        # Launch the screen media service
        Node(
            package='DiceMaster_Central',
            executable='screen_media_service',
            name='screen_media_service',
            output='screen',
            parameters=[],
            respawn=False
        ),
        
        # Wait 2 seconds then launch the test publisher
        TimerAction(
            period=2.0,
            actions=[
                Node(
                    package='DiceMaster_Central',
                    executable='screen_media_test_publisher',
                    name='screen_media_test_publisher',
                    output='screen',
                    parameters=[],
                    respawn=False
                )
            ]
        )
    ])


if __name__ == '__main__':
    generate_launch_description()
