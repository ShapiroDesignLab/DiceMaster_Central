"""
Screen Media Service - Optimized ROS2 node for handling screen media requests
Uses topic subscription for maximum performance and JSON-based text configuration

U-M Shapiro Design Lab
Daniel Hou @2024
"""
import time
from typing import Dict

import rclpy
from rclpy.node import Node
from DiceMaster_Central.msg import ScreenMediaCmd
from .screen_bus_manager import ScreenBusManager
from .screen import Screen
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

        # Create bus managers
        self.spi_buses = dice_config.active_spi_controllers
        self.bus_managers = {
            bus_id: ScreenBusManager(bus_id, self) for bus_id in self.spi_buses
        }

        # Create all screens
        self.screens: Dict[int, Screen] = {
            screen_config.id: Screen(
                node=self,
                screen_id=screen_config.id,
                bus_manager=self.bus_managers[screen_config.bus_id],
                using_rotation=self.global_config.auto_rotate,
                rotation_margin=self.global_config.rotation_margin
            ) for screen_config in self.screen_configs
        }  # screen_id -> Screen instance

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
        """Convert a ScreenMediaCmd message into a media request and send to respective screen"""
        screen_id = msg.screen_id
        if screen_id not in self.screens.keys():
            self.get_logger().error(f"Invalid screen ID {screen_id} in media command")
            return
        screen = self.screens[screen_id]
        screen.queue_media_request(msg)

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
