"""
Screen Bus Manager - Manages SPI communication for screens on a single bus
Handles concurrent transfers, message queuing, and GIF playback

U-M Shapiro Design Lab
Daniel Hou @2024
"""

import threading
import time
from queue import Empty, PriorityQueue
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

from dicemaster_central.config import dice_config
from dicemaster_central.constants import MessagePriority
from dicemaster_central.media_typing.protocol import ProtocolMessage
from .spi_device import SPIDevice

@dataclass
class QueuedMessage:
    """Message in the transmission queue"""
    screen_id: int
    message: ProtocolMessage
    priority: int = 5  # Lower number = higher priority
    timestamp: float = field(default_factory=time.time)
    
    def __lt__(self, other):
        # For priority queue sorting
        if self.priority != other.priority:
            return self.priority < other.priority
        return self.timestamp < other.timestamp


class ScreenBusManager:
    """
    Manages a single SPI bus with multiple screens.
    Handles message queuing, transmission, and GIF playback.
    """
    
    def __init__(self,
        bus_id: int,
        node
    ):
        self.bus_id = bus_id
        self.node = node
        
        # Get configuration from hardcoded config
        self.spi_config = dice_config.spi_config
        self.global_settings = dice_config.global_screen_config
        
        # Filter screen configs for this bus
        bus_screen_configs = [cfg for cfg in dice_config.screen_configs if cfg.bus_id == bus_id]
        self.screen_configs = {cfg.id: cfg for cfg in bus_screen_configs}
        
        # SPI devices for each screen on this bus
        self.spi_devices: Dict[int, SPIDevice] = {
            screen_id: SPIDevice(
                bus_id=screen_config.bus_id,
                bus_dev_id=screen_config.bus_dev_id,
                spi_config=self.spi_config,
                verbose=False
            )
            for screen_id, screen_config in self.screen_configs.items()
        }

        # Message queue and transmission
        self.message_queue = PriorityQueue()
        self.transmission_lock = threading.Lock()  # Only one device can use SPI at a time\
        self.last_screen_id = -1
        
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
        
        self.node.get_logger().info(f"Started bus manager for bus {self.bus_id}")

    def stop(self):
        """Stop the bus manager"""
        self.running = False
        
        # Join threads
        if self.transmission_thread and self.transmission_thread.is_alive():
            self.transmission_thread.join(timeout=2.0)
        
        # Close SPI devices
        for spi_device in self.spi_devices.values():
            spi_device.down()
        
        self.node.get_logger().info(f"Stopped bus manager for bus {self.bus_id}")

    def queue_protocol_message(self, screen_id: int, message: ProtocolMessage, priority: int = MessagePriority.NORMAL) -> bool:
        """Queue a protocol message for transmission"""
        if screen_id not in self.screen_configs:
            self.node.get_logger().warn(f"Invalid screen ID {screen_id} for bus {self.bus_id}")
            return False

        # Create queued message
        queued_msg = QueuedMessage(
            screen_id=screen_id,
            message=message,
            priority=priority
        )
        
        # Add to queue
        self.message_queue.put(queued_msg)
        
        return True
    
    def _transmission_worker(self):
        """Worker thread for transmitting messages"""
        self.node.get_logger().debug(f"Transmission worker started for bus {self.bus_id}")
        
        while self.running:
            try:
                # Get next message with timeout
                queued_msg = self.message_queue.get(timeout=1.0)
                
                # Transmit the message
                success = self._transmit_message(queued_msg)
                
                if success:
                    self.stats['messages_sent'] += 1
                    self.stats['bytes_transmitted'] += len(queued_msg.message.payload)
                else:
                    self.stats['messages_failed'] += 1
                    self.node.get_logger().warn(f"Failed to transmit message to screen {queued_msg.screen_id}")
                
                self.stats['last_activity'] = time.time()
                
                # Small delay to prevent overwhelming the bus
                time.sleep(0.001)
                
            except Empty:
                # No messages to process
                continue
            except Exception as e:
                self.node.get_logger().error(f"Error in transmission worker: {e}")

    def _transmit_message(self, queued_msg: QueuedMessage) -> bool:
        """Transmit a single message to a screen"""
        screen_id = queued_msg.screen_id
        if screen_id not in self.screen_configs.keys():
            self.node.get_logger().warn(f"Invalid screen ID {screen_id} for bus {self.bus_id}")
            return False

        spi_device = self.spi_devices[screen_id]

        try:
            # Ensure device is ready
            if self.last_screen_id != screen_id:
                # Clean old device
                old_spi_dev = self.spi_devices.get(self.last_screen_id)
                if old_spi_dev:
                    old_spi_dev.down()

            # Start new device and send
            spi_device.up()
            spi_device.send(list(queued_msg.message.payload))
            self.last_screen_id = screen_id
            return True
                
        except Exception as e:
            self.node.get_logger().error(f"SPI transmission error for screen {screen_id}: {e}")
            spi_device.down()  # Ensure device is closed
            return False

    def get_stats(self) -> Dict[str, Any]:
        """Get bus manager statistics"""
        stats = self.stats.copy()
        stats['queue_size'] = self.message_queue.qsize()
        stats['screens'] = list(self.screen_configs.keys())
        return stats
