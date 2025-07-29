"""
U-M Shapiro Design Lab
Daniel Hou @2024

This module handles communication with peripheral ESP32 boards through a chosen interface.

Protocols: see https://docs.google.com/document/d/1ovbKFz1-aYnTLMupWtqQHsDRdrbPbAs7edm_ehnVuko
"""
import threading
import numpy as np
from queue import Queue, Empty
from typing import Dict, Optional, List, Union
import tf2_ros

# Import the new message type
from DiceMaster_Central.msg import ScreenMediaCmd

from DiceMaster_Central.config.constants import (
    SPI_CHUNK_SIZE, MessagePriority, RequestStatus, ContentType, GIF_FRAME_TIME,
    Rotation
)
from DiceMaster_Central.media_typing.protocol import (
    TextBatchMessage, ImageStartMessage, ImageChunkMessage, 
    ImageEndMessage
)
from DiceMaster_Central.media_typing.media_types import (
    TextGroup, Image as MediaImage, GIF
)


class Screen:
    """
    Screen class that handles media processing, GIF playback, and orientation management.
    Takes a node object for ROS functionality instead of being a node itself.
    """
    def __init__(self,
        node, 
        screen_id: int,
        bus_manager,
        rotation_margin: float = 0.2
    ):
        # Basic properties
        self.screen_id = screen_id
        self.node = node
        self.bus_manager = bus_manager
        self.rotation_margin = rotation_margin
        self.current_rotation = Rotation.ROTATION_0
        
        # Content management
        self.media_processing_queue = Queue()
        self.request_counter = 0
        self.request_status: Dict[int, RequestStatus] = {}
        self.last_content = None
        self.last_content_type = None
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
        
        # TF2 setup for orientation tracking
        try:
            self.tf_buffer = tf2_ros.Buffer()
            self.tf_listener = tf2_ros.TransformListener(self.tf_buffer, self.node)
            
            # Screen edge frame names for orientation detection
            self.edge_frames = [
                f'screen_{screen_id}_edge_top',
                f'screen_{screen_id}_edge_right', 
                f'screen_{screen_id}_edge_bottom',
                f'screen_{screen_id}_edge_left'
            ]
            self.orientation_timer = self.node.create_timer(0.1, self.check_orientation)
        except Exception as e:
            self.node.get_logger().warn(f"Failed to setup TF2 for screen {screen_id}: {e}")
            self.orientation_timer = None

        self.node.get_logger().info(f"Screen {screen_id} initialized")

    def __repr__(self):
        return f"Screen(screen_id={self.screen_id}, rotation={self.current_rotation})"

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
            self.push_to_bus_manager(messages, MessagePriority.HIGH)
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
    def setup_gif_replay(self, frame_message_lists: List[List[Union[ImageStartMessage, ImageChunkMessage, ImageEndMessage]]]):
        """Setup GIF replay by creating a timer for frame cycling"""
        with self.gif_lock:
            # Stop any existing GIF playback
            self.destroy_gif_replay()
            
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
            
            # Update rotation for current frame if needed
            for msg in current_frame_messages:
                if hasattr(msg, 'rotation'):
                    msg.rotation = self.current_rotation
            
            # Push frame to bus manager
            self.push_to_bus_manager(current_frame_messages, MessagePriority.NORMAL)
            
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
        if self.last_content is None:
            return
            
        try:
            if self.last_content_type == ContentType.TEXT:
                self.update_text_orientation(self.last_content)
            elif self.last_content_type == 'image':
                self.update_image_orientation(self.last_content)
            elif self.last_content_type == 'gif':
                self.update_gif_orientation(self.last_content)
        except Exception as e:
            self.node.get_logger().error(f"Error re-sending content with rotation: {e}")

    def update_text_orientation(self, msg: TextBatchMessage):
        """Update text message orientation and resend"""
        msg.rotation = self.current_rotation
        self.push_to_bus_manager(msg, MessagePriority.HIGH)

    def update_image_orientation(self, msgs: List[Union[ImageStartMessage, ImageChunkMessage, ImageEndMessage]]):
        """Update image messages orientation and resend"""
        for msg in msgs:
            if hasattr(msg, 'rotation'):
                msg.rotation = self.current_rotation
        self.push_to_bus_manager(msgs, MessagePriority.HIGH)

    def update_gif_orientation(self, frame_message_lists: List[List[Union[ImageStartMessage, ImageChunkMessage, ImageEndMessage]]]):
        """Update GIF frame messages orientation"""
        # Update all frame messages with new rotation
        for frame_messages in frame_message_lists:
            for msg in frame_messages:
                if hasattr(msg, 'rotation'):
                    msg.rotation = self.current_rotation
        
        # Restart GIF playback with updated messages
        self.setup_gif_replay(frame_message_lists)


    def destroy(self):
        """Clean up resources"""
        self.running = False
        if self.orientation_timer:
            self.orientation_timer.cancel()
        if self.processing_thread.is_alive():
            self.processing_thread.join()
        self.node.get_logger().info(f'Screen {self.screen_id} destroyed')