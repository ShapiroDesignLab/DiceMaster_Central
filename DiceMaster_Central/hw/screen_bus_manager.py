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

from DiceMaster_Central.config.dice_config import ScreenConfig, SPIConfig, ScreenConfigGlobal
from DiceMaster_Central.config.constants import Rotation
from DiceMaster_Central.media_typing.media_types import MotionPicture
from DiceMaster_Central.media_typing.protocol import (
    ProtocolMessage, ImageStartMessage, 
    ImageChunkMessage, ImageEndMessage
)
from DiceMaster_Central.hw.spi_device import SPIDevice


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


@dataclass
class GifPlaybackState:
    """State for GIF playback"""
    motion_picture: MotionPicture
    current_frame: int
    rotation: int
    last_frame_time: float
    loop_count: int
    active: bool = True

class ScreenBusManager:
    """
    Manages a single SPI bus with multiple screens.
    Handles message queuing, transmission, and GIF playback.
    """
    
    def __init__(self, 
                 bus_id: int,
                 screen_configs: List[ScreenConfig],
                 spi_config: SPIConfig,
                 global_settings: ScreenConfigGlobal,
                 node):
        self.bus_id = bus_id
        self.screen_configs = {cfg.id: cfg for cfg in screen_configs}
        self.spi_config = spi_config
        self.global_settings = global_settings
        self.node = node
        
        # SPI devices for each screen on this bus
        self.spi_devices: Dict[int, SPIDevice] = {}
        
        # Message queue and transmission
        self.message_queue = PriorityQueue()
        self.transmission_lock = threading.Lock()  # Only one device can use SPI at a time
        
        # GIF playback management
        self.gif_states: Dict[int, GifPlaybackState] = {}
        self.gif_lock = threading.Lock()
        
        # Threading
        self.running = False
        self.transmission_thread = None
        self.gif_playback_thread = None
        
        # Statistics
        self.stats = {
            'messages_sent': 0,
            'messages_failed': 0,
            'bytes_transmitted': 0,
            'last_activity': time.time()
        }
        
        # Initialize SPI devices
        self._initialize_spi_devices()

    def _initialize_spi_devices(self):
        """Initialize SPI devices for screens on this bus"""
        for screen_id, screen_config in self.screen_configs.items():
            try:
                spi_device = SPIDevice(
                    bus_id=screen_config.bus_id,
                    bus_dev_id=screen_config.bus_dev_id,
                    spi_config={
                        'max_speed_hz': self.spi_config.max_speed_hz,
                        'mode': self.spi_config.mode,
                        'bits_per_word': self.spi_config.bits_per_word
                    },
                    verbose=False
                )
                self.spi_devices[screen_id] = spi_device
                
                self.node.get_logger().debug(f"Initialized SPI device for screen {screen_id} on bus {self.bus_id}")
                
            except Exception as e:
                self.node.get_logger().error(f"Failed to initialize SPI device for screen {screen_id}: {e}")

    def start(self):
        """Start the bus manager threads"""
        if self.running:
            return
        
        self.running = True
        
        # Start transmission thread
        self.transmission_thread = threading.Thread(target=self._transmission_worker, daemon=True)
        self.transmission_thread.start()
        
        # Start GIF playback thread
        self.gif_playback_thread = threading.Thread(target=self._gif_playback_worker, daemon=True)
        self.gif_playback_thread.start()
        
        self.node.get_logger().info(f"Started bus manager for bus {self.bus_id}")

    def stop(self):
        """Stop the bus manager"""
        self.running = False
        
        # Stop all GIF playback
        with self.gif_lock:
            for gif_state in self.gif_states.values():
                gif_state.active = False
            self.gif_states.clear()
        
        # Join threads
        if self.transmission_thread and self.transmission_thread.is_alive():
            self.transmission_thread.join(timeout=2.0)
        
        if self.gif_playback_thread and self.gif_playback_thread.is_alive():
            self.gif_playback_thread.join(timeout=2.0)
        
        # Close SPI devices
        for spi_device in self.spi_devices.values():
            spi_device.down()
        
        self.node.get_logger().info(f"Stopped bus manager for bus {self.bus_id}")

    def queue_protocol_message(self, screen_id: int, message: ProtocolMessage, priority: int = MessagePriority.NORMAL) -> bool:
        """Queue a protocol message for transmission"""
        if screen_id not in self.screen_configs:
            self.node.get_logger().warn(f"Invalid screen ID {screen_id} for bus {self.bus_id}")
            return False
        
        # Stop any existing GIF playback for this screen if it's not a GIF-related message
        if not isinstance(message, (ImageStartMessage, ImageChunkMessage, ImageEndMessage)):
            self._stop_gif_playback(screen_id)
        
        # Create queued message
        queued_msg = QueuedMessage(
            screen_id=screen_id,
            message=message,
            priority=priority
        )
        
        # Add to queue
        self.message_queue.put(queued_msg)
        
        return True

    def start_gif_playback(self, screen_id: int, motion_picture: MotionPicture, rotation: int = 0) -> bool:
        """Start GIF playback for a screen"""
        if screen_id not in self.screen_configs:
            return False
        
        # Stop any existing GIF playback for this screen
        self._stop_gif_playback(screen_id)
        
        # Create new GIF state
        gif_state = GifPlaybackState(
            motion_picture=motion_picture,
            current_frame=0,
            rotation=rotation,
            last_frame_time=time.time(),
            loop_count=0
        )
        
        with self.gif_lock:
            self.gif_states[screen_id] = gif_state
        
        self.node.get_logger().info(f"Started GIF playback for screen {screen_id}: {len(motion_picture.frames_data)} frames")
        return True

    def _stop_gif_playback(self, screen_id: int):
        """Stop GIF playback for a screen"""
        with self.gif_lock:
            if screen_id in self.gif_states:
                self.gif_states[screen_id].active = False
                del self.gif_states[screen_id]

    def _transmission_worker(self):
        """Worker thread for transmitting messages"""
        self.node.get_logger().debug(f"Transmission worker started for bus {self.bus_id}")
        
        while self.running:
            try:
                # Get next message with timeout
                queued_msg = self.message_queue.get(timeout=0.1)
                
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
        message = queued_msg.message
        
        spi_device = self.spi_devices.get(screen_id)
        if not spi_device:
            return False
        
        try:
            with self.transmission_lock:
                # Ensure device is ready
                spi_device.up()
                
                # Send the message payload
                spi_device.send(list(message.payload))
                
                # Close device
                spi_device.down()
                
                return True
                
        except Exception as e:
            self.node.get_logger().error(f"SPI transmission error for screen {screen_id}: {e}")
            spi_device.down()  # Ensure device is closed
            return False

    def _gif_playback_worker(self):
        """Worker thread for GIF frame scheduling"""
        self.node.get_logger().debug(f"GIF playback worker started for bus {self.bus_id}")
        
        while self.running:
            try:
                current_time = time.time()
                
                with self.gif_lock:
                    # Process each active GIF
                    screens_to_remove = []
                    
                    for screen_id, gif_state in self.gif_states.items():
                        if not gif_state.active:
                            screens_to_remove.append(screen_id)
                            continue
                        
                        # Check if it's time for the next frame
                        frame_duration = gif_state.motion_picture.delay_time / 1000.0  # Convert ms to seconds
                        
                        if current_time - gif_state.last_frame_time >= frame_duration:
                            # Send next frame
                            if self._send_gif_frame(screen_id, gif_state):
                                gif_state.last_frame_time = current_time
                                gif_state.current_frame = (gif_state.current_frame + 1) % len(gif_state.motion_picture.frames_data)
                                
                                # Increment loop count when back to frame 0
                                if gif_state.current_frame == 0:
                                    gif_state.loop_count += 1
                            else:
                                # Failed to send frame, stop playback
                                gif_state.active = False
                                screens_to_remove.append(screen_id)
                    
                    # Remove inactive GIFs
                    for screen_id in screens_to_remove:
                        if screen_id in self.gif_states:
                            del self.gif_states[screen_id]
                
                # Sleep for a short time
                time.sleep(0.010)  # 10ms resolution
                
            except Exception as e:
                self.node.get_logger().error(f"Error in GIF playback worker: {e}")

    def _send_gif_frame(self, screen_id: int, gif_state: GifPlaybackState) -> bool:
        """Send a single GIF frame to a screen"""
        try:
            motion_picture = gif_state.motion_picture
            frame_index = gif_state.current_frame
            frame_data = motion_picture.frames_data[frame_index]
            
            # Get frame metadata
            frame_metadata = motion_picture.get_frame_metadata(frame_index)
            
            # Create protocol messages for this frame
            start_message = ImageStartMessage(
                image_id=frame_metadata['image_id'],
                image_format=frame_metadata['image_format'],
                resolution=frame_metadata['resolution'],
                delay_time=frame_metadata['delay_time'],
                total_size=frame_metadata['total_size'],
                num_chunks=frame_metadata['num_chunks'],
                rotation=Rotation(gif_state.rotation)
            )
            
            # Queue start message with high priority
            self.queue_protocol_message(screen_id, start_message, MessagePriority.HIGH)
            
            # Send image chunks
            chunk_size = self.global_settings.max_chunk_size if self.global_settings else 2048
            chunk_id = 0
            start_location = 0
            
            for i in range(0, len(frame_data), chunk_size):
                chunk_data = frame_data[i:i + chunk_size]
                
                chunk_message = ImageChunkMessage(
                    image_id=frame_metadata['image_id'],
                    chunk_id=chunk_id,
                    start_location=start_location,
                    chunk_data=chunk_data
                )
                
                self.queue_protocol_message(screen_id, chunk_message, MessagePriority.NORMAL)
                
                chunk_id += 1
                start_location += len(chunk_data)
            
            # Send end message
            end_message = ImageEndMessage(image_id=frame_metadata['image_id'])
            self.queue_protocol_message(screen_id, end_message, MessagePriority.HIGH)
            
            return True
            
        except Exception as e:
            self.node.get_logger().error(f"Error sending GIF frame for screen {screen_id}: {e}")
            return False

    def get_stats(self) -> Dict[str, Any]:
        """Get bus manager statistics"""
        stats = self.stats.copy()
        stats['queue_size'] = self.message_queue.qsize()
        stats['active_gifs'] = len(self.gif_states)
        stats['screens'] = list(self.screen_configs.keys())
        return stats

    def is_screen_playing_gif(self, screen_id: int) -> bool:
        """Check if a screen is currently playing a GIF"""
        with self.gif_lock:
            return screen_id in self.gif_states and self.gif_states[screen_id].active

    def get_gif_info(self, screen_id: int) -> Optional[Dict[str, Any]]:
        """Get information about currently playing GIF"""
        with self.gif_lock:
            if screen_id not in self.gif_states:
                return None
            
            gif_state = self.gif_states[screen_id]
            return {
                'current_frame': gif_state.current_frame,
                'total_frames': len(gif_state.motion_picture.frames_data),
                'loop_count': gif_state.loop_count,
                'frame_duration_ms': gif_state.motion_picture.delay_time,
                'active': gif_state.active
            }
