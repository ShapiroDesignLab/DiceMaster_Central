#!/usr/bin/env python3
"""
Launch file for DiceMaster Chassis and IMU system
Launches both the IMU node and chassis node together for complete robot state management
"""
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare
import os


def generate_launch_description():
    # Declare launch arguments
    launch_nodes = []
    
    launch_nodes.extend([
        DeclareLaunchArgument(
            'calibration_duration',
            default_value='3.0',
            description='IMU calibration duration in seconds'
        ),
        DeclareLaunchArgument(
            'process_noise',
            default_value='0.001',
            description='Kalman filter process noise'
        ),
        DeclareLaunchArgument(
            'measurement_noise',
            default_value='1.0',
            description='Kalman filter measurement noise'
        ),
        DeclareLaunchArgument(
            'publishing_rate',
            default_value='50.0',
            description='Publishing rate in Hz for both IMU and chassis'
        ),
        DeclareLaunchArgument(
            'raw_imu_topic',
            default_value='/imu/raw',
            description='Topic name for raw IMU data'
        ),
        DeclareLaunchArgument(
            'urdf_path',
            default_value='/home/dice/DiceMaster/DiceMaster_Central/resource/dice.urdf',
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
            'auto_start_rviz',
            default_value='true',
            description='Automatically start RViz for visualization'
        ),
    ])
    
    # Dice IMU Node
    launch_nodes.append(
        Node(
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
    )
    
    # Dice Chassis Node
    launch_nodes.append(
        Node(
            package='dicemaster_central',
            executable='chassis_node',
            name='dice_chassis_node',
            parameters=[{
                'urdf_path': LaunchConfiguration('urdf_path'),
                'base_frame': LaunchConfiguration('base_frame'),
                'imu_frame': LaunchConfiguration('imu_frame'),
                'world_frame': LaunchConfiguration('world_frame'),
                'publish_rate': LaunchConfiguration('publishing_rate'),
            }],
            output='screen'
        )
    )
    
    # Robot State Publisher (publishes robot model from URDF)
    launch_nodes.append(
        Node(
            package='robot_state_publisher',
            executable='robot_state_publisher',
            name='dice_robot_state_publisher',
            parameters=[{
                'robot_description': open(LaunchConfiguration('urdf_path').perform(None)).read()
            }],
            output='screen'
        )
    )
    
    # Joint State Publisher (for joint states if needed)
    launch_nodes.append(
        Node(
            package='joint_state_publisher',
            executable='joint_state_publisher',
            name='dice_joint_state_publisher',
            output='screen'
        )
    )
    
    # RViz for visualization (conditional)
    from launch.conditions import IfCondition
    launch_nodes.append(
        Node(
            package='rviz2',
            executable='rviz2',
            name='rviz2',
            arguments=['-d', '/home/dice/DiceMaster/DiceMaster_Central/resource/dice_visualization.rviz'],
            output='screen',
            condition=IfCondition(LaunchConfiguration('auto_start_rviz'))
        )
    )
    
    return LaunchDescription(launch_nodes)


if __name__ == '__main__':
    generate_launch_description()
