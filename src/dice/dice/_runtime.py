"""Internal runtime — single ROS2 node, lazy init. NOT exposed to students."""
from __future__ import annotations
import typing

if typing.TYPE_CHECKING:
    from rclpy.node import Node

_node: Node | None = None
_initialized: bool = False
_publishers: dict = {}
_subscriptions: list = []


def get_node() -> Node:
    """Get or create the singleton ROS2 node."""
    global _node, _initialized
    if not _initialized:
        import rclpy
        if not rclpy.ok():
            rclpy.init()
        _node = rclpy.create_node('dice_sdk')
        _initialized = True
    return _node


def register_publisher(topic: str, pub) -> None:
    _publishers[topic] = pub


def register_subscription(sub) -> None:
    _subscriptions.append(sub)


def teardown() -> None:
    """Reset all dice module state. Called by game manager between games."""
    # Import here to avoid circular imports at module load time
    from dice import screen as screen_mod
    from dice import motion, orientation, assets
    from dice import timer as timer_mod

    if _node is not None:
        for sub in _subscriptions:
            _node.destroy_subscription(sub)
        for pub in _publishers.values():
            _node.destroy_publisher(pub)

    _publishers.clear()
    _subscriptions.clear()

    screen_mod._reset()
    motion._reset()
    orientation._reset()
    timer_mod._reset()
    assets._reset()
