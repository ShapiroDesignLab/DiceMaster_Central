"""
Helper utility for sending notifications to the DiceMaster notification system.

This provides a simple interface for other ROS nodes to send notifications
without dealing with the message publishing details.
"""

import rclpy
from rclpy.node import Node
from dicemaster_central_msgs.msg import NotificationRequest
from typing import Optional


class NotificationHelper:
    """
    Helper class for sending notifications to the DiceMaster system.
    
    This class provides a simple interface for other nodes to send
    INFO and ERROR notifications to screens.
    """
    
    def __init__(self, node: Node):
        """
        Initialize the notification helper.
        
        Args:
            node: The ROS node that will publish notifications
        """
        self.node = node
        self.publisher = node.create_publisher(
            NotificationRequest,
            '/dice_system/notifications',
            10
        )
        
        # Give the publisher time to be established
        import time
        time.sleep(0.1)
    
    def info(self, screen_id: int, message: str, duration: float = 5.0) -> None:
        """
        Send an INFO notification.
        
        Args:
            screen_id: Target screen ID
            message: Notification message
            duration: Display duration in seconds
        """
        self._send_notification(screen_id, 'info', message, duration)
    
    def error(self, screen_id: int, message: str, duration: float = 5.0) -> None:
        """
        Send an ERROR notification.
        
        Args:
            screen_id: Target screen ID  
            message: Notification message
            duration: Display duration in seconds
        """
        self._send_notification(screen_id, 'error', message, duration)
    
    def _send_notification(self, screen_id: int, level: str, message: str, duration: float) -> None:
        """
        Internal method to send a notification.
        
        Args:
            screen_id: Target screen ID
            level: Notification level ('info' or 'error')
            message: Notification message
            duration: Display duration in seconds
        """
        msg = NotificationRequest()
        msg.screen_id = screen_id
        msg.level = level
        msg.content = message
        msg.duration = duration
        
        self.publisher.publish(msg)
        
        # Log the notification
        self.node.get_logger().info(
            f"Sent {level.upper()} notification to screen {screen_id}: "
            f"'{message[:30]}{'...' if len(message) > 30 else ''}'"
        )


class NotificationMixin:
    """
    Mixin class that can be added to any ROS node to provide notification capabilities.
    
    Usage:
        class MyNode(Node, NotificationMixin):
            def __init__(self):
                super().__init__('my_node')
                self.init_notifications()
            
            def some_method(self):
                self.notify_info(0, "Operation completed successfully")
                self.notify_error(0, "Critical error occurred!")
    """
    
    def init_notifications(self):
        """Initialize the notification system for this node."""
        if not hasattr(self, 'get_logger'):
            raise TypeError("NotificationMixin can only be used with ROS Node classes")
        
        self._notification_helper = NotificationHelper(self)
    
    def notify_info(self, screen_id: int, message: str, duration: float = 5.0) -> None:
        """Send an INFO notification."""
        if hasattr(self, '_notification_helper'):
            self._notification_helper.info(screen_id, message, duration)
        else:
            self.get_logger().warn("Notifications not initialized. Call init_notifications() first.")
    
    def notify_error(self, screen_id: int, message: str, duration: float = 5.0) -> None:
        """Send an ERROR notification."""
        if hasattr(self, '_notification_helper'):
            self._notification_helper.error(screen_id, message, duration)
        else:
            self.get_logger().warn("Notifications not initialized. Call init_notifications() first.")


# Convenience functions for standalone usage
_global_node: Optional[Node] = None
_global_helper: Optional[NotificationHelper] = None


def init_global_notifications(node_name: str = 'notification_client') -> None:
    """
    Initialize global notification functions.
    
    This allows using send_info() and send_error() functions without
    managing a node or helper instance.
    
    Args:
        node_name: Name for the internal ROS node
    """
    global _global_node, _global_helper
    
    if _global_node is None:
        _global_node = Node(node_name)
        _global_helper = NotificationHelper(_global_node)


def send_info(screen_id: int, message: str, duration: float = 5.0) -> None:
    """
    Send an INFO notification using global helper.
    
    Note: Must call init_global_notifications() first.
    """
    if _global_helper is None:
        raise RuntimeError("Global notifications not initialized. Call init_global_notifications() first.")
    
    _global_helper.info(screen_id, message, duration)


def send_error(screen_id: int, message: str, duration: float = 5.0) -> None:
    """
    Send an ERROR notification using global helper.
    
    Note: Must call init_global_notifications() first.
    """
    if _global_helper is None:
        raise RuntimeError("Global notifications not initialized. Call init_global_notifications() first.")
    
    _global_helper.error(screen_id, message, duration)


def cleanup_global_notifications() -> None:
    """Clean up global notification resources."""
    global _global_node, _global_helper
    
    if _global_node is not None:
        _global_node.destroy_node()
        _global_node = None
        _global_helper = None
