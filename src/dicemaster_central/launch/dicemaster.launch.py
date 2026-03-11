from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.substitutions import LaunchConfiguration
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.conditions import IfCondition
from ament_index_python.packages import get_package_share_directory
import os


def generate_launch_description():
    launch_nodes = []
    
    # Get package share directory
    pkg_share = get_package_share_directory('dicemaster_central')
    
    # # Add launch arguments
    # launch_nodes.extend([
    #     DeclareLaunchArgument(
    #         'enable_remote_logger',
    #         default_value='true',
    #         description='Enable remote logger for web-based log viewing'
    #     ),
    #     DeclareLaunchArgument(
    #         'remote_logger_port',
    #         default_value='8443',
    #         description='HTTPS port for remote logger web interface'
    #     ),
    # ])
    
    # 1. Include IMU launch file
    launch_nodes.append(
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource([
                os.path.join(pkg_share, 'launch', 'imu.launch.py')
            ])
        )
    )
    
    # 2. Include Chassis launch file
    launch_nodes.append(
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource([
                os.path.join(pkg_share, 'launch', 'chassis.launch.py')
            ])
        )
    )
    
    # 3. Include Screens launch file
    launch_nodes.append(
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource([
                os.path.join(pkg_share, 'launch', 'screens.launch.py')
            ])
        )
    )
    
    # 4. Include Managers launch file
    launch_nodes.append(
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource([
                os.path.join(pkg_share, 'launch', 'managers.launch.py')
            ])
        )
    )
    
    # # 5. Include Remote Logger launch file (conditional)
    # launch_nodes.append(
    #     IncludeLaunchDescription(
    #         PythonLaunchDescriptionSource([
    #             os.path.join(pkg_share, 'launch', 'remote_logger.launch.py')
    #         ]),
    #         launch_arguments={
    #             'port': LaunchConfiguration('remote_logger_port'),
    #         }.items(),
    #         condition=IfCondition(LaunchConfiguration('enable_remote_logger'))
    #     )
    # )
    
    return LaunchDescription(launch_nodes)
