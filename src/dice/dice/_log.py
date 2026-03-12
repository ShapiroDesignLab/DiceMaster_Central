"""Logging — send messages to ROS2 logger."""
from dice._runtime import get_node


def log(message: str) -> None:
    get_node().get_logger().info(message)
