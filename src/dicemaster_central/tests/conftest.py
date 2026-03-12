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
            'dicemaster_central_msgs', 'dicemaster_central_msgs.msg',
            'spidev']:
    sys.modules.setdefault(mod, MagicMock())

# Ensure rclpy.node.Node is a real class so ScreenBusManager can subclass it
import rclpy.node as _rclpy_node
if not isinstance(getattr(_rclpy_node, 'Node', None), type):
    class _StubNode:
        def __init__(self, *args, **kwargs): pass
        def get_logger(self): return MagicMock()
        def create_subscription(self, *args, **kwargs): return MagicMock()
        def destroy_node(self): pass
    _rclpy_node.Node = _StubNode

# Ensure ScreenPose stub has screen_id and rotation attributes
import dicemaster_central_msgs.msg as _msgs
if not isinstance(getattr(_msgs, 'ScreenPose', None), type):
    class _ScreenPose:
        screen_id: int = 0
        rotation: int = 0
    _msgs.ScreenPose = _ScreenPose

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

# Stub hw and hw.screen subpackages so that importing bus_event_loop (and other
# hw.screen modules) does NOT execute the real __init__.py files, which chain
# into pydantic/rclpy unavailable on macOS.
_hw_dir = os.path.join(_pkg_dir, 'hw')
_hw_screen_dir = os.path.join(_hw_dir, 'screen')

for _mod_name, _mod_dir in [
    ('dicemaster_central.hw', _hw_dir),
    ('dicemaster_central.hw.screen', _hw_screen_dir),
]:
    if _mod_name not in sys.modules:
        _mod = types.ModuleType(_mod_name)
        _mod.__path__ = [_mod_dir]
        _mod.__package__ = _mod_name
        _mod.__spec__ = None
        sys.modules[_mod_name] = _mod
