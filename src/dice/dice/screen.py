"""Screen control — set content on dice faces via ROS2 publishers."""

from dice._runtime import get_node, register_publisher
from dicemaster_central_msgs.msg import ScreenMediaCmd

_TEXT = 0
_IMAGE = 1
_GIF = 2

_publishers: dict = {}


def _get_publisher(screen_id: int):
    topic = f"/screen_{screen_id}_cmd"
    if topic not in _publishers:
        node = get_node()
        pub = node.create_publisher(ScreenMediaCmd, topic, 10)
        _publishers[topic] = pub
        register_publisher(topic, pub)
    return _publishers[topic]


def _publish(screen_id: int, media_type: int, path: str) -> None:
    msg = ScreenMediaCmd()
    msg.screen_id = screen_id
    msg.media_type = media_type
    msg.file_path = path
    _get_publisher(screen_id).publish(msg)


def set_text(screen_id: int, path: str) -> None:
    _publish(screen_id, _TEXT, path)


def set_image(screen_id: int, path: str) -> None:
    _publish(screen_id, _IMAGE, path)


def set_gif(screen_id: int, path: str) -> None:
    _publish(screen_id, _GIF, path)


def _reset() -> None:
    _publishers.clear()
