"""
Screen Bus Manager — ROS2 node, one per SPI bus.

Owns subscriptions to /screen_N_cmd and /chassis/screen_N_pose.
Delegates all encoding and SPI work to BusEventLoop.
"""
from typing import Dict

from rclpy.node import Node
from dicemaster_central_msgs.msg import ScreenMediaCmd, ScreenPose

from .screen import Screen
from .spi_device import SPIDevice
from .bus_event_loop import BusEventLoop, Event, EventType

from dicemaster_central.config import dice_config, ScreenConfig


class ScreenBusManager(Node):

    def __init__(self, bus_id: int):
        super().__init__(f'screen_bus_manager_{bus_id}')
        self.bus_id = bus_id

        bus_cfg = dice_config.bus_configs[bus_id]
        screen_cfgs: Dict[int, ScreenConfig] = {
            cfg.id: cfg
            for cfg in dice_config.screen_configs.values()
            if cfg.bus_id == bus_id
        }

        self.spi_device = SPIDevice(
            bus_id=bus_id,
            bus_dev_id=bus_cfg.use_dev,
            spi_config=dice_config.spi_config,
            verbose=False,
        )

        self.screens: Dict[int, Screen] = {
            sid: Screen(node=self, screen_id=sid)
            for sid in screen_cfgs
        }

        self.event_loop = BusEventLoop(
            bus_id=bus_id,
            screens=self.screens,
            spi_device=self.spi_device,
            bus_min_interval_s=bus_cfg.bus_min_interval_s,
            logger=self.get_logger(),
        )

        # ScreenMediaCmd subscriptions — one per screen on this bus
        self._cmd_subs = {
            sid: self.create_subscription(
                ScreenMediaCmd,
                f'/screen_{sid}_cmd',
                self._on_media_cmd,
                10,
            )
            for sid in screen_cfgs
        }

        # ScreenPose subscriptions — moved from Screen, now owned here
        self._pose_subs = {
            sid: self.create_subscription(
                ScreenPose,
                f'/chassis/screen_{sid}_pose',
                self._on_screen_pose,
                10,
            )
            for sid in screen_cfgs
        }

    def start(self) -> None:
        self.event_loop.start()
        self.get_logger().info(f"ScreenBusManager started for bus {self.bus_id}")

    def stop(self) -> None:
        self.event_loop.stop()
        if hasattr(self, 'spi_device'):
            del self.spi_device
        self.get_logger().info(f"ScreenBusManager stopped for bus {self.bus_id}")

    def destroy_node(self) -> None:
        self.stop()
        super().destroy_node()

    # ------------------------------------------------------------------
    # ROS callbacks — enqueue only, return immediately
    # ------------------------------------------------------------------

    def _on_media_cmd(self, msg: ScreenMediaCmd) -> None:
        if msg.screen_id not in self.screens:
            self.get_logger().error(f"Unknown screen_id {msg.screen_id}")
            return
        self.event_loop.enqueue(Event(
            type=EventType.NEW_CONTENT,
            screen_id=msg.screen_id,
            payload=msg,
        ))

    def _on_screen_pose(self, msg: ScreenPose) -> None:
        if msg.screen_id not in self.screens:
            return
        self.event_loop.enqueue(Event(
            type=EventType.ROTATION_CHANGED,
            screen_id=msg.screen_id,
            payload=msg.rotation,  # raw int; BusEventLoop wraps with Rotation(...)
        ))


def main(args=None):
    import sys
    import rclpy
    from rclpy.executors import MultiThreadedExecutor

    if len(sys.argv) < 2:
        print("Usage: screen_bus_manager.py <bus_id>")
        sys.exit(1)

    bus_id = int(sys.argv[1])
    rclpy.init(args=args)
    node = None
    executor = None
    try:
        node = ScreenBusManager(bus_id)
        node.start()
        executor = MultiThreadedExecutor()
        executor.add_node(node)
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        if node:
            node.destroy_node()
        if executor:
            executor.shutdown()


if __name__ == '__main__':
    main()
