#!/usr/bin/env python3
"""
Example script demonstrating how to send notifications to the DiceMaster notification system.

This shows how other ROS nodes can publish notifications to the /dice_system/notifications topic.
"""

import rclpy
from rclpy.node import Node
import time
from DiceMaster_Central.msg import NotificationRequest


class NotificationTester(Node):
    """Test node that demonstrates sending notifications"""
    
    def __init__(self):
        super().__init__('notification_tester')
        
        # Create publisher for notifications
        self.notification_publisher = self.create_publisher(
            NotificationRequest,
            '/dice_system/notifications',
            10
        )
        
        # Wait for publisher to be established
        time.sleep(1)
        
        self.get_logger().info('Notification Tester ready - sending test notifications')
        
        # Send some test notifications
        self.send_test_notifications()
    
    def send_test_notifications(self):
        """Send various test notifications"""
        
        # Send an INFO notification
        self.send_notification(
            screen_id=0,
            level='info',
            content='System startup complete. All sensors initialized successfully.',
            duration=3.0
        )
        
        time.sleep(4)
        
        # Send an ERROR notification
        self.send_notification(
            screen_id=0,
            level='error',
            content='Battery level is critically low! Please connect charger immediately.',
            duration=5.0
        )
        
        time.sleep(6)
        
        # Send a longer INFO notification to test text wrapping
        self.send_notification(
            screen_id=0,
            level='info',
            content='This is a longer notification message that should wrap across multiple lines to demonstrate the text wrapping functionality of the notification system.',
            duration=4.0
        )
        
    def send_notification(self, screen_id: int, level: str, content: str, duration: float = 5.0):
        """
        Send a notification message.
        
        Args:
            screen_id: Target screen ID
            level: Notification level ('info' or 'error')
            content: Notification content
            duration: Display duration in seconds
        """
        msg = NotificationRequest()
        msg.screen_id = screen_id
        msg.level = level
        msg.content = content
        msg.duration = duration
        
        self.notification_publisher.publish(msg)
        self.get_logger().info(f"Sent {level.upper()} notification: '{content[:30]}...'")


def main():
    """Main entry point"""
    rclpy.init()
    
    tester = NotificationTester()
    
    try:
        # Keep the node alive for a bit to send notifications
        rclpy.spin_once(tester, timeout_sec=15)
    except KeyboardInterrupt:
        pass
    finally:
        tester.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
