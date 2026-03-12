import threading
import time
from unittest.mock import MagicMock
from dicemaster_central.hw.screen.bus_event_loop import BusEventLoop, Event, EventType


def _make_loop():
    """Build a BusEventLoop with mocked SPI and screens."""
    mock_spi = MagicMock()
    mock_spi.send = MagicMock()
    screens = {}
    loop = BusEventLoop(
        bus_id=0,
        screens=screens,
        spi_device=mock_spi,
        bus_min_interval_s=0.0,  # no rate limit in tests
        logger=MagicMock(),
    )
    return loop, mock_spi, screens


def test_event_type_values():
    assert EventType.NEW_CONTENT != EventType.ROTATION_CHANGED
    assert EventType.SHUTDOWN != EventType.NEW_CONTENT


def test_enqueue_wakes_loop():
    """Enqueue an event and verify the condition is notified."""
    loop, _, _ = _make_loop()
    notified = threading.Event()

    original_notify = loop.condition.notify_all
    def spy_notify():
        notified.set()
        original_notify()
    loop.condition.notify_all = spy_notify

    loop.enqueue(Event(type=EventType.SHUTDOWN, screen_id=0))
    assert notified.wait(timeout=1.0), "condition.notify_all was not called"


def test_shutdown_stops_loop():
    """Start the loop, send SHUTDOWN, verify thread exits."""
    loop, _, _ = _make_loop()
    loop.start()
    loop.enqueue(Event(type=EventType.SHUTDOWN, screen_id=0))
    loop._thread.join(timeout=2.0)
    assert not loop._thread.is_alive(), "Event loop thread did not stop"
