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
            'base_frame',
            default_value='base_link',
            description='Base frame ID for the robot'
        ),
        DeclareLaunchArgument(
            'imu_frame',
            default_value='imu_link',
            description='IMU frame ID'
        ),
        DeclareLaunchArgument(
            'world_frame',
            default_value='world',
            description='World frame ID'
        ),
        DeclareLaunchArgument(
            'publish_rate',
            default_value='50.0',
            description='Publishing rate in Hz for chassis'
        ),
        DeclareLaunchArgument(
            'auto_start_rviz',
            default_value='false',
            description='Automatically start RViz for visualization'
        ),
    ])
    
    # Dice Chassis Node
    launch_nodes.append(
        Node(
            package='dicemaster_central',
            executable='chassis_node',
            name='dice_chassis_node',
            parameters=[{
                'base_frame': LaunchConfiguration('base_frame'),
                'imu_frame': LaunchConfiguration('imu_frame'),
                'world_frame': LaunchConfiguration('world_frame'),
                'publish_rate': LaunchConfiguration('publish_rate'),
                'imu_topic': '/imu/data',
                'alternative_imu_topic': '/data/imu',
            }],
            output='screen'
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
    
    # RViz for visualization (conditional)
    launch_nodes.append(
        Node(
            package='rviz2',
            executable='rviz2',
            name='rviz2',
            arguments=['-d', '/home/dice/DiceMaster/DiceMaster_Central/dicemaster_central/resource/dice_visualization.rviz'],
            output='screen',
            condition=IfCondition(LaunchConfiguration('auto_start_rviz'))
        )
    )
    
    return LaunchDescription(launch_nodes)


if __name__ == '__main__':
    generate_launch_description()
