# TF2-Free Chassis with Integrated Motion Detection

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Remove all TF2 infrastructure from the chassis node, merge motion detection into it, and switch to SingleThreadedExecutor to cut CPU from ~51% to ~15% on the Pi.

**Architecture:** The chassis node currently wastes ~36% CPU on TF2 broadcasting/listening that nothing consumes, plus the motion detector runs as a separate node with its own DDS subscription to the same IMU data. We merge both into one node with one IMU subscription, zero TF2 overhead, and a single-threaded executor. The `DiceOrientation.compute()` API (validated by `tests/test_tf_vs_orientation_math.py` — 3527 tests, 571 quaternions, exact match) provides all orientation data without TF lookups.

**Tech Stack:** Python 3.11, ROS2 Humble, scipy, numpy, rclpy

**Validated by:** `tests/test_tf_vs_orientation_math.py` — proves DiceOrientation produces byte-identical results to the TF2 transform chain across 571 diverse quaternions (axis-aligned, tilted, random).

---

## Current State

### CPU breakdown on Pi (measured):
| Component | CPU % |
|-----------|-------|
| ROS2 MultiThreadedExecutor + 50Hz TF broadcast + timers | 36% |
| DDS IMU subscription (50Hz incoming) | ~15% |
| DiceOrientation.compute() + sticky + publishing | ~1% |
| **Total** | **~51%** |

### What gets removed:
- `tf2_ros.Buffer` + `TransformListener` — **dead code** (no lookups remain)
- `StaticTransformBroadcaster` — **declared but never called**
- `TransformBroadcaster` + 50Hz `timer_callback` — publishes `world→imu_link` that **only RViz uses**
- `robot_state_publisher` node from `chassis.launch.py` — publishes URDF TF tree for RViz
- `MultiThreadedExecutor` — no callbacks need concurrency
- Separate `MotionDetectorNode` process — merges into chassis

### What gets added:
- Motion detection logic (from `motion_detector.py`) runs in-process on same IMU data
- Publishes `/imu/motion` from chassis node instead of separate node
- `SingleThreadedExecutor` replaces `MultiThreadedExecutor`

### Files involved:

| File | Action |
|------|--------|
| `dicemaster_central/dicemaster_central/hw/chassis.py` | Modify: remove TF2, add motion detection, switch executor |
| `dicemaster_central/dicemaster_central/hw/imu/motion_detector.py` | Keep as-is (standalone entry point preserved for backward compat) |
| `dicemaster_central/launch/chassis.launch.py` | Modify: remove `robot_state_publisher` |
| `dicemaster_central/launch/imu.launch.py` | Modify: remove `motion_detector` node |
| `dicemaster_central/package.xml` | Modify: remove `tf2_ros`, `tf2_geometry_msgs`, `robot_state_publisher` deps |
| `tests/test_chassis_tf2_removal.py` | Create: verify no TF2 imports, motion detection works |
| `tests/test_chassis_orientation.py` | Exists: update if needed |

### Consumer inventory for removed topics:
- `/tf` (dynamic, `world→imu_link`): only RViz. No other DiceMaster node subscribes.
- `/tf_static` (URDF frames): only RViz. Chassis no longer does TF lookups.
- Downstream consumers of `/chassis/orientation`, `/chassis/screen_N_pose`, `/imu/motion`: **unchanged** — these topics continue to be published.

---

## Task 1: Remove TF2 from chassis.py

**Files:**
- Modify: `dicemaster_central/dicemaster_central/hw/chassis.py`
- Test: `tests/test_chassis_tf2_removal.py`

**Context:** The chassis node imports `tf2_ros`, `TransformBroadcaster`, `StaticTransformBroadcaster`, creates a `tf_buffer`, `tf_listener`, `tf_broadcaster`, `static_tf_broadcaster`, and runs a 50Hz `timer_callback` that calls `_publish_dynamic_transforms()`. None of this is consumed by any DiceMaster node. The `Pose` and `TransformStamped` geometry_msgs are also only used for TF broadcasting.

**Step 1: Write the failing test**

Create `tests/test_chassis_tf2_removal.py`:

