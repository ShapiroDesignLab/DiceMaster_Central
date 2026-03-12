"""Motion detection — shake callbacks and polling via ROS2 subscription."""

from dice._runtime import get_node, register_subscription
from dicemaster_central_msgs.msg import MotionDetection

_shake_handlers: list = []
_shaking: bool = False
_intensity: float = 0.0
_subscribed: bool = False


def on_shake(handler) -> None:
    global _subscribed
    _shake_handlers.append(handler)
    if not _subscribed:
        node = get_node()
        sub = node.create_subscription(MotionDetection, "/imu/motion", _on_motion, 10)
        register_subscription(sub)
        _subscribed = True


def is_shaking() -> bool:
    _ensure_subscribed()
    return _shaking


def shake_intensity() -> float:
    _ensure_subscribed()
    return _intensity


def _ensure_subscribed() -> None:
    global _subscribed
    if not _subscribed:
        node = get_node()
        sub = node.create_subscription(MotionDetection, "/imu/motion", _on_motion, 10)
        register_subscription(sub)
        _subscribed = True


def _on_motion(msg: MotionDetection) -> None:
    global _shaking, _intensity
    _shaking = msg.shaking
    _intensity = msg.shake_intensity
    if msg.shaking:
        for handler in _shake_handlers:
            handler(msg.shake_intensity)


def _reset() -> None:
    global _shaking, _intensity, _subscribed
    _shake_handlers.clear()
    _shaking = False
    _intensity = 0.0
    _subscribed = False
