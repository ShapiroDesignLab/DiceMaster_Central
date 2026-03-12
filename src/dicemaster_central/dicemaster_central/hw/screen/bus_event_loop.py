"""
Event-driven SPI bus loop for DiceMaster screens.

One BusEventLoop per SPI bus. The ROS executor thread enqueues Events and
notifies the condition. The loop thread blocks on condition.wait(timeout),
where timeout is the next GIF frame deadline. All SPI sends happen here.
"""
from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from dicemaster_central.constants import GIF_FRAME_TIME, Rotation

if TYPE_CHECKING:
    from dicemaster_central.hw.screen.screen import Screen
    from dicemaster_central.hw.screen.spi_device import SPIDevice


class EventType(Enum):
    NEW_CONTENT      = auto()
    ROTATION_CHANGED = auto()
    SHUTDOWN         = auto()


@dataclass
class Event:
    type: EventType
    screen_id: int
    payload: Any = None  # ScreenMediaCmd for NEW_CONTENT, Rotation for ROTATION_CHANGED


class BusEventLoop:
    """
    Single event loop thread per SPI bus.

    Public API (called from ROS executor thread):
        enqueue(event)  — thread-safe, wakes the loop
        start()         — launch the loop thread
        stop()          — enqueue SHUTDOWN and join
    """

    def __init__(
        self,
        bus_id: int,
        screens: Dict[int, 'Screen'],
        spi_device: 'SPIDevice',
        bus_min_interval_s: float,
        logger,
    ):
        self.bus_id = bus_id
        self.screens = screens
        self.spi = spi_device
        self.bus_min_interval_s = bus_min_interval_s
        self.logger = logger

        self.condition = threading.Condition(threading.Lock())
        self._event_deque: deque[Event] = deque()
        self._last_send_time: float = 0.0
        self._thread: Optional[threading.Thread] = None

    # ------------------------------------------------------------------
    # Public API (ROS executor thread)
    # ------------------------------------------------------------------

    def enqueue(self, event: Event) -> None:
        with self.condition:
            self._event_deque.append(event)
            self.condition.notify_all()

    def start(self) -> None:
        self._thread = threading.Thread(
            target=self._run, name=f"bus_loop_{self.bus_id}", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self.enqueue(Event(type=EventType.SHUTDOWN, screen_id=0))
        if self._thread:
            self._thread.join(timeout=3.0)
            if self._thread.is_alive():
                self.logger.error(
                    f"BusEventLoop bus {self.bus_id}: thread did not stop within 3s"
                )

    # ------------------------------------------------------------------
    # Event loop (bus thread only)
    # ------------------------------------------------------------------

    def _run(self) -> None:
        self.logger.debug(f"BusEventLoop started for bus {self.bus_id}")
        while True:
            timeout = self._next_gif_deadline()
            with self.condition:
                self.condition.wait(timeout=timeout)
                events = list(self._event_deque)
                self._event_deque.clear()

            # Handle SHUTDOWN first
            for ev in events:
                if ev.type == EventType.SHUTDOWN:
                    self.logger.debug(f"BusEventLoop shutdown for bus {self.bus_id}")
                    return

            # Drain content/rotation events
            for ev in events:
                if ev.type == EventType.NEW_CONTENT:
                    self._handle_new_content(ev)
                elif ev.type == EventType.ROTATION_CHANGED:
                    self._handle_rotation(ev)

            # Advance GIF frames whose deadline has passed
            for screen in self.screens.values():
                if screen.gif_active and time.monotonic() >= screen.next_frame_time:
                    self._send_gif_frame(screen)
                    screen.next_frame_time = time.monotonic() + GIF_FRAME_TIME

    def _next_gif_deadline(self) -> Optional[float]:
        """Return seconds until earliest GIF frame deadline, or None if no active GIFs."""
        now = time.monotonic()
        deadlines = [
            s.next_frame_time - now
            for s in self.screens.values()
            if s.gif_active
        ]
        if not deadlines:
            return None
        return max(0.0, min(deadlines))

    # ------------------------------------------------------------------
    # Event handlers (bus thread only)
    # ------------------------------------------------------------------

    def _handle_new_content(self, ev: Event) -> None:
        screen = self.screens.get(ev.screen_id)
        if screen is None:
            self.logger.warn(f"NEW_CONTENT for unknown screen {ev.screen_id}")
            return
        screen.process_media(ev.payload)
        msgs = screen.current_msgs()
        if msgs:
            self._rate_limited_send(msgs)

    def _handle_rotation(self, ev: Event) -> None:
        screen = self.screens.get(ev.screen_id)
        if screen is None:
            return
        new_rotation = Rotation(ev.payload)
        if new_rotation == screen.current_rotation:
            return
        screen.current_rotation = new_rotation
        if screen.gif_active:
            screen.gif_rotation = new_rotation
            return
        msgs = screen.resend_with_rotation()
        if msgs:
            self._rate_limited_send(msgs)

    def _send_gif_frame(self, screen: 'Screen') -> None:
        msgs = screen.advance_gif_frame()
        if msgs:
            self._rate_limited_send(msgs)

    # ------------------------------------------------------------------
    # SPI send with rate limiter (bus thread only)
    # ------------------------------------------------------------------

    def _rate_limited_send(self, msgs) -> None:
        now = time.monotonic()
        gap = now - self._last_send_time
        if gap < self.bus_min_interval_s:
            time.sleep(self.bus_min_interval_s - gap)
        if not isinstance(msgs, list):
            msgs = [msgs]
        for msg in msgs:
            self.spi.send(msg.payload)
        self._last_send_time = time.monotonic()
