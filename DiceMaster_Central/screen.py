import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Vector3
import tf2_ros
import tf2_geometry_msgs
import numpy as np
import time
import threading
from typing import Optional, Tuple, List

from .protocol import (
    ProtocolMessage, TextMessage, ImageStartMessage, ImageChunkMessage, 
    ImageEndMessage, MessageType, ImageFormat, ImageResolution, Rotation,
    split_image_into_chunks
)
from .bus import SPIDevice, Bus
from .constants import (
    NUM_SCREEN, NUM_SPI_CTRL, NUM_DEV_PER_SPI_CTRL, IMG_RES_240SQ, 
    IMG_RES_480SQ, CHUNK_SIZE, MAX_TEXT_LEN, TXT_CMD, FONT_SIZE, 
    TEXT_PADDING, SCREEN_WIDTH, BYTE_SIZE, USING_ORIENTED_SCREENS
)
from PIL import ImageFont

def HIBYTE(val):
    return (val >> 8) & 0xFF

def LOBYTE(val):
    return val & 0xFF


class ScreenNode(Node):
    """
    ROS2 Screen Node that handles SPI communication and auto-rotation for a single screen.
    Each screen is spawned as a separate node with a unique ID.
    """

    def __init__(self, screen_id: int, bus_num: int, dev_num: int, auto_rotate: bool = True, 
                 rotation_margin: float = 0.2):
        super().__init__(f'screen_{screen_id}_node')
        
        self.screen_id = screen_id
        self.auto_rotate = auto_rotate
        self.rotation_margin = rotation_margin  # Margin before triggering rotation
        self.current_rotation = Rotation.ROTATION_0
        self.last_content = None  # Store last sent content for re-rotation
        self.last_content_type = None  # 'image' or 'text'
        
        # SPI Communication setup
        self.bus = Bus()
        self.spi_device = SPIDevice(screen_id, bus_num, dev_num)
        self.bus.register(self.spi_device)
        self.bus.run()
        
        # TF2 setup for orientation tracking
        self.tf_buffer = tf2_ros.Buffer()
        self.tf_listener = tf2_ros.TransformListener(self.tf_buffer, self)
        
        # Screen edge frame names for orientation detection
        self.edge_frames = [
            f'screen_{screen_id}_edge_top',
            f'screen_{screen_id}_edge_right', 
            f'screen_{screen_id}_edge_bottom',
            f'screen_{screen_id}_edge_left'
        ]
        
        # Timer for orientation checking
        if self.auto_rotate:
            self.orientation_timer = self.create_timer(0.1, self.check_orientation)  # 10Hz
        
        # Message ID counter
        self.msg_id_counter = 0
        
        self.get_logger().info(f'Screen {screen_id} node initialized on bus {bus_num}, device {dev_num}')

    def get_next_msg_id(self) -> int:
        """Get next message ID for protocol"""
        self.msg_id_counter = (self.msg_id_counter + 1) % 256
        return self.msg_id_counter

    def send_message(self, message: ProtocolMessage):
        """Send a protocol message over SPI"""
        msg_bytes = message.build_message()
        # Convert to list format expected by bus
        msg_list = list(msg_bytes)
        self.bus.queue((self.spi_device, message.msg_type, msg_list))

    def check_orientation(self):
        """Check current orientation and trigger rotation if needed"""
        if not self.auto_rotate:
            return
            
        try:
            # Get transform from base_link to each edge frame
            edge_vectors = []
            
            for edge_frame in self.edge_frames:
                try:
                    transform = self.tf_buffer.lookup_transform(
                        'base_link', edge_frame, rclpy.time.Time())
                    
                    # Extract the position vector (this tells us where the edge is)
                    edge_pos = np.array([
                        transform.transform.translation.x,
                        transform.transform.translation.y,
                        transform.transform.translation.z
                    ])
                    edge_vectors.append(edge_pos)
                    
                except tf2_ros.LookupException:
                    self.get_logger().warn(f'Could not find transform to {edge_frame}')
                    return
                except tf2_ros.ExtrapolationException:
                    return  # Data not available yet
                    
            if len(edge_vectors) != 4:
                return
                
            # Determine which edge is most "up" (highest Z component)
            # Edge order: top, right, bottom, left (0, 1, 2, 3)
            z_components = [vec[2] for vec in edge_vectors]
            max_z_idx = np.argmax(z_components)
            max_z_value = z_components[max_z_idx]
            
            # Check if this edge is significantly more "up" than current top
            current_top_idx = (4 - self.current_rotation) % 4  # Convert rotation to edge index
            current_top_z = z_components[current_top_idx]
            
            # If the highest edge is different and exceeds margin, rotate
            if (max_z_idx != current_top_idx and 
                max_z_value - current_top_z > self.rotation_margin):
                
                # Calculate required rotation
                new_rotation = Rotation((4 - max_z_idx) % 4)
                
                if new_rotation != self.current_rotation:
                    self.get_logger().info(f'Auto-rotating screen {self.screen_id} from {self.current_rotation} to {new_rotation}')
                    self.current_rotation = new_rotation
                    
                    # Re-send last content with new rotation
                    if self.last_content is not None:
                        self._resend_with_rotation()
                        
        except Exception as e:
            self.get_logger().warn(f'Error in orientation check: {str(e)}')

    def _resend_with_rotation(self):
        """Re-send the last content with current rotation"""
        if self.last_content is None:
            return
            
        if self.last_content_type == 'image':
            self.draw_image(self.last_content['data'], 
                          self.last_content['resolution'],
                          self.last_content['delay'])
        elif self.last_content_type == 'text':
            self.draw_text(self.last_content['bg_color'],
                          self.last_content['font_color'], 
                          self.last_content['texts'])

    def draw_image(self, image_data: bytes, resolution: ImageResolution = ImageResolution.RES_480x480, 
                  delay_time: int = 0):
        """Draw an image on the screen with current rotation"""
        try:
            # Store content for potential re-rotation
            self.last_content = {
                'data': image_data,
                'resolution': resolution,
                'delay': delay_time
            }
            self.last_content_type = 'image'
            
            # Split image into chunks
            chunks = split_image_into_chunks(image_data, CHUNK_SIZE)
            
            # Send image start message
            start_msg = ImageStartMessage(
                image_id=self.screen_id,
                image_format=ImageFormat.JPEG,  # Assume JPEG for now
                resolution=resolution,
                delay_time=delay_time,
                total_size=len(image_data),
                num_chunks=len(chunks),
                rotation=self.current_rotation,
                msg_id=self.get_next_msg_id()
            )
            self.send_message(start_msg)
            
            # Send image chunks
            for chunk_id, start_location, chunk_data in chunks:
                chunk_msg = ImageChunkMessage(
                    image_id=self.screen_id,
                    chunk_id=chunk_id,
                    start_location=start_location,
                    chunk_data=chunk_data,
                    msg_id=self.get_next_msg_id()
                )
                self.send_message(chunk_msg)
            
            # Send image end message
            end_msg = ImageEndMessage(
                image_id=self.screen_id,
                msg_id=self.get_next_msg_id()
            )
            self.send_message(end_msg)
            
            self.get_logger().debug(f'Sent image to screen {self.screen_id} with rotation {self.current_rotation}')
            
        except Exception as e:
            self.get_logger().error(f'Error drawing image: {str(e)}')

    def draw_text(self, bg_color: int, font_color: int, texts: List[Tuple[int, int, int, str]]):
        """Draw text on the screen with current rotation"""
        try:
            # Store content for potential re-rotation
            self.last_content = {
                'bg_color': bg_color,
                'font_color': font_color,
                'texts': texts
            }
            self.last_content_type = 'text'
            
            # Create text message
            text_msg = TextMessage(msg_id=self.get_next_msg_id())
            text_msg.add_text_group(bg_color, font_color, texts, self.current_rotation)
            
            self.send_message(text_msg)
            
            self.get_logger().debug(f'Sent text to screen {self.screen_id} with rotation {self.current_rotation}')
            
        except Exception as e:
            self.get_logger().error(f'Error drawing text: {str(e)}')

    def set_auto_rotate(self, enabled: bool):
        """Enable or disable auto-rotation"""
        self.auto_rotate = enabled
        if enabled and not hasattr(self, 'orientation_timer'):
            self.orientation_timer = self.create_timer(0.1, self.check_orientation)
        elif not enabled and hasattr(self, 'orientation_timer'):
            self.orientation_timer.cancel()
            delattr(self, 'orientation_timer')

    def set_rotation(self, rotation: Rotation):
        """Manually set screen rotation (disables auto-rotate)"""
        self.set_auto_rotate(False)
        old_rotation = self.current_rotation
        self.current_rotation = rotation
        
        if old_rotation != rotation and self.last_content is not None:
            self._resend_with_rotation()
            
        self.get_logger().info(f'Manually set screen {self.screen_id} rotation to {rotation}')

    def destroy_node(self):
        """Clean shutdown"""
        if hasattr(self, 'orientation_timer'):
            self.orientation_timer.cancel()
        super().destroy_node()


# Legacy Screen class for backwards compatibility
class Screen:
    """
    Legacy screen class for backwards compatibility
    """

    def __init__(self, uid, bus, dev, bus_obj):
        self.id = uid
        self.spi_device = SPIDevice(uid, bus, dev)
        self.last_img_id = 0
        bus_obj.register(self.spi_device)
        self.bus = bus_obj

    def draw_img(self, img_bytes, img_res=IMG_RES_480SQ, frame_time=0, orientation=0):
        """Legacy image drawing method"""
        pass

    def draw_text(self, color, text_list, lang):
        """Legacy text drawing method"""
        pass

    def draw_option(self, menu_items):
        """Legacy option drawing method"""
        pass

    def send_array(self, barray):
        """Legacy array sending method"""
        self.bus.queue((self.spi_device, TXT_CMD, barray))


if __name__ == "__main__":
    print("Error, calling module screen directly!")