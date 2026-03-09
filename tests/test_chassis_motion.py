"""Test motion detection integrated into chassis orientation pipeline."""
import numpy as np
import os

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHASSIS_PATH = os.path.join(
    _REPO, "dicemaster_central", "dicemaster_central", "hw", "chassis.py"
)


def test_chassis_has_motion_publisher():
    """Chassis source should create /imu/motion publisher."""
    with open(CHASSIS_PATH) as f:
        source = f.read()
    assert "'/imu/motion'" in source or '"/imu/motion"' in source


def test_chassis_has_shake_detection():
    """Chassis source should contain shake detection logic."""
    with open(CHASSIS_PATH) as f:
        source = f.read()
    assert "_detect_shaking" in source
    assert "_get_shake_intensity" in source
    assert "_get_stillness_factor" in source


def test_chassis_processes_accel_gyro():
    """Chassis imu_callback should process linear_acceleration and angular_velocity."""
    with open(CHASSIS_PATH) as f:
        source = f.read()
    assert "linear_acceleration" in source
    assert "angular_velocity" in source


def test_chassis_no_separate_motion_node_import():
    """Chassis should not import MotionDetectorNode -- logic is inline."""
    with open(CHASSIS_PATH) as f:
        source = f.read()
    assert "MotionDetectorNode" not in source


def test_shake_detection_algorithm():
    """Validate the shake detection math works standalone."""
    from collections import deque

    history_size = 50
    accel_history = deque(maxlen=history_size)
    gyro_history = deque(maxlen=history_size)

    # Simulate still state -- low variance
    rng = np.random.default_rng(42)
    for _ in range(25):
        accel_history.append(9.81 + rng.normal(0, 0.05))
        gyro_history.append(abs(rng.normal(0, 0.1)))

    recent_accel = list(accel_history)[-20:]
    accel_std = np.std(recent_accel)
    assert accel_std < 5.0, "Still state should not trigger shake"

    # Simulate shaking -- high variance
    for _ in range(25):
        accel_history.append(9.81 + rng.normal(0, 8.0))
        gyro_history.append(abs(rng.normal(0, 6.0)))

    recent_accel = list(accel_history)[-20:]
    recent_gyro = list(gyro_history)[-20:]
    accel_std = np.std(recent_accel)
    gyro_mean = np.mean(recent_gyro)
    shaking = accel_std > 5.0 or gyro_mean > 5.0
    assert shaking, "Shaking state should trigger shake detection"