```python
"""Verify chassis.py has no TF2 dependencies after removal."""
import ast
import os

CHASSIS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "dicemaster_central", "dicemaster_central", "hw", "chassis.py",
)

def _get_imports(filepath):
    """Extract all import names from a Python file using AST."""
    with open(filepath) as f:
        tree = ast.parse(f.read())
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module)
    return imports

def test_no_tf2_imports():
    imports = _get_imports(CHASSIS_PATH)
    tf2_imports = {i for i in imports if "tf2" in i}
    assert not tf2_imports, f"TF2 imports still present: {tf2_imports}"

def test_no_transform_stamped_import():
    imports = _get_imports(CHASSIS_PATH)
    # TransformStamped is from geometry_msgs, only used for TF
    with open(CHASSIS_PATH) as f:
        source = f.read()
    assert "TransformStamped" not in source, "TransformStamped still referenced"

def test_no_pose_import():
    """Pose was only used to wrap IMU orientation for TF broadcast."""
    with open(CHASSIS_PATH) as f:
        source = f.read()
    assert "from geometry_msgs.msg import Pose" not in source

def test_no_timer_callback_method():
    """The 50Hz TF timer_callback should be removed."""
    with open(CHASSIS_PATH) as f:
        source = f.read()
    assert "def timer_callback" not in source
    assert "_publish_dynamic_transforms" not in source

def test_no_publish_rate_parameter():
    """publish_rate was only for TF broadcast frequency."""
    with open(CHASSIS_PATH) as f:
        source = f.read()
    assert "'publish_rate'" not in source

def test_single_threaded_executor():
    with open(CHASSIS_PATH) as f:
        source = f.read()
    assert "SingleThreadedExecutor" in source
    assert "MultiThreadedExecutor" not in source
```

**Step 2: Run test to verify it fails**

```bash
cd /Users/danielhou/Code/DiceMaster/DiceMaster_Central
python3 -m pytest tests/test_chassis_tf2_removal.py -v
```

Expected: 6 FAIL (TF2 imports still present, etc.)

**Step 3: Remove TF2 from chassis.py**

Remove these imports (lines 10-13):
```python
# DELETE these lines:
from geometry_msgs.msg import Pose, TransformStamped
import tf2_ros
from tf2_ros import TransformBroadcaster, StaticTransformBroadcaster
```

Replace `from geometry_msgs.msg import Pose, TransformStamped` with nothing — `Pose` is no longer needed.

Remove from `__init__` (lines 71-74, 86, 121-125, 176-177):
- Parameter declarations: `base_frame`, `imu_frame`, `world_frame`, `publish_rate`
- Parameter reads: `self.base_frame`, `self.imu_frame`, `self.world_frame`, `self.publish_rate`
- TF2 setup block (lines 121-125): `self.tf_buffer`, `self.tf_listener`, `self.tf_broadcaster`, `self.static_tf_broadcaster`
- 50Hz timer (line 177): `self.timer = self.create_timer(1.0/self.publish_rate, self.timer_callback)`

Remove startup log lines referencing removed params (lines 183-184).

Remove methods:
- `timer_callback` (line 220-223)
- `_publish_dynamic_transforms` (lines 225-254)

Rewrite `imu_callback` — no longer needs `Pose` wrapper, store quaternion directly:
```python
def imu_callback(self, msg):
    """Callback for IMU data — store orientation and motion sensor data."""
    with self.pose_lock:
        self._imu_orientation = msg.orientation
        self.last_pose_time = time.time()
        if not self.imu_connected:
            self.imu_connected = True
            self.get_logger().info('IMU data connected - using live orientation')
```

Rewrite `_get_imu_quaternion`:
```python
def _get_imu_quaternion(self) -> np.ndarray:
    with self.pose_lock:
        o = self._imu_orientation
        return np.array([o.x, o.y, o.z, o.w])
```

Update `__init__` to initialize `self._imu_orientation` instead of `self.current_pose`:
```python
# Replace the current_pose block with:
from geometry_msgs.msg import Quaternion
self._imu_orientation = Quaternion(x=1.0, y=0.0, z=0.0, w=0.0)  # default: pi around X
self.pose_lock = threading.Lock()
self.last_pose_time = None
self.imu_connected = False
```

