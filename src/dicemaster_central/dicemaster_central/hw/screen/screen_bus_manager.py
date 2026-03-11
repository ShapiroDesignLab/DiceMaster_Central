"""
Screen Bus Manager - Manages SPI communication for screens on a single bus
Handles concurrent transfers, message queuing, and GIF playback

U-M Shapiro Design Lab
Daniel Hou @2024
"""

import itertools
import threading
import time
from queue import Empty, PriorityQueue
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

from rclpy.node import Node
from dicemaster_central_msgs.msg import ScreenMediaCmd

from .screen import Screen
from .spi_device import SPIDevice

from dicemaster_central.config import dice_config, ScreenConfig
from dicemaster_central.constants import MessagePriority
from dicemaster_central.media_typing.protocol import ProtocolMessage


_sequence_counter = itertools.count()


@dataclass
class QueuedMessage:
    """Message in the transmission queue"""
    screen_id: int
    message: ProtocolMessage
    priority: int = 5  # Lower number = higher priority
    sequence: int = field(default_factory=lambda: next(_sequence_counter))

    def __lt__(self, other):
        if self.priority != other.priority:
            return self.priority < other.priority
        return self.sequence < other.sequence

class ScreenBusManager(Node):
    """
    Manages a single SPI bus with multiple screens.
    Handles message queuing, transmission, and GIF playback.
    """
    
    def __init__(self,
        bus_id: int,
    ):
        # Initialize ROS2 node first
        super().__init__(f'screen_bus_manager_{bus_id}')
        
        self.bus_id = bus_id

        # Get configuration from hardcoded config
        self.bus_config = dice_config.bus_configs[bus_id]
        self.spi_config = dice_config.spi_config
        self.global_settings = dice_config.global_screen_config
        
        # Filter screen configs for this bus
        self.screen_configs: Dict[int, ScreenConfig] = {
            cfg.id: cfg for cfg in dice_config.screen_configs.values() if cfg.bus_id == bus_id
        }

        # SPI devices for each screen on this bus
        self.spi_device = SPIDevice(
            bus_id=self.bus_id,
            bus_dev_id=self.bus_config.use_dev,
            spi_config=self.spi_config,
            verbose=False
        )

        self.screens: Dict[int, Screen] = {
            screen_config.id: Screen(
                node=self,
                screen_id=screen_config.id,
                bus_manager=self,
            ) for screen_config in self.screen_configs.values()
        }  # screen_id -> Screen instance
        
        self.screen_cmd_subs = {
            screen_id: self.create_subscription(
                ScreenMediaCmd,
                f'/screen_{screen_id}_cmd',
                self._handle_media_command,
                10  # QoS depth
            )
            for screen_id in self.screen_configs.keys()
        }

        # Message queue
        self.message_queue = PriorityQueue()

        # Threading
        self.running = False
        self.transmission_thread = None

        # Statistics
        self.stats = {
            'messages_sent': 0,
            'messages_failed': 0,
            'bytes_transmitted': 0,
            'last_activity': time.time()
        }

    def start(self):
        """Start the bus manager threads"""
        if self.running:
            return
        
        self.running = True
        
        # Start transmission thread
        self.transmission_thread = threading.Thread(target=self._transmission_worker, daemon=True)
        self.transmission_thread.start()
        
        self.get_logger().info(f"Started bus manager for bus {self.bus_id}")

    def stop(self):
        """Stop the bus manager"""
        # Join threads
        if self.transmission_thread and self.transmission_thread.is_alive():
            self.transmission_thread.join(timeout=2.0)
        
        # Close SPI devices
        del self.spi_device
        while not self.message_queue.empty():
            try:
                self.message_queue.get_nowait()
            except Empty:
                break # Queue is now empty
                    
        # Mark as stopped
        self.running = False
        self.get_logger().info(f"Stopped bus manager for bus {self.bus_id}")
    
    def _handle_media_command(self, msg: ScreenMediaCmd):
        """Convert a ScreenMediaCmd message into a media request and send to respective screen"""
        screen_id = msg.screen_id
        if screen_id not in self.screens.keys():
            self.get_logger().error(f"Invalid screen ID {screen_id} in media command")
            return
        screen = self.screens[screen_id]
        screen.queue_media_request(msg)

    def queue_protocol_message(self, screen_id: int, message: ProtocolMessage, priority: int = MessagePriority.NORMAL) -> bool:
        """Queue a protocol message for transmission"""
        if screen_id not in self.screen_configs.keys():
            self.get_logger().warn(f"Invalid screen ID {screen_id} for bus {self.bus_id}")
            return False
        # Add to queue
        self.message_queue.put(
            QueuedMessage(
                screen_id=screen_id,
                message=message,
                priority=priority
            )
        )
        return True
    
    def _transmission_worker(self):
        """Worker thread for transmitting messages"""
        self.get_logger().debug(f"Transmission worker started for bus {self.bus_id}")
        
        while self.running:
            try:
                # Get next message with timeout
                queued_msg = self.message_queue.get(timeout=1.0)

                # Send and log
                self.spi_device.send(queued_msg.message.payload)
                self.stats['messages_sent'] += 1
                self.stats['bytes_transmitted'] += len(queued_msg.message.payload)
            
            except Empty:
                # No messages to process
                continue
            except Exception as e:
                self.get_logger().error(f"Error in transmission worker: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Get bus manager statistics"""
        stats = self.stats.copy()
        stats['queue_size'] = self.message_queue.qsize()
        stats['screens'] = list(self.screen_configs.keys())
        return stats

    def destroy_node(self):
        """Override destroy to ensure proper cleanup"""
        self.stop()
        super().destroy_node()


def main(args=None):
    """Main function for standalone screen bus manager"""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: screen_bus_manager.py <bus_id>")
        sys.exit(1)
    
    try:
        bus_id = int(sys.argv[1])
    except ValueError:
        print(f"Invalid bus_id: {sys.argv[1]}. Must be an integer.")
        sys.exit(1)
    
    import rclpy
    from rclpy.executors import MultiThreadedExecutor
    
    rclpy.init(args=args)
    
    bus_manager = None
    executor = None
    try:
        bus_manager = ScreenBusManager(bus_id)
        bus_manager.start()
        
        bus_manager.get_logger().info(f"Starting ScreenBusManager for bus {bus_id}")
        
        # Use multithreaded executor
        executor = MultiThreadedExecutor()
        executor.add_node(bus_manager)
        executor.spin()
        
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Error running screen bus manager for bus {bus_id}: {e}")
    finally:
        if bus_manager is not None:
            bus_manager.destroy_node()
        if executor is not None:
            executor.shutdown()

if __name__ == '__main__':
    main()
