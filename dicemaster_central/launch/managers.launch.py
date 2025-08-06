#!/usr/bin/env python3
"""
Launch script for the DiceMaster Game Manager

This launch file starts the game manager which handles:
1. Game discovery and loading
2. Strategy management and lifecycle
3. Game control service (/game_control)

Usage:
  ros2 launch dicemaster_central managers.launch.py

Services:
  - /game_control - Control games (start, stop, list, restart)
"""

from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    
    # Game Manager Node
    game_manager_node = Node(
        package='dicemaster_central',
        executable='game_manager.py',
        name='game_manager',
        output='screen',
        parameters=[{
            # Parameters loaded from dice_config automatically
        }]
    )

    print("Launching Managers")
    
    return LaunchDescription([
        game_manager_node,
    ])