Update `orientation_callback` — the IMU signal loss check used `self.pose_lock` which still works, but remove the `imu_connected = False` logic that was in `_publish_dynamic_transforms` and move it here:
```python
def orientation_callback(self):
    with self.pose_lock:
        pose_time = self.last_pose_time

    if pose_time is None or time.time() - pose_time > 1.0:
        if self.imu_connected and pose_time is not None:
            self.imu_connected = False
            self.get_logger().warn('IMU signal lost - maintaining last known orientation')
        return
    # ... rest unchanged ...
```

Switch executor in `main()`:
```python
def main(args=None):
    import rclpy
    from rclpy.executors import SingleThreadedExecutor

    rclpy.init(args=args)
    node = None
    executor = None
    try:
        node = ChassisNode()
        executor = SingleThreadedExecutor()
        executor.add_node(node)
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        if node is not None:
            node.destroy_node()
        if executor is not None:
            executor.shutdown()
```

Remove the `timer` cancel from `destroy_node` (only `orientation_timer` remains).

**Step 4: Run tests**

```bash
python3 -m pytest tests/test_chassis_tf2_removal.py tests/test_chassis_orientation.py -v
```

Expected: all pass.

**Step 5: Commit**

```bash
git add dicemaster_central/dicemaster_central/hw/chassis.py tests/test_chassis_tf2_removal.py
git commit -m "refactor: remove TF2 infrastructure from chassis node

TF2 buffer, listener, broadcasters, and 50Hz TF timer removed.
Nothing in the system consumed these transforms.
Switch to SingleThreadedExecutor for lower overhead."
```

---

## Task 2: Integrate motion detection into chassis node

**Files:**
- Modify: `dicemaster_central/dicemaster_central/hw/chassis.py`
- Test: `tests/test_chassis_motion.py`
- Reference: `dicemaster_central/dicemaster_central/hw/imu/motion_detector.py`

**Context:** The `MotionDetectorNode` (in `hw/imu/motion_detector.py`) subscribes to `/imu/data`, maintains accel/gyro magnitude history buffers (deque, size 50), and publishes `MotionDetection` messages to `/imu/motion`. The chassis node already subscribes to the same IMU topic. By processing the accel/gyro data in the same `imu_callback`, we eliminate a second DDS subscription and a second ROS node entirely.

The motion detector's core logic is pure Python with no ROS dependency: `update_motion_data()`, `detect_shaking()`, `get_shake_intensity()`, `get_stillness_factor()`. We copy these methods into the chassis node.

**Step 1: Write the failing test**

Create `tests/test_chassis_motion.py`:

