"""
Screen Media Service - Optimized ROS2 node for handling screen media requests
Uses topic subscription for maximum performance and JSON-based text configuration

U-M Shapiro Design Lab
Daniel Hou @2024
"""

import threading
import time
from queue import Queue
from typing import Dict, List, Any

import rclpy
from rclpy.node import Node
from DiceMaster_Central.msg import ScreenMediaCmd

from DiceMaster_Central.config.dice_config import DiceConfigSubscriber
from DiceMaster_Central.hw.screen_bus_manager import ScreenBusManager


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
        self.config_subscriber = DiceConfigSubscriber(self, self._on_config_update)
        self.screen_configs = []
        self.spi_config = None
        self.global_settings = None
        
        # Bus managers - one per SPI bus for concurrent operation
        self.bus_managers: Dict[int, ScreenBusManager] = {}
        self.screen_to_bus_map: Dict[int, int] = {}  # screen_id -> bus_id

        # Processing threads
        self.running = True
        
        # Subscribe to media commands
        self.media_subscription = self.create_subscription(
            ScreenMediaCmd,
            '/screen_media_cmd',
            self._handle_media_command,
            10  # QoS depth
        )
        
        # Wait for configuration before starting
        self._wait_for_config()
        
        # Start processing
        self.processing_thread.start()
        
        self.get_logger().info("ScreenMediaService initialized and ready")

    def _wait_for_config(self, timeout: float = 30.0):
        """Wait for configuration to be available"""
        start_time = time.time()
        while not self.config_subscriber.is_config_available():
            if time.time() - start_time > timeout:
                self.get_logger().error("Timeout waiting for configuration")
                raise RuntimeError("Configuration not available")
            
            # rclpy.spin_once(self, timeout_sec=0.1)
            time.sleep(0.1)
        
        self.get_logger().info("Configuration received")

    def _on_config_update(self, config: Dict[str, Any]):
        """Handle configuration updates"""
        try:
            self.screen_configs = self.config_subscriber.get_screen_configs()
            self.spi_config = self.config_subscriber.get_spi_config()
            self.global_settings = self.config_subscriber.get_global_settings()
            
            # Initialize bus managers
            self._initialize_bus_managers()
            
            self.get_logger().info(f"Configuration updated: {len(self.screen_configs)} screens configured")

        except Exception as e:
            self.get_logger().error(f"Error processing configuration update: {e}")

    def _initialize_bus_managers(self):
        """Initialize bus managers for each unique SPI bus"""
        if not self.screen_configs or not self.spi_config:
            return
        
        # Group screens by bus_id
        bus_to_screens: Dict[int, List] = {}
        self.screen_to_bus_map.clear()
        
        for screen_config in self.screen_configs:
            bus_id = screen_config.bus_id
            if bus_id not in bus_to_screens:
                bus_to_screens[bus_id] = []
            bus_to_screens[bus_id].append(screen_config)
            self.screen_to_bus_map[screen_config.id] = bus_id
        
        # Create bus managers
        for bus_id, screens in bus_to_screens.items():
            if bus_id in self.bus_managers:
                continue
            self.bus_managers[bus_id] = ScreenBusManager(
                bus_id=bus_id,
                screen_configs=screens,
                spi_config=self.spi_config,
                global_settings=self.global_settings,
                node=self
            )
            self.bus_managers[bus_id].start()
            self.get_logger().info(f"Initialized bus manager for bus {bus_id} with {len(screens)} screens")

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
