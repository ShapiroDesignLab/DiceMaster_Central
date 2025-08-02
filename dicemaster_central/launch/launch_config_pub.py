#!/usr/bin/env python3
"""
Launch file for DiceMaster Configuration Publisher
Launches the dice config publisher node with optional config file argument
"""

import os
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess
from launch.substitutions import LaunchConfiguration, PythonExpression
from launch.conditions import IfCondition, UnlessCondition
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory


def generate_launch_description():
    """Generate launch description for config publisher"""
    
    # Declare launch arguments
    config_file_arg = DeclareLaunchArgument(
        'config_file',
        default_value='',
        description='Path to configuration YAML file. If empty, uses default resource/config.yaml'
    )
    
    verbose_arg = DeclareLaunchArgument(
        'verbose',
        default_value='false',
        description='Enable verbose logging'
    )
    
    validate_only_arg = DeclareLaunchArgument(
        'validate_only',
        default_value='false',
        description='Only validate config and exit (test mode)'
    )
    
    # Get launch configurations
    config_file = LaunchConfiguration('config_file')
    verbose = LaunchConfiguration('verbose')
    validate_only = LaunchConfiguration('validate_only')
    
    # Determine the python executable and module path
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    dice_config_module = os.path.join(parent_dir, 'DiceMaster_Central', 'dice_config.py')
    
    # Config publisher node for normal operation
    config_publisher_node = Node(
        package='DiceMaster_Central',
        executable='python3',
        name='dice_config_publisher',
        arguments=[
            dice_config_module,
            'publisher',
            PythonExpression(['"--config-file ', config_file, '"']) if config_file else ""
        ],
        output='screen',
        parameters=[
            {'use_sim_time': False}
        ],
        condition=UnlessCondition(validate_only)
    )
    
    # Alternative: Execute process for more control
    config_publisher_process = ExecuteProcess(
        cmd=[
            'python3', dice_config_module, 'publisher'
        ],
        name='dice_config_publisher',
        output='screen',
        condition=UnlessCondition(validate_only)
    )
    
    # Test/validation process
    config_test_process = ExecuteProcess(
        cmd=[
            'python3', dice_config_module
        ],
        name='dice_config_test',
        output='screen',
        condition=IfCondition(validate_only)
    )
    
    # Create launch description
    ld = LaunchDescription()
    
    # Add arguments
    ld.add_action(config_file_arg)
    ld.add_action(verbose_arg) 
    ld.add_action(validate_only_arg)
    
    # Add nodes/processes
    ld.add_action(config_publisher_process)
    ld.add_action(config_test_process)
    
    return ld


def main():
    """Main function for direct execution"""
    print("DiceMaster Config Publisher Launch File")
    print("Usage examples:")
    print("  ros2 launch DiceMaster_Central launch_config_pub.py")
    print("  ros2 launch DiceMaster_Central launch_config_pub.py config_file:=/path/to/config.yaml")
    print("  ros2 launch DiceMaster_Central launch_config_pub.py validate_only:=true")


if __name__ == '__main__':
    main()