from abc import ABC, abstractmethod
from rclpy.node import Node

class BaseStrategy(Node, ABC):
    """
    Base class for all strategies in the DiceMaster Central system.
    Provides common functionality and structure for derived strategy classes.
    """

    def __init__(self, name: str, *args,):
        super().__init__(name)
        self.get_logger().info(f"{name} strategy initialized")
        self.running = True

    @abstractmethod
    def start(self):
        pass

    @abstractmethod
    def stop(self):
        pass