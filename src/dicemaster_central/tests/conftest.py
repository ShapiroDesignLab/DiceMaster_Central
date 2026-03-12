"""
conftest.py — stub out ROS2 dependencies so config/constants tests can run on macOS.
"""
import sys
import types
import os
from unittest.mock import MagicMock

# Stub rclpy and other unavailable dependencies before any test imports
# trigger dicemaster_central.__init__
for mod in ['rclpy', 'rclpy.node', 'rclpy.action', 'rclpy.executors',
            'rclpy.qos', 'rclpy.parameter', 'rclpy.callback_groups',
            'dicemaster_central_msgs', 'dicemaster_central_msgs.msg']:
    sys.modules.setdefault(mod, MagicMock())

# Pre-register the dicemaster_central package as a lightweight stub so that
# Python does NOT execute __init__.py (which would pull in hw/pydantic/etc.).
# Submodule imports like `from dicemaster_central.config import ...` will still
# resolve to the real .py files because we set __path__ correctly.
_pkg_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'dicemaster_central')
if 'dicemaster_central' not in sys.modules:
    _pkg = types.ModuleType('dicemaster_central')
    _pkg.__path__ = [_pkg_dir]
    _pkg.__package__ = 'dicemaster_central'
    _pkg.__spec__ = None
    sys.modules['dicemaster_central'] = _pkg
