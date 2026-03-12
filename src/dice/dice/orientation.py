"""Orientation — track which screen faces up/down via ROS2 subscription."""

from dice._runtime import get_node, register_subscription
from dicemaster_central_msgs.msg import ChassisOrientation

_change_handlers: list = []
_top: int = 1
_bottom: int = 6
_subscribed: bool = False


def on_change(handler) -> None:
    global _subscribed
    _change_handlers.append(handler)
    if not _subscribed:
        node = get_node()
        sub = node.create_subscription(ChassisOrientation, "/chassis/orientation", _on_orientation, 10)
        register_subscription(sub)
        _subscribed = True


def top() -> int:
    _ensure_subscribed()
    return _top


def bottom() -> int:
    _ensure_subscribed()
    return _bottom


def _ensure_subscribed() -> None:
    global _subscribed
    if not _subscribed:
        node = get_node()
        sub = node.create_subscription(ChassisOrientation, "/chassis/orientation", _on_orientation, 10)
        register_subscription(sub)
        _subscribed = True


def _on_orientation(msg: ChassisOrientation) -> None:
    global _top, _bottom
    _top = msg.top_screen_id
    _bottom = msg.bottom_screen_id
    for handler in _change_handlers:
        handler(msg.top_screen_id, msg.bottom_screen_id)


def _reset() -> None:
    global _top, _bottom, _subscribed
    _change_handlers.clear()
    _top = 1
    _bottom = 6
    _subscribed = False
