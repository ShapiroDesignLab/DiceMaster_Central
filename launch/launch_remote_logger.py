"""
Launch file for DiceMaster Remote Logger
"""

from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration


def generate_launch_description():
    """Generate launch description for remote logger"""
    
    launch_nodes = []
    
    # Add launch arguments
    launch_nodes.extend([
        DeclareLaunchArgument(
            'port',
            default_value='8443',
            description='HTTPS port for remote logger web interface'
        ),
        DeclareLaunchArgument(
            'max_logs',
            default_value='1000',
            description='Maximum number of logs to keep in memory'
        ),
        DeclareLaunchArgument(
            'cert_file',
            default_value='',
            description='SSL certificate file path (optional, will generate self-signed if not provided)'
        ),
        DeclareLaunchArgument(
            'key_file',
            default_value='',
            description='SSL private key file path (optional, will generate self-signed if not provided)'
        ),
    ])
    
    # Remote Logger Node
    launch_nodes.append(
        Node(
            package='dicemaster_central',
            executable='remote_logger',
            name='remote_logger_node',
            parameters=[{
                'port': LaunchConfiguration('port'),
                'max_logs': LaunchConfiguration('max_logs'),
                'cert_file': LaunchConfiguration('cert_file'),
                'key_file': LaunchConfiguration('key_file'),
            }],
            arguments=[
                '--port', LaunchConfiguration('port'),
                '--max-logs', LaunchConfiguration('max_logs'),
                '--cert', LaunchConfiguration('cert_file'),
                '--key', LaunchConfiguration('key_file'),
            ],
            output='screen'
        )
    )
    
    return LaunchDescription(launch_nodes)
