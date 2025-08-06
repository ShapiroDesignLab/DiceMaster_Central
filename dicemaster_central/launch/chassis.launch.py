#!/usr/bin/env python3
"""
Launch file for DiceMaster Chassis system
Launches the chassis node and robot state publisher for robot description and TF management
"""
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch.conditions import IfCondition
from launch_ros.actions import Node


def generate_launch_description():
    # Declare launch arguments
    launch_nodes = []
    
    launch_nodes.extend([
        DeclareLaunchArgument(
            'urdf_path',
            default_value='/home/dice/DiceMaster/DiceMaster_Central/dicemaster_central/resource/dice.urdf',
            description='Path to the dice URDF file'
        ),
        DeclareLaunchArgument(
            'publish_rate',
            default_value='50.0',
            description='Publishing rate in Hz for chassis'
        ),
        DeclareLaunchArgument(
            'publish_to_topics',
            default_value='true',
            description='Enable publishing to topics'
        ),
    ])
    
    # Dice Chassis Node
    launch_nodes.append(
        Node(
            package='dicemaster_central',
            executable='chassis.py',
            name='dice_chassis_node',
            parameters=[{
                'publish_rate': LaunchConfiguration('publish_rate'),
                'publish_to_topics': LaunchConfiguration('publish_to_topics'),
            }],
        )
    )
    
    # Robot State Publisher (publishes robot model from URDF)
    # Read URDF file content
    urdf_file_path = '/home/dice/DiceMaster/DiceMaster_Central/dicemaster_central/resource/dice.urdf'
    with open(urdf_file_path, 'r', encoding='utf-8') as urdf_file:
        robot_description_content = urdf_file.read()
    
    launch_nodes.append(
        Node(
            package='robot_state_publisher',
            executable='robot_state_publisher',
            name='dice_robot_state_publisher',
            parameters=[{
                'robot_description': robot_description_content
            }],
            output='screen'
        )
    )

    print("Launching Chassis")
    
    return LaunchDescription(launch_nodes)


if __name__ == '__main__':
    generate_launch_description()
