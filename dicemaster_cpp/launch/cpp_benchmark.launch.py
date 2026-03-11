"""Launch C++ IMU hardware + Madgwick filter + C++ chassis for benchmarking."""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('simulate', default_value='false',
                              description='Use synthetic IMU data (no hardware needed)'),

        # C++ IMU hardware node
        Node(
            package='dicemaster_cpp',
            executable='imu_hardware_cpp',
            name='imu_hardware_cpp',
            output='screen',
            parameters=[{
                'i2c_bus': 6,
                'i2c_address': 0x68,
                'polling_rate': 50.0,
                'simulate': LaunchConfiguration('simulate'),
            }]
        ),

        # Madgwick filter (existing C++ node)
        Node(
            package='imu_filter_madgwick',
            executable='imu_filter_madgwick_node',
            name='imu_filter_madgwick',
            output='screen',
            parameters=[{
                'use_mag': False,
                'gain': 0.1,
                'world_frame': 'enu',
                'publish_tf': False,
                'publish_rate': 20.0,
                'fixed_frame': 'world',
                'stateless': False,
                'reverse_tf': False,
                'constant_dt': 0.0,
                'publish_debug_topics': False,
                'remove_gravity_vector': False,
                'zeta': 0.0,
                'orientation_stddev': 0.0,
            }]
        ),

        # C++ chassis node
        Node(
            package='dicemaster_cpp',
            executable='chassis_cpp',
            name='dice_chassis_cpp',
            output='screen',
            parameters=[{
                'orientation_rate': 10.0,
                'edge_detection_frames': 2,
            }]
        ),
    ])
