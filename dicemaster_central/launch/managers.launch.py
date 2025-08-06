#!/usr/bin/env python3
"""
Launch script for the DiceMaster Notification Manager
"""

import rclpy
from rclpy.node import Node
from dicemaster_central.managers.notifications import NotificationManager


def main():
    """Launch the notification manager"""
    rclpy.init()
    
    # Create and start notification manager
    notification_manager = NotificationManager()
    
    try:
        rclpy.spin(notification_manager)
    except KeyboardInterrupt:
        notification_manager.get_logger().info('Notification Manager shutting down')
    finally:
        notification_manager.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
