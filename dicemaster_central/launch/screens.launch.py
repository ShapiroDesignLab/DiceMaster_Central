#!/usr/bin/env python3
"""
Launch file for screen bus managers
Dynamically spawns ScreenBusManager nodes based on dice_config

U-M Shapiro Design Lab
Daniel Hou @2024
"""

from launch import LaunchDescription
from launch_ros.actions import Node
import sys

# Add the package to Python path to import config
sys.path.append('/home/dice/DiceMaster/DiceMaster_Central/dicemaster_central')

from dicemaster_central.config import dice_config


def generate_launch_description():
    """Generate launch description with screen bus manager nodes"""
    
    # Get active SPI buses from config
    active_buses = dice_config.active_spi_controllers
    
    # Get screen configs to verify which buses are actually used
    used_buses = set()
    for screen_config in dice_config.screen_configs:
        used_buses.add(screen_config.bus_id)
    
    # Only launch bus managers for buses that are both active and have screens
    buses_to_launch = set(active_buses).intersection(used_buses)
    
    nodes = []
    
    for bus_id in buses_to_launch:
        # Count screens on this bus for logging
        screens_on_bus = [cfg for cfg in dice_config.screen_configs if cfg.bus_id == bus_id]
        screen_ids = [cfg.id for cfg in screens_on_bus]
        
        # Create node for this bus
        node = Node(
            package='dicemaster_central',
            executable='screen_bus_manager',
            name=f'screen_bus_manager_{bus_id}',
            namespace='',
            parameters=[{
                'bus_id': bus_id,
            }],
            arguments=[str(bus_id)],
            output='screen',
            emulate_tty=True,
        )
        
        nodes.append(node)
        
        print(f"Launching ScreenBusManager for bus {bus_id} with screens {screen_ids}")
    
    if not nodes:
        print("Warning: No screen bus managers to launch. Check your dice_config.")
    else:
        print(f"Launching {len(nodes)} screen bus manager nodes")
    
    return LaunchDescription(nodes)


if __name__ == '__main__':
    # For testing purposes
    from dicemaster_central.config import dice_config
    
    print("=== Screen Launch Configuration ===")
    print(f"Active SPI controllers: {dice_config.active_spi_controllers}")
    print("Screen configurations:")
    for cfg in dice_config.screen_configs:
        print(f"  Screen {cfg.id}: bus={cfg.bus_id}, dev={cfg.bus_dev_id}")
    
    # Show what would be launched
    active_buses = dice_config.active_spi_controllers
    used_buses = set(cfg.bus_id for cfg in dice_config.screen_configs)
    buses_to_launch = set(active_buses).intersection(used_buses)
    
    print(f"Buses to launch: {sorted(buses_to_launch)}")
    for bus_id in sorted(buses_to_launch):
        screens = [cfg.id for cfg in dice_config.screen_configs if cfg.bus_id == bus_id]
        print(f"  Bus {bus_id}: screens {screens}")
