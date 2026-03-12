from dice import motion
from dicemaster_central_msgs.msg import MotionDetection


def _make_motion_msg(shaking=False, intensity=0.0):
    msg = MotionDetection()
    msg.shaking = shaking
    msg.shake_intensity = intensity
    return msg


def test_on_shake_creates_subscription(mock_runtime):
    motion.on_shake(lambda i: None)
    topics = [s.topic for s in mock_runtime.subscriptions_]
    assert "/imu/motion" in topics


def test_on_shake_callback(mock_runtime):
    called = []
    motion.on_shake(lambda i: called.append(i))
    sub = mock_runtime.subscriptions_[-1]
    sub.callback(_make_motion_msg(shaking=True, intensity=0.8))
    assert called == [0.8]


def test_on_shake_ignores_non_shaking(mock_runtime):
    called = []
    motion.on_shake(lambda i: called.append(i))
    sub = mock_runtime.subscriptions_[-1]
    sub.callback(_make_motion_msg(shaking=False, intensity=0.0))
    assert called == []


def test_is_shaking_default(mock_runtime):
    assert motion.is_shaking() is False


def test_is_shaking_updates(mock_runtime):
    motion.on_shake(lambda i: None)
    sub = mock_runtime.subscriptions_[-1]
    sub.callback(_make_motion_msg(shaking=True, intensity=0.7))
    assert motion.is_shaking() is True
    sub.callback(_make_motion_msg(shaking=False, intensity=0.0))
    assert motion.is_shaking() is False


def test_shake_intensity(mock_runtime):
    motion.on_shake(lambda i: None)
    sub = mock_runtime.subscriptions_[-1]
    sub.callback(_make_motion_msg(shaking=True, intensity=0.6))
    assert motion.shake_intensity() == 0.6


def test_subscription_created_once(mock_runtime):
    motion.on_shake(lambda i: None)
    motion.on_shake(lambda i: None)
    topics = [s.topic for s in mock_runtime.subscriptions_ if s.topic == "/imu/motion"]
    assert len(topics) == 1
