"""
Screen Media Service - Optimized ROS2 node for handling screen media requests
Uses topic subscription for maximum performance and JSON-based text configuration

U-M Shapiro Design Lab
Daniel Hou @2024
"""
import time

import rclpy
from rclpy.node import Node
from dicemaster_central_msgs.msg import ScreenMediaCmd
from .screen_bus_manager import ScreenBusManager
from dicemaster_central.config import dice_config

class ScreenMediaService(Node):
    """
    Main screen media service node that:
    1. Subscribes to ScreenMediaCmd topic
    2. Processes media using media_types classes
    3. Manages multiple SPI bus managers for concurrent transfers
    4. Handles GIF looping and timing
    """
    
    def __init__(self):
        super().__init__('screen_media_service')
        
        # Configuration
        self.screen_configs = dice_config.screen_configs
        self.spi_config = dice_config.spi_config
        self.global_config = dice_config.global_screen_config

        # Create bus managers (now they are independent nodes)
        self.spi_buses = dice_config.active_spi_controllers
        self.bus_managers = {
            bus_id: ScreenBusManager(bus_id) for bus_id in self.spi_buses
        }
        for bus_manager in self.bus_managers.values():
            bus_manager.start()

        # Screens are now managed directly by their respective bus managers
        # Create a lookup for routing messages to the correct bus manager
        self.screen_to_bus_manager = {
            screen_config.id: self.bus_managers[screen_config.bus_id] 
            for screen_config in self.screen_configs.values()
        }

        # Processing threads
        self.running = True
        
        # Subscribe to media commands
        self.media_subscription = self.create_subscription(
            ScreenMediaCmd,
            '/screen_media_cmd',
            self._handle_media_command,
            10  # QoS depth
        )

        self.get_logger().info("ScreenMediaService initialized and ready")

    def _handle_media_command(self, msg):
        """Route media command to the appropriate bus manager"""
        screen_id = msg.screen_id
        if screen_id not in self.screen_to_bus_manager:
            self.get_logger().error(f"Invalid screen ID {screen_id} in media command")
            return
        
        # Route to the appropriate bus manager
        bus_manager = self.screen_to_bus_manager[screen_id]
        bus_manager._handle_media_command(msg)

    def shutdown(self):
        """Shutdown the service"""
        self.get_logger().info("Shutting down ScreenMediaService")
        self.running = False
        
        # Stop all bus managers
        for bus_manager in self.bus_managers.values():
            bus_manager.stop()

    def destroy_node(self):
        """Override destroy to ensure proper cleanup"""
        self.shutdown()
        super().destroy_node()


def main(args=None):
    """Main function for screen media service"""
    rclpy.init(args=args)
    
    try:
        service = ScreenMediaService()
        rclpy.spin(service)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Error running screen media service: {e}")
    finally:
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
