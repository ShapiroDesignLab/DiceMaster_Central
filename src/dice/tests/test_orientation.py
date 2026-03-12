from dice import orientation
from dicemaster_central_msgs.msg import ChassisOrientation


def _make_orientation_msg(top=1, bottom=6):
    msg = ChassisOrientation()
    msg.top_screen_id = top
    msg.bottom_screen_id = bottom
    return msg


def test_on_change_creates_subscription(mock_runtime):
    orientation.on_change(lambda t, b: None)
    topics = [s.topic for s in mock_runtime.subscriptions_]
    assert "/chassis/orientation" in topics


def test_on_change_callback(mock_runtime):
    called = []
    orientation.on_change(lambda t, b: called.append((t, b)))
    sub = mock_runtime.subscriptions_[-1]
    sub.callback(_make_orientation_msg(top=3, bottom=4))
    assert called == [(3, 4)]


def test_top_default(mock_runtime):
    assert orientation.top() == 1


def test_bottom_default(mock_runtime):
    assert orientation.bottom() == 6


def test_state_updates(mock_runtime):
    orientation.on_change(lambda t, b: None)
    sub = mock_runtime.subscriptions_[-1]
    sub.callback(_make_orientation_msg(top=5, bottom=2))
    assert orientation.top() == 5
    assert orientation.bottom() == 2


def test_subscription_created_once(mock_runtime):
    orientation.on_change(lambda t, b: None)
    orientation.on_change(lambda t, b: None)
    topics = [s.topic for s in mock_runtime.subscriptions_ if s.topic == "/chassis/orientation"]
    assert len(topics) == 1