```python
"""Test motion detection integrated into chassis orientation pipeline."""
import numpy as np
import importlib.util
import os
import sys

# Import orientation math without rclpy
_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_MOD = os.path.join(_REPO, "dicemaster_central", "dicemaster_central", "hw", "orientation_math.py")
_spec = importlib.util.spec_from_file_location("orientation_math", _MOD)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["orientation_math"] = _mod
_spec.loader.exec_module(_mod)

# Import the motion detection functions we'll add to chassis
_MOTION_MOD = os.path.join(_REPO, "dicemaster_central", "dicemaster_central", "hw", "imu", "motion_detector.py")


def test_chassis_has_motion_publisher():
    """Chassis source should create /imu/motion publisher."""
    chassis_path = os.path.join(
        _REPO, "dicemaster_central", "dicemaster_central", "hw", "chassis.py"
    )
    with open(chassis_path) as f:
        source = f.read()
    assert "'/imu/motion'" in source or '"/imu/motion"' in source

def test_chassis_has_shake_detection():
    """Chassis source should contain shake detection logic."""
    chassis_path = os.path.join(
        _REPO, "dicemaster_central", "dicemaster_central", "hw", "chassis.py"
    )
    with open(chassis_path) as f:
        source = f.read()
    assert "detect_shaking" in source
    assert "shake_intensity" in source
    assert "stillness_factor" in source

def test_chassis_processes_accel_gyro():
    """Chassis imu_callback should process linear_acceleration and angular_velocity."""
    chassis_path = os.path.join(
        _REPO, "dicemaster_central", "dicemaster_central", "hw", "chassis.py"
    )
    with open(chassis_path) as f:
        source = f.read()
    assert "linear_acceleration" in source
    assert "angular_velocity" in source

def test_chassis_no_separate_motion_node_import():
    """Chassis should not import MotionDetectorNode — logic is inline."""
    chassis_path = os.path.join(
        _REPO, "dicemaster_central", "dicemaster_central", "hw", "chassis.py"
    )
    with open(chassis_path) as f:
        source = f.read()
    assert "MotionDetectorNode" not in source

def test_shake_detection_algorithm():
    """Validate the shake detection math works standalone."""
    from collections import deque

    history_size = 50
    accel_history = deque(maxlen=history_size)
    gyro_history = deque(maxlen=history_size)

    # Simulate still state — low variance
    rng = np.random.default_rng(42)
    for _ in range(25):
        accel_history.append(9.81 + rng.normal(0, 0.05))
        gyro_history.append(rng.normal(0, 0.1))

    recent_accel = list(accel_history)[-20:]
    accel_std = np.std(recent_accel)
    assert accel_std < 5.0, "Still state should not trigger shake"

    # Simulate shaking — high variance
    for _ in range(25):
        accel_history.append(9.81 + rng.normal(0, 8.0))
        gyro_history.append(rng.normal(0, 6.0))

    recent_accel = list(accel_history)[-20:]
    recent_gyro = list(gyro_history)[-20:]
    accel_std = np.std(recent_accel)
    gyro_mean = np.mean(np.abs(recent_gyro))
    shaking = accel_std > 5.0 or gyro_mean > 5.0
    assert shaking, "Shaking state should trigger shake detection"
```

**Step 2: Run test to verify it fails**

```bash
python3 -m pytest tests/test_chassis_motion.py -v
```

