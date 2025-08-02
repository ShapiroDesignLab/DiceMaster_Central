"""
U-M Shapiro Design Lab
Daniel Hou @2024

This module handles communication with peripheral ESP32 boards through a chosen interface.

Protocols: see https://docs.google.com/document/d/1ovbKFz1-aYnTLMupWtqQHsDRdrbPbAs7edm_ehnVuko
"""
import threading
import time
import numpy as np
from queue import Queue, Empty
from typing import Dict, Optional, Any
import tf2_ros

# Import the new message type
from dicemaster_central_msgs.msg import ScreenMediaCmd
from dicemaster_central.config import dice_config
from dicemaster_central.constants import (
    MessagePriority, RequestStatus, ContentType, GIF_FRAME_TIME,
    Rotation
)
from dicemaster_central.media_typing.media_types import (
    TextGroup, Image as MediaImage, GIF
)
from dicemaster_central.hw.screen import ScreenBusManager

SPI_CHUNK_SIZE = dice_config.spi_config.max_buffer_size


class Screen:
    """
    Screen class that handles media processing, GIF playback, and optional orientation management.
    
    This class manages a single screen device and provides:
    - Media processing (text, images, GIFs) in a separate thread
    - Optional automatic rotation tracking using TF2 transforms
    - GIF playback with frame timing
    - Orientation-aware content re-transmission
    
    Args:
        node: ROS2 node for logging and timer creation
        screen_id: Unique identifier for this screen
        bus_manager: Bus manager for sending protocol messages
        using_rotation: Whether to enable automatic rotation tracking (default: False)
        rotation_margin: Threshold for rotation changes in meters (default: 0.2)
    """
    def __init__(self,
        node, 
        screen_id: int,
        bus_manager,
        using_rotation=False,
        rotation_margin: float = 0.2
    ):
        # Basic properties
        self.screen_id = screen_id
        self.node = node
        self.bus_manager: ScreenBusManager = bus_manager
        self.using_rotation = using_rotation
        self.rotation_margin = rotation_margin
        self.current_rotation = Rotation.ROTATION_0
        
        # Content management
        self.media_processing_queue = Queue()
        self.request_counter = 0
        self.request_status: Dict[int, RequestStatus] = {}
        self.last_content: Any = None  # Can be TextBatchMessage, List of messages, or List of Lists for GIF
        self.last_content_type: Optional[str] = None
        self.running = True

        # Content processing thread
        self.processing_thread = threading.Thread(target=self._processing_worker, daemon=True)
        self.processing_thread.start()
        
        # GIF playback management
        self.gif_messages = []  # List of message lists for each frame
        self.gif_timer = None
        self.gif_frame_index = 0
        self.gif_active = False
        self.gif_lock = threading.Lock()
        
        # Rotation tracking setup (optional)
        self.tf_buffer = None
        self.tf_listener = None
        self.edge_frames = None
        self.orientation_timer = None
        
        if using_rotation:
            self._setup_rotation_tracking()

        self.node.get_logger().info(f"Screen {screen_id} initialized {' with rotation tracking' if using_rotation else ''}")

    def __repr__(self):
        return f"Screen(screen_id={self.screen_id}, rotation={self.current_rotation}, rotation_enabled={self.using_rotation})"

    def _setup_rotation_tracking(self):
        """Setup TF2 and orientation tracking for automatic rotation detection"""
        try:
            self.tf_buffer = tf2_ros.Buffer()
            self.tf_listener = tf2_ros.TransformListener(self.tf_buffer, self.node)
            
            # Screen edge frame names for orientation detection
            self.edge_frames = [
                f'screen_{self.screen_id}_edge_top',
                f'screen_{self.screen_id}_edge_right', 
                f'screen_{self.screen_id}_edge_bottom',
                f'screen_{self.screen_id}_edge_left'
            ]
            
            # Create timer for orientation checking at 10Hz
            self.orientation_timer = self.node.create_timer(0.1, self.check_orientation)
            self.node.get_logger().info(f"Rotation tracking enabled for screen {self.screen_id}")
            
        except Exception as e:
            self.node.get_logger().warn(f"Failed to setup rotation tracking for screen {self.screen_id}: {e}")
            self.tf_buffer = None
            self.tf_listener = None
            self.edge_frames = None
            self.orientation_timer = None

    def destroy(self):
        """Clean up resources"""
        self.running = False
        self.destroy_gif_replay()
        if self.orientation_timer:
            self.orientation_timer.cancel()
        if self.processing_thread.is_alive():
            self.processing_thread.join(timeout=2.0)
        self.node.get_logger().info(f'Screen {self.screen_id} destroyed')

    # Communication methods
    def queue_media_request(self, request_msg: ScreenMediaCmd):
        """Queue a media request for processing"""
        req_id = self._get_next_request_id()
        counter = 0
        while self.request_status.get(req_id) in [RequestStatus.PENDING, RequestStatus.PROCESSING] and counter < 10:
            req_id = self._get_next_request_id()
            counter += 1
        if counter >= 10:
            self.node.get_logger().warn(f"Failed to get available request ID for screen {self.screen_id}")
            return
        
        self.request_status[req_id] = RequestStatus.PENDING
        self.node.get_logger().info(f"Queuening media request for screen {self.screen_id} with ID {req_id}")
        self.media_processing_queue.put((req_id, request_msg))

    def push_to_bus_manager(self, msgs, priority=MessagePriority.NORMAL) -> None:
        """Push messages to bus manager"""
        if not isinstance(msgs, list):
            msgs = [msgs]
        for msg in msgs:
            self.bus_manager.queue_protocol_message(self.screen_id, msg, priority)

    def _get_next_request_id(self) -> int:
        """Generate next request ID"""
        self.request_counter = (self.request_counter + 1) % 65536
        return self.request_counter

    # -----------------------------------   
    # Media processing methods
    # -----------------------------------
    def _processing_worker(self):
        """Main processing worker thread"""
        self.node.get_logger().debug(f"Processing worker started for screen {self.screen_id}")
        
        while self.running:
            try:
                # Get next request with timeout
                req_id, request = self.media_processing_queue.get(timeout=0.1)
                self.request_status[req_id] = RequestStatus.PROCESSING
                
                success = False
                if request.media_type == ContentType.TEXT:
                    success = self._process_text_request(request)
                elif request.media_type == ContentType.IMAGE:
                    success = self._process_image_request(request)
                elif request.media_type == ContentType.GIF:
                    success = self._process_gif_request(request)
                else:
                    self.node.get_logger().error(f"Unknown media type: {request.media_type}")
                
                self.request_status[req_id] = RequestStatus.COMPLETED if success else RequestStatus.FAILED
                
            except Empty:
                continue
            except Exception as e:
                self.node.get_logger().error(f"Error in processing worker for screen {self.screen_id}: {e}")

    def _process_text_request(self, request: ScreenMediaCmd) -> bool:
        """Process text request using TextGroup from JSON file"""
        try:
            # Use TextGroup to load and validate JSON configuration
            text_group = TextGroup(file_path=request.file_path)
            text_message = text_group.to_msg(rotation=self.current_rotation)
            
            # Store content for re-orientation
            self.last_content = text_message
            self.last_content_type = ContentType.TEXT
            
            # Push to bus manager
            self.node.get_logger().info("Pushed text prompt to bus")
            self.push_to_bus_manager(text_message, MessagePriority.HIGH)
            return True
            
        except Exception as e:
            self.node.get_logger().error(f"Error processing text request: {e}")
            return False

    def _process_image_request(self, request: ScreenMediaCmd) -> bool:
        """Process image request using Image media type"""
        try:
            # Use Image class to load and validate image
            image = MediaImage(file_path=request.file_path)
            messages = image.to_msg(rotation=self.current_rotation, chunk_size=SPI_CHUNK_SIZE)
            
            # Store content for re-orientation
            self.last_content = messages
            self.last_content_type = 'image'
            
            # Push all messages to bus manager
            self.node.get_logger().info("Pushed image prompt to bus")
            self.push_to_bus_manager(messages)
            return True
            
        except Exception as e:
            self.node.get_logger().error(f"Error processing image request: {e}")
            return False

    def _process_gif_request(self, request: ScreenMediaCmd) -> bool:
        """Process GIF request using GIF media type"""
        try:
            # Use GIF class to load GIF frames
            gif = GIF(
                file_path=request.file_path,
                delay_time=int(GIF_FRAME_TIME * 1000)  # Convert to ms
            )
            
            if not gif.frames_data:
                self.node.get_logger().error(f"No frames found in GIF: {request.file_path}")
                return False
            
            # Generate protocol messages for all frames using to_msg()
            frame_message_lists = gif.to_msg(rotation=self.current_rotation, chunk_size=SPI_CHUNK_SIZE)
            
            # Store content for re-orientation and setup GIF playback
            self.last_content = frame_message_lists
            self.last_content_type = 'gif'
            
            # Setup GIF replay
            self.node.get_logger().info("GIF replay setup")
            self.setup_gif_replay(frame_message_lists)
            return True
            
        except Exception as e:
            self.node.get_logger().error(f"Error processing GIF request: {e}")
            return False

    def get_request_status(self, request_id: int) -> Optional[RequestStatus]:
        """Get status of a request"""
        return self.request_status.get(request_id)

    def get_active_requests(self) -> Dict[int, RequestStatus]:
        """Get all active request statuses"""
        return self.request_status.copy()

    # -----------------------------------
    # GIF Utilities
    # -----------------------------------
    def setup_gif_replay(self, frame_message_lists: Any):
        """Setup GIF replay by creating a timer for frame cycling"""
        # Stop any existing GIF playback
        self.destroy_gif_replay()
            
        with self.gif_lock:
            # Store the frame messages
            self.gif_messages = frame_message_lists
            self.gif_frame_index = 0
            self.gif_active = True
            
            # Create timer for GIF playback at 12Hz
            self.gif_timer = self.node.create_timer(GIF_FRAME_TIME, self._gif_frame_callback)
            
            self.node.get_logger().info(f"Started GIF playback for screen {self.screen_id}: {len(frame_message_lists)} frames")

    def _gif_frame_callback(self):
        """Timer callback for GIF frame playback"""
        with self.gif_lock:
            if not self.gif_active or not self.gif_messages:
                return
            
            # Get current frame messages
            current_frame_messages = self.gif_messages[self.gif_frame_index]
            
            # Update rotation for current frame if rotation is enabled
            # Only the first message (ImageStartMessage) has rotation
            if self.using_rotation and current_frame_messages and hasattr(current_frame_messages[0], 'rotation'):
                current_frame_messages[0].rotation = self.current_rotation
            
            # Push frame to bus manager
            self.push_to_bus_manager(current_frame_messages, MessagePriority.HIGH)
            
            # Advance to next frame
            self.gif_frame_index = (self.gif_frame_index + 1) % len(self.gif_messages)

    def destroy_gif_replay(self):
        """Destroy GIF replay resources"""
        with self.gif_lock:
            self.gif_active = False
            if self.gif_timer:
                self.gif_timer.cancel()
                self.gif_timer = None
            self.gif_messages = []
            self.gif_frame_index = 0

    # -----------------------------------
    # Rotation and Orientation Management
    # -----------------------------------
    def check_orientation(self) -> None:
        """Check current orientation and trigger rotation if needed"""
        # Skip if rotation tracking is not enabled
        if not self.using_rotation or self.tf_buffer is None or self.edge_frames is None:
            return
            
        try:
            # Get transform from base_link to each edge frame
            edge_vectors = []
            current_time = self.node.get_clock().now()

            for edge_frame in self.edge_frames:
                try:
                    transform = self.tf_buffer.lookup_transform(
                        'base_link', edge_frame, current_time, timeout=tf2_ros.Duration(seconds=0.1)
                    )
                    # Extract Z component of the edge position
                    z_component = transform.transform.translation.z
                    edge_vectors.append(z_component)
                except Exception:
                    # If we can't get transform, skip this iteration
                    return
                    
            if len(edge_vectors) != 4:
                return
                
            # Determine which edge is most "up" (highest Z component)
            max_z_idx = np.argmax(edge_vectors)
            max_z_value = edge_vectors[max_z_idx]
            
            # Check if this edge is significantly more "up" than current top
            current_top_idx = (4 - self.current_rotation) % 4
            current_top_z = edge_vectors[current_top_idx]
            
            # If the highest edge is different and exceeds margin, rotate
            if (max_z_idx != current_top_idx and 
                max_z_value - current_top_z > self.rotation_margin):
                
                new_rotation = Rotation((4 - max_z_idx) % 4)
                self.set_rotation(new_rotation)
                        
        except Exception as e:
            self.node.get_logger().debug(f'Error in orientation check for screen {self.screen_id}: {str(e)}')

    def set_rotation(self, rotation: Rotation):
        """Manually set screen rotation and update content"""
        if self.current_rotation == rotation:
            return
            
        old_rotation = self.current_rotation
        self.current_rotation = rotation
        
        self.node.get_logger().info(f'Screen {self.screen_id} rotation changed from {old_rotation} to {rotation}')
        
        # Update current content with new rotation
        if self.last_content is not None:
            self._resend_with_rotation()

    def _resend_with_rotation(self):
        """Re-send the last content with current rotation"""
        if self.last_content is None or not self.using_rotation:
            return
            
        try:
            if self.last_content_type == ContentType.TEXT:
                # For text messages, update rotation directly
                if hasattr(self.last_content, 'rotation'):
                    self.last_content.rotation = self.current_rotation
                    self.push_to_bus_manager(self.last_content, MessagePriority.HIGH)
            elif self.last_content_type == 'image':
                # For image messages, only the start message has rotation
                if isinstance(self.last_content, list) and len(self.last_content) > 0:
                    start_msg = self.last_content[0]  # First message should be ImageStartMessage
                    if hasattr(start_msg, 'rotation'):
                        start_msg.rotation = self.current_rotation
                    self.push_to_bus_manager(self.last_content, MessagePriority.HIGH)
            elif self.last_content_type == 'gif':
                # For GIF, update rotation in all frame start messages and restart playback
                if isinstance(self.last_content, list):
                    for frame_messages in self.last_content:
                        if isinstance(frame_messages, list) and len(frame_messages) > 0:
                            start_msg = frame_messages[0]  # First message should be ImageStartMessage
                            if hasattr(start_msg, 'rotation'):
                                start_msg.rotation = self.current_rotation
                    # Restart GIF playback with updated messages
                    self.setup_gif_replay(self.last_content)
        except Exception as e:
            self.node.get_logger().error(f"Error re-sending content with rotation: {e}")

    def update_text_orientation(self, msg):
        """Update text message orientation and resend"""
        if hasattr(msg, 'rotation'):
            msg.rotation = self.current_rotation
            self.push_to_bus_manager(msg, MessagePriority.HIGH)

    def update_image_orientation(self, msgs):
        """Update image messages orientation and resend"""
        if isinstance(msgs, list) and len(msgs) > 0:
            # Only the first message (ImageStartMessage) has rotation
            start_msg = msgs[0]
            if hasattr(start_msg, 'rotation'):
                start_msg.rotation = self.current_rotation
            self.push_to_bus_manager(msgs, MessagePriority.HIGH)

    def update_gif_orientation(self, frame_message_lists):
        """Update GIF frame messages orientation"""
        if isinstance(frame_message_lists, list):
            # Update rotation in all frame start messages
            for frame_messages in frame_message_lists:
                if isinstance(frame_messages, list) and len(frame_messages) > 0:
                    start_msg = frame_messages[0]  # First message should be ImageStartMessage
                    if hasattr(start_msg, 'rotation'):
                        start_msg.rotation = self.current_rotation
            
            # Restart GIF playback with updated messages
            self.setup_gif_replay(frame_message_lists)

    def enable_rotation_tracking(self):
        """Enable rotation tracking for this screen"""
        if not self.using_rotation:
            self.using_rotation = True
            self._setup_rotation_tracking()

    def disable_rotation_tracking(self):
        """Disable rotation tracking for this screen"""
        if self.using_rotation:
            self.using_rotation = False
            if self.orientation_timer:
                self.orientation_timer.cancel()
                self.orientation_timer = None
            self.tf_buffer = None
            self.tf_listener = None
            self.edge_frames = None
            self.node.get_logger().info(f"Rotation tracking disabled for screen {self.screen_id}")

    def get_rotation_status(self) -> dict:
        """Get current rotation status information"""
        return {
            'using_rotation': self.using_rotation,
            'current_rotation': self.current_rotation,
            'rotation_margin': self.rotation_margin,
            'tf_tracking_active': self.orientation_timer is not None
        }