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


# ---------------------------------------------------------------------------
# Screen tests
# ---------------------------------------------------------------------------

from unittest.mock import MagicMock, patch
from dicemaster_central.constants import ContentType, Rotation


def _make_screen(screen_id=1):
    node = MagicMock()
    from dicemaster_central.hw.screen.screen import Screen
    return Screen(node=node, screen_id=screen_id)


def test_screen_has_no_processing_thread():
    s = _make_screen()
    assert not hasattr(s, 'processing_thread'), "processing_thread should be removed"
    assert not hasattr(s, 'media_processing_queue'), "queue should be removed"


def test_screen_has_gif_fields():
    s = _make_screen()
    assert hasattr(s, 'next_frame_time')
    assert hasattr(s, 'gif_rotation')
    assert s.gif_active is False


def _make_screen_with_mock_text(mock_text_msg):
    """Return a Screen and a mock TextGroup class; patches media_types in sys.modules."""
    import sys
    import types
    mock_text_group_inst = MagicMock()
    mock_text_group_inst.to_msg.return_value = mock_text_msg
    MockTextGroup = MagicMock(return_value=mock_text_group_inst)

    mock_media_types_mod = types.ModuleType('dicemaster_central.media_typing.media_types')
    mock_media_types_mod.TextGroup = MockTextGroup
    mock_media_types_mod.Image = MagicMock()
    mock_media_types_mod.GIF = MagicMock()

    # Also stub the parent package so the local import inside screen.py works
    mock_media_typing_mod = types.ModuleType('dicemaster_central.media_typing')
    mock_media_typing_mod.__path__ = []

    sys.modules.setdefault('dicemaster_central.media_typing', mock_media_typing_mod)
    sys.modules['dicemaster_central.media_typing.media_types'] = mock_media_types_mod
    return _make_screen(), MockTextGroup


def test_screen_process_media_text(tmp_path):
    import json
    cfg = {"bg_color": "0x0000", "texts": [{"x": 10, "y": 10, "font_id": 1,
           "font_color": "0xFFFF", "text": "hi"}]}
    p = tmp_path / "test.json"
    p.write_text(json.dumps(cfg))

    from dicemaster_central_msgs.msg import ScreenMediaCmd
    msg = ScreenMediaCmd()
    msg.screen_id = 1
    msg.media_type = int(ContentType.TEXT)
    msg.file_path = str(p)

    mock_text_msg = MagicMock()
    s, _ = _make_screen_with_mock_text(mock_text_msg)
    s.process_media(msg)
    msgs = s.current_msgs()
    assert msgs is not None


def test_screen_resend_with_rotation(tmp_path):
    import json
    cfg = {"bg_color": "0x0000", "texts": [{"x": 10, "y": 10, "font_id": 1,
           "font_color": "0xFFFF", "text": "hi"}]}
    p = tmp_path / "test.json"
    p.write_text(json.dumps(cfg))

    from dicemaster_central_msgs.msg import ScreenMediaCmd
    msg = ScreenMediaCmd()
    msg.screen_id = 1
    msg.media_type = int(ContentType.TEXT)
    msg.file_path = str(p)

    mock_text_msg = MagicMock()
    mock_text_msg.rotation = Rotation.ROTATION_0
    s, _ = _make_screen_with_mock_text(mock_text_msg)
    s.process_media(msg)
    s.current_rotation = Rotation.ROTATION_90
    result = s.resend_with_rotation()
    assert result is not None
    assert result.rotation == Rotation.ROTATION_90