Expected: first 3 tests FAIL (chassis doesn't have motion code yet), last 2 PASS.

**Step 3: Add motion detection to chassis.py**

Add to imports at top of `chassis.py`:
```python
from collections import deque
```

Add to `__init__`, after the screen state tracking block:
```python
# Motion detection state (merged from MotionDetectorNode)
self._accel_magnitude_history = deque(maxlen=50)
self._gyro_magnitude_history = deque(maxlen=50)
self._shake_accel_threshold = 13.0   # m/s²
self._shake_gyro_threshold = 5.0     # rad/s
self._shake_variance_threshold = 5.0
```

Add the motion publisher (inside the `if self.publish_to_topics:` block, after screen_pose_publishers):
```python
# Motion detection publisher (merged from motion_detector node)
self.motion_pub = self.create_publisher(MotionDetection, '/imu/motion', 10)
```

Update `_import_ros_message_deps` to also import MotionDetection:
```python
def _import_ros_message_deps():
    global ChassisOrientation, ScreenPose, MotionDetection
    try:
        from dicemaster_central_msgs.msg import ChassisOrientation, ScreenPose, MotionDetection
        return True
    except ImportError:
        return False
```

And add `MotionDetection = None` at module level alongside the others.

Update `imu_callback` to also process accel/gyro:
```python
def imu_callback(self, msg):
    """Callback for IMU data — store orientation and motion sensor data."""
    with self.pose_lock:
        self._imu_orientation = msg.orientation
        self.last_pose_time = time.time()
        if not self.imu_connected:
            self.imu_connected = True
            self.get_logger().info('IMU data connected - using live orientation')

    # Motion detection: accumulate accel/gyro magnitudes
    accel = np.array([msg.linear_acceleration.x, msg.linear_acceleration.y, msg.linear_acceleration.z])
    gyro = np.array([msg.angular_velocity.x, msg.angular_velocity.y, msg.angular_velocity.z])
    self._accel_magnitude_history.append(np.linalg.norm(accel))
    self._gyro_magnitude_history.append(np.linalg.norm(gyro))
```

Add motion detection methods (copied from `motion_detector.py`, adapted as private methods):
```python
def _detect_shaking(self) -> bool:
    if len(self._accel_magnitude_history) < 20:
        return False
    recent_accel = list(self._accel_magnitude_history)[-20:]
    recent_gyro = list(self._gyro_magnitude_history)[-20:]
    accel_std = np.std(recent_accel)
    gyro_mean = np.mean(recent_gyro)
    return bool(accel_std > self._shake_variance_threshold or gyro_mean > self._shake_gyro_threshold)

def _get_shake_intensity(self) -> float:
    if len(self._accel_magnitude_history) < 10:
        return 0.0
    recent_accel = list(self._accel_magnitude_history)[-10:]
    recent_gyro = list(self._gyro_magnitude_history)[-10:]
    accel_intensity = min(np.std(recent_accel) / 10.0, 1.0)
    gyro_intensity = min(np.mean(recent_gyro) / 5.0, 1.0)
    return (accel_intensity + gyro_intensity) / 2.0

def _get_stillness_factor(self) -> float:
    return max(0.0, 1.0 - self._get_shake_intensity())
```

Add motion publishing to `_publish_or_log_orientation_data`, after publishing screen poses:
```python
# Publish motion detection
if self.motion_pub:
    motion_msg = MotionDetection()
    motion_msg.header.stamp = self.get_clock().now().to_msg()
    motion_msg.shaking = self._detect_shaking()
    motion_msg.shake_intensity = self._get_shake_intensity()
    motion_msg.stillness_factor = self._get_stillness_factor()
    self.motion_pub.publish(motion_msg)
```

**Step 4: Run tests**

```bash
python3 -m pytest tests/test_chassis_motion.py tests/test_chassis_tf2_removal.py tests/test_chassis_orientation.py -v
```

Expected: all pass.

**Step 5: Commit**

```bash
git add dicemaster_central/dicemaster_central/hw/chassis.py tests/test_chassis_motion.py
git commit -m "feat: integrate motion detection into chassis node

Merge shake detection from MotionDetectorNode into ChassisNode.
Same IMU callback processes orientation + accel/gyro data.
Publishes /imu/motion from chassis — eliminates separate node."
```

---

## Task 3: Update launch files and package.xml

**Files:**
- Modify: `dicemaster_central/launch/chassis.launch.py`
- Modify: `dicemaster_central/launch/imu.launch.py`
- Modify: `dicemaster_central/package.xml`

**Context:** `chassis.launch.py` currently launches `robot_state_publisher` (reads URDF, publishes static TFs) alongside the chassis node. Since TF is removed, `robot_state_publisher` is no longer needed. `imu.launch.py` launches the `motion_detector` node, which is now handled by chassis. `package.xml` has `tf2_ros`, `tf2_geometry_msgs`, and `robot_state_publisher` as dependencies.

**Step 1: Update chassis.launch.py**

Replace entire content with:
```python
#!/usr/bin/env python3
"""Launch file for DiceMaster Chassis node (TF2-free)."""
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument(
            'publish_to_topics',
            default_value='true',
            description='Enable publishing to topics'
        ),
        DeclareLaunchArgument(
            'orientation_rate',
            default_value='10.0',
            description='Orientation detection rate in Hz'
        ),
        Node(
            package='dicemaster_central',
            executable='chassis.py',
            name='dice_chassis_node',
            parameters=[{
                'publish_to_topics': LaunchConfiguration('publish_to_topics'),
                'orientation_rate': LaunchConfiguration('orientation_rate'),
            }],
        ),
    ])
```

**Step 2: Update imu.launch.py**

Remove the `motion_detector_node` Node block (lines 86-90) and its inclusion in the LaunchDescription return (line 102). The motion detection is now handled by the chassis node. Keep `imu_hardware` and `imu_filter_madgwick` nodes.

**Step 3: Update package.xml**

Remove these lines:
```xml
<depend>tf2_ros</depend>
<depend>tf2_geometry_msgs</depend>
<depend>robot_state_publisher</depend>
```

Keep `geometry_msgs` (still used for `Quaternion`).

**Step 4: Verify launch file syntax**

```bash
python3 -c "
import importlib.util, sys
for f in ['dicemaster_central/launch/chassis.launch.py', 'dicemaster_central/launch/imu.launch.py']:
    spec = importlib.util.spec_from_file_location('launch', f)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    desc = mod.generate_launch_description()
    print(f'{f}: OK ({len(desc.entities)} entities)')
"
```

**Step 5: Commit**

```bash
git add dicemaster_central/launch/chassis.launch.py dicemaster_central/launch/imu.launch.py dicemaster_central/package.xml
git commit -m "chore: update launch files and deps for TF2-free chassis

Remove robot_state_publisher from chassis launch.
Remove motion_detector from IMU launch (now in chassis).
Remove tf2_ros, tf2_geometry_msgs, robot_state_publisher deps."
```

---

## Task 4: Deploy and benchmark on Pi

**Files:**
- No code changes — deployment and verification only.

**Step 1: Push and pull**

```bash
git push
ssh dice1 'cd ~/DiceMaster/DiceMaster_Central && git pull'
```

**Step 2: Rebuild**

```bash
ssh dice1 'cd ~/DiceMaster/DiceMaster_Central && source scripts/setup_workspace.sh'
```

Expected: clean build, 4-5 packages (no `robot_state_publisher` needed).

**Step 3: Launch and benchmark idle CPU**

```bash
ssh dice1 'source ~/ros2_humble/install/setup.bash && source ~/DiceMaster/DiceMaster_Central/ros_ws/install/setup.bash && nohup ros2 run dicemaster_central chassis.py > /tmp/chassis_bench.log 2>&1 &'
sleep 5
# Get PID
ssh dice1 'pgrep -f "lib/dicemaster_central/chassis.py"'
# Measure idle CPU (no IMU)
ssh dice1 'python3 -c "
import time
def ticks(pid):
    with open(f\"/proc/{pid}/stat\") as f:
        p = f.read().split()
        return int(p[13]) + int(p[14])
pid = PID_HERE
t1 = ticks(pid); time.sleep(5); t2 = ticks(pid)
print(f\"Idle: {(t2-t1)/500*100:.1f}% CPU\")
"'
```

Expected: **<10% idle CPU** (was 15% with TF2 + MultiThreadedExecutor).

**Step 4: Benchmark with fake IMU**

Publish 50Hz fake IMU data and measure active CPU. Compare:
- Before: ~51% CPU
- Target: ~15-20% CPU

**Step 5: Verify topic output**

```bash
ssh dice1 'source ~/ros2_humble/install/setup.bash && source ~/DiceMaster/DiceMaster_Central/ros_ws/install/setup.bash && ros2 topic list | grep -E "chassis|imu/motion"'
```

Expected topics:
```
/chassis/orientation
/chassis/screen_1_pose
/chassis/screen_2_pose
/chassis/screen_3_pose
/chassis/screen_4_pose
/chassis/screen_5_pose
/chassis/screen_6_pose
/imu/motion
```

Verify orientation data:
```bash
# Publish fake IMU, then:
ros2 topic echo /chassis/orientation --once
ros2 topic echo /imu/motion --once
```

**Step 6: Kill and clean up**

```bash
ssh dice1 'pkill -f chassis.py'
```

**Step 7: Commit benchmark results to memory** (no code commit needed)

---

## Task 5: Run full test suite

**Files:**
- All test files

**Step 1: Run locally**

```bash
cd /Users/danielhou/Code/DiceMaster/DiceMaster_Central
python3 -m pytest tests/ -v
```

Expected: all tests pass (tf2_removal, motion, orientation, tf_vs_orientation_math).

**Step 2: Run on Pi**

```bash
ssh dice1 'cd ~/DiceMaster/DiceMaster_Central && python3 -m pytest tests/ -v'
```

**Step 3: Commit any test fixes if needed**

---

## Expected Results

| Metric | Before | After | Reduction |
|--------|--------|-------|-----------|
| Idle CPU (no IMU) | 15% | <5% | ~70% |
| Active CPU (10Hz orient) | 51% | ~15% | ~70% |
| ROS nodes for chassis+motion | 2 | 1 | 50% |
| DDS subscriptions to IMU | 2 | 1 | 50% |
| TF2 messages/sec | 50 | 0 | 100% |
| Dependencies (package.xml) | 8 | 5 | 37% |
