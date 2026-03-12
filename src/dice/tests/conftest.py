import sys
import types
import pytest

# ── Mock ROS2 message types (before any dice imports) ──────────────────────

class ScreenMediaCmd:
    def __init__(self):
        self.screen_id = 0
        self.media_type = 0
        self.file_path = ""

class MotionDetection:
    def __init__(self):
        self.shaking = False
        self.shake_intensity = 0.0

class ChassisOrientation:
    def __init__(self):
        self.top_screen_id = 1
        self.bottom_screen_id = 6

# Only inject mocks if real messages aren't available
if 'dicemaster_central_msgs' not in sys.modules:
    msgs_module = types.ModuleType('dicemaster_central_msgs')
    msg_module = types.ModuleType('dicemaster_central_msgs.msg')
    msg_module.ScreenMediaCmd = ScreenMediaCmd
    msg_module.MotionDetection = MotionDetection
    msg_module.ChassisOrientation = ChassisOrientation
    msgs_module.msg = msg_module
    sys.modules['dicemaster_central_msgs'] = msgs_module
    sys.modules['dicemaster_central_msgs.msg'] = msg_module


# ── Mock ROS2 Node ─────────────────────────────────────────────────────────

class MockPublisher:
    def __init__(self):
        self.messages = []

    def publish(self, msg):
        self.messages.append(msg)


class MockSubscription:
    def __init__(self, msg_type, topic, callback, qos):
        self.msg_type = msg_type
        self.topic = topic
        self.callback = callback
        self.qos = qos


class MockLogger:
    def __init__(self):
        self.messages = []

    def info(self, msg):
        self.messages.append(("info", msg))

    def warn(self, msg):
        self.messages.append(("warn", msg))

    def error(self, msg):
        self.messages.append(("error", msg))

    def debug(self, msg):
        self.messages.append(("debug", msg))


class MockNode:
    def __init__(self):
        self.publishers_ = {}
        self.subscriptions_ = []
        self.timers_ = []
        self._logger = MockLogger()

    def create_publisher(self, msg_type, topic, qos):
        pub = MockPublisher()
        self.publishers_[topic] = pub
        return pub

    def create_subscription(self, msg_type, topic, callback, qos):
        sub = MockSubscription(msg_type, topic, callback, qos)
        self.subscriptions_.append(sub)
        return sub

    def create_timer(self, period, callback):
        timer = {"period": period, "callback": callback, "cancelled": False}
        self.timers_.append(timer)
        return timer

    def destroy_publisher(self, pub):
        pass

    def destroy_subscription(self, sub):
        pass

    def destroy_timer(self, timer):
        timer["cancelled"] = True

    def get_logger(self):
        return self._logger


@pytest.fixture(autouse=True)
def mock_runtime(monkeypatch):
    """Replace the runtime node with a mock for every test."""
    mock_node = MockNode()
    import dice._runtime as runtime_module
    monkeypatch.setattr(runtime_module, "_node", mock_node)
    monkeypatch.setattr(runtime_module, "_initialized", True)
    from dice import _runtime
    _runtime.teardown()
    yield mock_node
