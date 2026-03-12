"""
Screen — pure data and encoding object.

Holds state for one screen (rotation, last content, GIF frames).
Has no threads or timers. All calls happen on the BusEventLoop thread
except __init__ and destroy (called from ScreenBusManager on the ROS thread).
"""
from __future__ import annotations

from typing import Any, List, Optional

from dicemaster_central_msgs.msg import ScreenMediaCmd
from dicemaster_central.config import dice_config
from dicemaster_central.constants import ContentType, GIF_FRAME_TIME, Rotation

SPI_CHUNK_SIZE = dice_config.spi_config.max_buffer_size


class Screen:
    """
    Pure data/encoding object for one screen.

    BusEventLoop calls process_media(), resend_with_rotation(), advance_gif_frame()
    — always from the bus event loop thread, so no internal locking is needed.
    """

    def __init__(self, node, screen_id: int, bus_manager=None):
        self.screen_id = screen_id
        self.node = node
        self.current_rotation = Rotation.ROTATION_0

        self._last_content: Any = None
        self._last_content_type: Optional[ContentType] = None

        self.gif_active = False
        self.gif_messages: List[List] = []
        self.gif_frame_index = 0
        self.gif_rotation = Rotation.ROTATION_0
        self.next_frame_time: float = 0.0

        self.node.get_logger().info(f"Screen {screen_id} initialized")

    def __repr__(self):
        return f"Screen(screen_id={self.screen_id}, rotation={self.current_rotation})"

    def destroy(self) -> None:
        self.gif_active = False
        self.gif_messages = []
        self.node.get_logger().info(f"Screen {self.screen_id} destroyed")

    # ------------------------------------------------------------------
    # Called by BusEventLoop (bus thread)
    # ------------------------------------------------------------------

    def process_media(self, request: ScreenMediaCmd) -> None:
        """Encode media and store. Sets up GIF state if media_type is GIF."""
        try:
            if request.media_type == ContentType.TEXT:
                self._process_text(request)
            elif request.media_type == ContentType.IMAGE:
                self._process_image(request)
            elif request.media_type == ContentType.GIF:
                self._process_gif(request)
            else:
                self.node.get_logger().error(f"Unknown media type: {request.media_type}")
        except Exception as e:
            self.node.get_logger().error(
                f"Screen {self.screen_id} process_media error: {e}"
            )

    def current_msgs(self) -> Optional[Any]:
        """Return encoded messages for current TEXT or IMAGE content. None for GIF."""
        if self._last_content_type in (ContentType.TEXT, ContentType.IMAGE):
            return self._last_content
        return None

    def resend_with_rotation(self) -> Optional[Any]:
        """Re-encode last static content with current_rotation. Returns messages."""
        if self._last_content is None:
            return None
        try:
            if self._last_content_type == ContentType.TEXT:
                self._last_content.rotation = self.current_rotation
                self._last_content.encode()
                return self._last_content
            elif self._last_content_type == ContentType.IMAGE:
                msgs = self._last_content
                if msgs:
                    msgs[0].rotation = self.current_rotation
                    msgs[0].encode()
                return msgs
            else:
                self.node.get_logger().warn(
                    f"Screen {self.screen_id} resend_with_rotation called with "
                    f"unexpected content type: {self._last_content_type}"
                )
        except Exception as e:
            self.node.get_logger().error(
                f"Screen {self.screen_id} resend_with_rotation error: {e}"
            )
        return None

    def advance_gif_frame(self) -> Optional[List]:
        """Advance to next GIF frame, apply gif_rotation, return message list."""
        if not self.gif_active or not self.gif_messages:
            return None
        msgs = self.gif_messages[self.gif_frame_index]
        msgs[0].rotation = self.gif_rotation
        msgs[0].encode()
        self.gif_frame_index = (self.gif_frame_index + 1) % len(self.gif_messages)
        return msgs

    # ------------------------------------------------------------------
    # Internal encoding helpers
    # ------------------------------------------------------------------

    def _process_text(self, request: ScreenMediaCmd) -> None:
        from dicemaster_central.media_typing.media_types import TextGroup
        self._stop_gif()
        tg = TextGroup(file_path=request.file_path)
        msg = tg.to_msg(rotation=self.current_rotation, screen_id=self.screen_id)
        self._last_content = msg
        self._last_content_type = ContentType.TEXT

    def _process_image(self, request: ScreenMediaCmd) -> None:
        from dicemaster_central.media_typing.media_types import Image as MediaImage
        self._stop_gif()
        img = MediaImage(file_path=request.file_path)
        msgs = img.to_msg(
            rotation=self.current_rotation,
            chunk_size=SPI_CHUNK_SIZE,
            screen_id=self.screen_id,
        )
        self._last_content = msgs
        self._last_content_type = ContentType.IMAGE

    def _process_gif(self, request: ScreenMediaCmd) -> None:
        import time
        from dicemaster_central.media_typing.media_types import GIF
        self._stop_gif()
        gif = GIF(file_path=request.file_path, delay_time=int(GIF_FRAME_TIME * 1000))
        if not gif.frames_data:
            self.node.get_logger().error(f"No GIF frames in {request.file_path}")
            self._last_content = None
            self._last_content_type = None
            return
        self.gif_messages = gif.to_msg(
            rotation=self.current_rotation,
            chunk_size=SPI_CHUNK_SIZE,
            screen_id=self.screen_id,
        )
        self._last_content = self.gif_messages
        self._last_content_type = ContentType.GIF
        self.gif_frame_index = 0
        self.gif_rotation = self.current_rotation
        self.gif_active = True
        self.next_frame_time = time.monotonic()

    def _stop_gif(self) -> None:
        self.gif_active = False
        self.gif_messages = []
        self.gif_frame_index = 0
