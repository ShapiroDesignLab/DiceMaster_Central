from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.substitutions import LaunchConfiguration
from launch.launch_description_sources import PythonLaunchDescriptionSource
from ament_index_python.packages import get_package_share_directory
import os


def generate_launch_description():
    # Screen configuration - each screen gets its own node
    # Format: (screen_id, bus_num, dev_num)
    screen_configs = [
        (1, 0, 0),  # Screen 1 on bus 0, device 0
        (2, 0, 1),  # Screen 2 on bus 0, device 1  
        (3, 1, 0),  # Screen 3 on bus 1, device 0
        (4, 1, 1),  # Screen 4 on bus 1, device 1
        (5, 2, 0),  # Screen 5 on bus 2, device 0
        (6, 2, 1),  # Screen 6 on bus 2, device 1
    ]
    
    launch_nodes = []
    
    # Add launch arguments
    launch_nodes.extend([
        DeclareLaunchArgument(
            'calibration_duration',
            default_value='3.0',
            description='Calibration duration in seconds'
        ),
        DeclareLaunchArgument(
            'roll_offset',
            default_value='0.0',
            description='Roll offset in radians'
        ),
        DeclareLaunchArgument(
            'pitch_offset',
            default_value='0.0',
            description='Pitch offset in radians'
        ),
        DeclareLaunchArgument(
            'yaw_offset',
            default_value='0.0',
            description='Yaw offset in radians'
        ),
        DeclareLaunchArgument(
            'mpu6050_topic',
            default_value='/imu',
            description='Topic name for MPU6050 driver output'
        ),
        DeclareLaunchArgument(
            'process_noise',
            default_value='0.01',
            description='Kalman filter process noise'
        ),
        DeclareLaunchArgument(
            'measurement_noise',
            default_value='0.1',
            description='Kalman filter measurement noise'
        ),
        DeclareLaunchArgument(
            'auto_rotate',
            default_value='true',
            description='Enable auto-rotation for screens'
        ),
        DeclareLaunchArgument(
            'rotation_margin',
            default_value='0.2',
            description='Margin for auto-rotation triggering'
        ),
    ])
    
    # Include MPU6050 driver launch file
    launch_nodes.append(
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource([
                os.path.join(
                    get_package_share_directory('mpu6050driver'),
                    'launch',
                    'mpu6050driver_launch.py'
                )
            ])
        )
    )
    
    # Dice IMU Node
    launch_nodes.append(
        Node(
            package='dicemaster_central',
            executable='imu_node',
            name='dice_imu_node',
            parameters=[{
                'calibration_duration': LaunchConfiguration('calibration_duration'),
                'roll_offset': LaunchConfiguration('roll_offset'),
                'pitch_offset': LaunchConfiguration('pitch_offset'),
                'yaw_offset': LaunchConfiguration('yaw_offset'),
                'mpu6050_topic': LaunchConfiguration('mpu6050_topic'),
                'process_noise': LaunchConfiguration('process_noise'),
                'measurement_noise': LaunchConfiguration('measurement_noise'),
            }],
            output='screen'
        )
    )
    
    # Robot State Publisher for URDF
    launch_nodes.append(
        Node(
            package='robot_state_publisher',
            executable='robot_state_publisher',
            name='dice_robot_state_publisher',
            parameters=[{
                'robot_description': open(
                    '/home/dice/DiceMaster/DiceMaster_Central/resources/dice.urdf'
                ).read()
            }],
            output='screen'
        )
    )
    
    # Create individual screen nodes
    for screen_id, bus_num, dev_num in screen_configs:
        launch_nodes.append(
            Node(
                package='dicemaster_central',
                executable='screen_node',
                name=f'screen_{screen_id}_node',
                arguments=[
                    str(screen_id),
                    str(bus_num), 
                    str(dev_num),
                    LaunchConfiguration('auto_rotate'),
                    LaunchConfiguration('rotation_margin')
                ],
                output='screen'
            )
        )
    
    return LaunchDescription(launch_nodes)
