"""
conftest.py — stub out ROS2 dependencies so config/constants tests can run on macOS.
"""
import sys
from unittest.mock import MagicMock

# Stub rclpy and its submodules before any test imports trigger dicemaster_central.__init__
for mod in ['rclpy', 'rclpy.node', 'rclpy.action', 'rclpy.executors',
            'rclpy.qos', 'rclpy.parameter', 'rclpy.callback_groups',
            'dicemaster_central_msgs', 'dicemaster_central_msgs.msg']:
    sys.modules.setdefault(mod, MagicMock())
