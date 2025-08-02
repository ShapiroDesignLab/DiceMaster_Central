"""
U-M Shapiro Design Lab
DiceMaster Notification Manager

ROS2 node that provides services to send notifications to screens with different logging levels.
Supports INFO and ERROR notifications with appropriate colors and formatting.
"""

import rclpy
from rclpy.node import Node
from rclpy.service import Service
from typing import Dict, Optional, List, Tuple
import threading
import time

# DiceMaster imports
from dicemaster_central.data_types.media_types import VirtualTextGroup
from dicemaster_central.hw.screen import ScreenManager, ScreenRequest, ContentType
from dicemaster_central.config.constants import Rotation

# ROS message imports  
from dicemaster_central_msgs.msg import NotificationRequest


class NotificationManager(Node):
    """
    ROS2 node that manages notifications to screens.
    
    Listens to the /dice_system/notifications topic for notification requests
    and displays them with appropriate colors and formatting.
    """
    
    # Color constants (RGB565 format)
    COLOR_WHITE = 0xFFFF      # White background
    COLOR_BLACK = 0x0000      # Black text
    COLOR_RED = 0xF800        # Red text for errors
    
    def __init__(self, screen_manager: Optional[ScreenManager] = None):
        super().__init__('notification_manager')
        
        # Screen manager for sending notifications
        self.screen_manager = screen_manager
        
        # Request ID counter for tracking notifications
        self.request_id_counter = 0
        self.request_lock = threading.Lock()
        
        # Create subscriber for notification requests
        self.notification_subscriber = self.create_subscription(
            NotificationRequest,
            '/dice_system/notifications',
            self._handle_notification_message,
            10  # QoS depth
        )
        
        self.get_logger().info('Notification Manager initialized - listening on /dice_system/notifications')
    
    def set_screen_manager(self, screen_manager: ScreenManager):
        """Set the screen manager after initialization"""
        self.screen_manager = screen_manager
    
    def _get_next_request_id(self) -> int:
        """Get next unique request ID"""
        with self.request_lock:
            self.request_id_counter = (self.request_id_counter + 1) % 65536
            return self.request_id_counter
    
    def _handle_notification_message(self, msg: NotificationRequest):
        """Handle incoming notification messages from the topic"""
        try:
            # Extract message data
            screen_id = msg.screen_id
            level = msg.level.lower()
            content = msg.content
            duration = msg.duration if msg.duration > 0 else 5.0
            
            # Validate inputs
            if level not in ['info', 'error']:
                self.get_logger().error(f"Invalid notification level: {level}. Must be 'info' or 'error'")
                return
            
            if not content.strip():
                self.get_logger().error("Notification content cannot be empty")
                return
            
            # Check if screen manager is available
            if not self.screen_manager:
                self.get_logger().error("Screen manager not available")
                return
            
            # Create notification text group
            notification_text_group = self._create_notification_text_group(level, content)
            
            # Create screen request
            screen_request = ScreenRequest(
                screen_id=screen_id,
                content_type=ContentType.TEXT,
                request_id=0,  # Will be set by screen manager
                text_content="",  # Not used for VirtualTextGroup
                bg_color=notification_text_group.bg_color,
                font_color=notification_text_group.font_color,
                virtual_text_group=notification_text_group
            )
            
            # Queue the request
            request_id = self.screen_manager.queue_request(screen_request)
            
            # Log the notification
            self.get_logger().info(
                f"Processed {level.upper()} notification to screen {screen_id}: "
                f"'{content[:50]}{'...' if len(content) > 50 else ''}' (request_id: {request_id})"
            )
            
        except Exception as e:
            self.get_logger().error(f"Error handling notification message: {str(e)}")
    
    def _create_notification_text_group(self, level: str, content: str) -> VirtualTextGroup:
        """
        Create a VirtualTextGroup for the notification.
        
        Args:
            level: Notification level ('info' or 'error')
            content: Notification content text
            
        Returns:
            VirtualTextGroup configured for the notification
        """
        # Determine colors based on level
        if level == 'info':
            bg_color = self.COLOR_WHITE
            font_color = self.COLOR_BLACK
            level_text = "[INFO]"
        else:  # error
            bg_color = self.COLOR_WHITE
            font_color = self.COLOR_RED
            level_text = "[ERROR]"
        
        # Format text content
        # First line: level indicator at top-left
        # Subsequent lines: content starting from next line
        texts = []
        
        # Add level indicator at top-left (10, 20)
        texts.append((10, 20, 0, level_text))  # font_id=0 for default font
        
        # Split content into lines and add them
        content_lines = self._wrap_text(content, max_width=70)  # Approximate character limit per line
        
        y_position = 50  # Start content below the level indicator
        line_height = 25  # Spacing between lines
        
        for i, line in enumerate(content_lines):
            texts.append((10, y_position + (i * line_height), 0, line))
        
        # Create VirtualTextGroup
        virtual_text_group = VirtualTextGroup(
            file_path="virtual://notification",  # Virtual file path identifier
            bg_color=bg_color,
            font_color=font_color,
            texts=texts
        )
        
        return virtual_text_group
    
    def _wrap_text(self, text: str, max_width: int = 70) -> List[str]:
        """
        Wrap text into lines that fit within the specified character width.
        
        Args:
            text: Text to wrap
            max_width: Maximum characters per line
            
        Returns:
            List of text lines
        """
        words = text.split()
        lines = []
        current_line = ""
        
        for word in words:
            # Check if adding this word would exceed the line length
            test_line = current_line + (" " if current_line else "") + word
            
            if len(test_line) <= max_width:
                current_line = test_line
            else:
                # Start a new line
                if current_line:
                    lines.append(current_line)
                    current_line = word
                else:
                    # Word is longer than max_width, split it
                    lines.append(word[:max_width])
                    current_line = word[max_width:]
        
        # Add the last line if there's content
        if current_line:
            lines.append(current_line)
        
        return lines if lines else [""]
    
    def send_info_notification(self, screen_id: int, content: str, duration: float = 5.0) -> bool:
        """
        Convenience method to send an INFO notification.
        
        Args:
            screen_id: Target screen ID
            content: Notification content
            duration: Display duration in seconds
            
        Returns:
            True if notification was queued successfully
        """
        return self._send_notification_direct(screen_id, "info", content, duration)
    
    def send_error_notification(self, screen_id: int, content: str, duration: float = 5.0) -> bool:
        """
        Convenience method to send an ERROR notification.
        
        Args:
            screen_id: Target screen ID
            content: Notification content
            duration: Display duration in seconds
            
        Returns:
            True if notification was queued successfully
        """
        return self._send_notification_direct(screen_id, "error", content, duration)
    
    def _send_notification_direct(self, screen_id: int, level: str, content: str, duration: float) -> bool:
        """
        Direct method to send notifications without going through ROS service.
        Useful for internal notifications or when called from other nodes.
        """
        try:
            if not self.screen_manager:
                self.get_logger().error("Screen manager not available for direct notification")
                return False
            
            # Create notification text group
            notification_text_group = self._create_notification_text_group(level, content)
            
            # Create screen request
            screen_request = ScreenRequest(
                screen_id=screen_id,
                content_type=ContentType.TEXT,
                request_id=0,
                text_content="",
                bg_color=notification_text_group.bg_color,
                font_color=notification_text_group.font_color,
                virtual_text_group=notification_text_group
            )
            
            # Queue the request
            request_id = self.screen_manager.queue_request(screen_request)
            
            # Log the notification
            self.get_logger().info(
                f"Sent {level.upper()} notification to screen {screen_id}: "
                f"'{content[:50]}{'...' if len(content) > 50 else ''}'"
            )
            
            return True
            
        except Exception as e:
            self.get_logger().error(f"Error sending direct notification: {str(e)}")
            return False


def main(args=None):
    """Main entry point for the notification manager node"""
    rclpy.init(args=args)
    
    # Create notification manager
    notification_manager = NotificationManager()
    
    try:
        # Spin the node
        rclpy.spin(notification_manager)
    except KeyboardInterrupt:
        notification_manager.get_logger().info('Notification Manager shutting down')
    finally:
        notification_manager.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
