"""
U-M Shapiro Design Lab
Daniel Hou @2024

This module handles communication with peripheral ESP32 boards through a chosen interface.

Protocols: see https://docs.google.com/document/d/1ovbKFz1-aYnTLMupWtqQHsDRdrbPbAs7edm_ehnVuko
"""
from __future__ import annotations

import threading
from queue import Queue, Empty
from typing import Dict, Optional, Any

# Import the new message type
from dicemaster_central_msgs.msg import ScreenMediaCmd, ScreenPose
from dicemaster_central.config import dice_config
from dicemaster_central.constants import (
    MessagePriority, RequestStatus, ContentType, GIF_FRAME_TIME,
    Rotation
)
from dicemaster_central.media_typing.media_types import (
    TextGroup, Image as MediaImage, GIF
)

SPI_CHUNK_SIZE = dice_config.spi_config.max_buffer_size


class Screen:
    """
    Screen class that handles media processing, GIF playback, and chassis-driven rotation.
    
    This class manages a single screen device and provides:
    - Media processing (text, images, GIFs) in a separate thread
    - Rotation updates by subscribing to chassis pose topics (/chassis/screen_{id}_pose)
    - GIF playback with frame timing
    - Content re-transmission when rotation changes
    
    Note: This class does NOT perform orientation detection. It relies entirely on
    rotation information provided by the chassis node via ScreenPose messages.
    
    Args:
        node: ROS2 node for logging and timer creation
        screen_id: Unique identifier for this screen
        bus_manager: Bus manager for sending protocol messages
    """
    def __init__(self,
        node, 
        screen_id: int,
        bus_manager
    ):
        # Basic properties
        self.screen_id = screen_id
        self.node = node
        self.bus_manager = bus_manager
        self.current_rotation = Rotation.ROTATION_0
        
        # Content management
        self.media_processing_queue = Queue()
        self.request_counter = 0
        self.request_status: Dict[int, RequestStatus] = {}
        self.last_content: Any = None  # Can be TextBatchMessage, List of messages, or List of Lists for GIF
        self.last_content_type: Optional[ContentType] = None
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
        
        # Chassis pose subscription for rotation updates
        topic_name = f'/chassis/screen_{self.screen_id}_pose'
        self.pose_subscription = self.node.create_subscription(
            ScreenPose,
            topic_name,
            self._pose_callback,
            10
        )
        self.node.get_logger().info(f"Screen {self.screen_id} subscribed to {topic_name}")

        self.node.get_logger().info(f"Screen {screen_id} initialized")

    def __repr__(self):
        return f"Screen(screen_id={self.screen_id}, rotation={self.current_rotation})"

    def _pose_callback(self, msg: ScreenPose):
        """Callback for chassis pose updates from /chassis/screen_{id}_pose topic
        
        Receives ScreenPose messages from the chassis node containing rotation
        information calculated from IMU and orientation detection.
        """
        if msg.screen_id != self.screen_id:
            return
            
        new_rotation = Rotation(msg.rotation)
        if new_rotation == self.current_rotation:
            return

        # Update bottom rotation and resend
        old_rotation = self.current_rotation
        self.current_rotation = new_rotation
        self.node.get_logger().info(
            f'Screen {self.screen_id} rotation updated from {old_rotation} to {new_rotation} '
            f'(up_alignment: {msg.up_alignment:.3f}, facing_up: {msg.is_facing_up})'
        )
        
        # Re-send current content with new rotation
        if self.last_content is not None:
            self._resend_with_rotation()

    def destroy(self):
        """Clean up resources"""
        self.running = False
        self.destroy_gif_replay()
        if self.pose_subscription:
            # Subscription cleanup is handled by ROS2 automatically
            pass
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
        # self.node.get_logger().info(f"Queuening media request for screen {self.screen_id} with rot={self.current_rotation}")
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
            # Stop any active GIF playback
            self.destroy_gif_replay()
            
            # Use TextGroup to load and validate JSON configuration
            text_group = TextGroup(file_path=request.file_path)
            text_message = text_group.to_msg(rotation=self.current_rotation, screen_id=self.screen_id)
            
            # Store content for re-transmission when rotation changes
            self.last_content = text_message
            self.last_content_type = ContentType.TEXT
            
            # Push to bus manager
            # self.node.get_logger().info("Pushed text prompt to bus")
            self.push_to_bus_manager(text_message, MessagePriority.HIGH)
            return True
            
        except Exception as e:
            self.node.get_logger().error(f"Error processing text request: {e}")
            return False

    def _process_image_request(self, request: ScreenMediaCmd) -> bool:
        """Process image request using Image media type"""
        try:
            # Stop any active GIF playback
            self.destroy_gif_replay()
            
            # Use Image class to load and validate image
            image = MediaImage(file_path=request.file_path)
            messages = image.to_msg(rotation=self.current_rotation, chunk_size=SPI_CHUNK_SIZE, screen_id=self.screen_id)
            
            # Store content for re-transmission when rotation changes
            self.last_content = messages
            self.last_content_type = ContentType.IMAGE
            
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
            frame_message_lists = gif.to_msg(rotation=self.current_rotation, chunk_size=SPI_CHUNK_SIZE, screen_id=self.screen_id)
            
            # Store content for re-transmission when rotation changes and setup GIF playback
            self.last_content = frame_message_lists
            self.last_content_type = ContentType.GIF
            
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
        from time import perf_counter
        
        # Start timing this callback execution
        callback_start = perf_counter()
        
        # Log time since last callback (timer interval)
        if not hasattr(self, "_gif_last_t"):
            self._gif_last_t = callback_start
        
        self.node.get_logger().info(f"Timer interval: {callback_start - self._gif_last_t:.4f}s")
        
        with self.gif_lock:
            if not self.gif_active or not self.gif_messages:
                return
            
            # Get current frame messages
            current_frame_messages = self.gif_messages[self.gif_frame_index]
            
            # Update rotation for current frame if rotation is enabled
            # Only the first message (ImageStartMessage) has rotation
            if current_frame_messages and hasattr(current_frame_messages[0], 'rotation'):
                current_frame_messages[0].rotation = self.current_rotation
            
            # Push frame to bus manager
            self.push_to_bus_manager(current_frame_messages, MessagePriority.HIGH)
            
            # Advance to next frame
            self.gif_frame_index = (self.gif_frame_index + 1) % len(self.gif_messages)
        
        # Log callback execution time
        callback_end = perf_counter()
        self.node.get_logger().info(f"Callback execution: {callback_end - callback_start:.4f}s")
        self._gif_last_t = callback_start

    def destroy_gif_replay(self):
        """Destroy GIF replay resources"""
        # self.node.get_logger().info("GIF playback stopped")
        with self.gif_lock:
            self.gif_active = False
            if self.gif_timer:
                self.gif_timer.cancel()
                self.gif_timer = None
            self.gif_messages = []
            self.gif_frame_index = 0

    def _resend_with_rotation(self):
        """Re-send the last content with current rotation"""
        if self.last_content is None:
            return
            
        try:
            if self.last_content_type == ContentType.TEXT:
                # For text messages, update rotation and resend
                if hasattr(self.last_content, 'rotation'):
                    self.last_content.rotation = self.current_rotation
                    self.push_to_bus_manager(self.last_content, MessagePriority.HIGH)
            elif self.last_content_type == ContentType.IMAGE:
                # For image messages, only the start message has rotation
                if isinstance(self.last_content, list) and len(self.last_content) > 0:
                    start_msg = self.last_content[0]  # First message should be ImageStartMessage
                    if hasattr(start_msg, 'rotation'):
                        start_msg.rotation = self.current_rotation
                    self.push_to_bus_manager(self.last_content, MessagePriority.HIGH)
            elif self.last_content_type == ContentType.GIF:
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