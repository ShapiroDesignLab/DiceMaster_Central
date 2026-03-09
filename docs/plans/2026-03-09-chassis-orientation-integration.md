# Chassis DiceOrientation Integration Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace all 30 TF lookups/tick in chassis.py with the validated `DiceOrientation.compute()` API, achieving ~53x speedup while preserving stickiness and debouncing behavior.

**Architecture:** `DiceOrientation` is initialized once with `dice_geometry.yaml` at node startup. Each 10Hz orientation tick extracts the IMU quaternion from `self.current_pose` as a numpy array, calls `orient.compute(imu_quat)` once, then feeds the raw results through the existing stickiness (`_apply_sticky_selection`) and edge debouncing (consecutive-frame detection) logic. TF infrastructure is kept for `world→imu_link` broadcast and debugging; `robot_state_publisher` remains running.

**Tech Stack:** Python 3.11, NumPy, SciPy, ROS2 Humble (rclpy), PyYAML

---

## Context

### Files involved
- `dicemaster_central/hw/chassis.py` — ROS2 node being modified
- `dicemaster_central/hw/orientation_math.py` — `DiceOrientation` class (already validated, 8 tests passing)
- `resource/dice_geometry.yaml` — precomputed geometry config
- `dicemaster_central/config.py` — `dice_config` with screen configs
- `dicemaster_central/constants.py` — `Rotation` enum (ROTATION_0/90/180/270)
- `tests/test_orientation_math.py` — existing validation tests (do not modify)

### DiceOrientation API reference
```python
orient = DiceOrientation('resource/dice_geometry.yaml')

result = orient.compute(imu_quat_xyzw)
# Returns:
#   'face_z':         {1: float, 2: float, ..., 6: float}  # z-position per screen
#   'up_alignments':  {1: float, ..., 6: float}             # [-1, 1] per screen
#   'top_screen':     int                                     # screen_id with highest z
#   'bottom_screen':  int                                     # screen_id with lowest z
#   'top_rotation':   int                                     # 0/1/2/3 from lowest edge
#   'top_edge_z':     {'top': float, 'left': float, 'bottom': float, 'right': float}

all_edges = orient.compute_all_edges(imu_quat_xyzw)
# Returns: {screen_id: {edge_name: z_position}}
```

### What changes and what stays

**Removed (TF lookups replaced by DiceOrientation):**
- `_get_screen_z_position()` — 6 TF lookups → `compute()['face_z']`
- `_calculate_up_alignment()` — manual `z/0.0508` → `compute()['up_alignments']`
- `_get_screen_edge_positions()` — 4 TF lookups per screen → `compute()['top_edge_z']`

**Preserved (UX/stability logic):**
- `_apply_sticky_selection()` — reduces jitter near ambiguous orientations
- Edge debouncing (`screen_edge_consecutive_count`, `screen_edge_detection_history`) — requires N consecutive frames before rotation change
- All ROS message publishing (`ChassisOrientation`, `ScreenPose`)
- TF broadcast of `world→imu_link` at 50Hz
- IMU callback and pose tracking

**Behavior change (intentional improvement):**
- Edge rotation now computed for top screen only (was wastefully computed for all 6)
- Non-top screens retain last-known rotation from when they were on top

---

## Task 1: Integration test — orientation pipeline without ROS

Write a test that validates the full orientation pipeline (DiceOrientation → stickiness → debouncing → output) without requiring rclpy. This simulates what `orientation_callback` does.

**Files:**
- Create: `tests/test_chassis_orientation.py`

**Step 1: Write the test file**

```python
"""Tests for the chassis orientation pipeline logic (no ROS dependency).

Validates that DiceOrientation output, fed through the stickiness and
debouncing logic from chassis.py, produces correct results.
"""

import importlib.util
import os

import numpy as np
import pytest
from scipy.spatial.transform import Rotation

# ---------------------------------------------------------------------------
# Import orientation_math without rclpy
# ---------------------------------------------------------------------------
_MODULE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'dicemaster_central', 'hw',
)
_spec = importlib.util.spec_from_file_location(
    'orientation_math', os.path.join(_MODULE_DIR, 'orientation_math.py')
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
DiceOrientation = _mod.DiceOrientation
NUM_SCREENS = _mod.NUM_SCREENS

_RESOURCE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'resource'
)
_CONFIG_PATH = os.path.join(_RESOURCE_DIR, 'dice_geometry.yaml')


# ---------------------------------------------------------------------------
# Stickiness helper (extracted from chassis.py, pure function)
# ---------------------------------------------------------------------------

def apply_sticky_selection(values_dict, margin=0.01, mode='max'):
    """Identical to ChassisNode._apply_sticky_selection — pure function."""
    if len(values_dict) < 2:
        return values_dict

    values_array = np.array(list(values_dict.values()))
    ids_array = np.array(list(values_dict.keys()))

    target_value = np.max(values_array) if mode == 'max' else np.min(values_array)
    modified_values = values_dict.copy()

    target_mask = np.abs(values_array - target_value) < 1e-6
    target_indices = np.where(target_mask)[0]

    if len(target_indices) > 0:
        non_target_indices = np.where(~target_mask)[0]
        if len(non_target_indices) > 0:
            if mode == 'max':
                second_best = np.max(values_array[non_target_indices])
                separation = target_value - second_best
            else:
                second_best = np.min(values_array[non_target_indices])
                separation = second_best - target_value

            if separation < margin:
                for idx in target_indices:
                    screen_id = ids_array[idx]
                    modified_values[screen_id] = values_dict[screen_id] * 0.5

    return modified_values


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestStickySelection:
    """Verify stickiness helper reduces confidence for ambiguous values."""

    def test_clear_max_unchanged(self):
        values = {1: 0.05, 2: -0.03, 3: -0.02}
        result = apply_sticky_selection(values, margin=0.01, mode='max')
        assert result[1] == 0.05  # Clear winner untouched

    def test_close_max_halved(self):
        values = {1: 0.050, 2: 0.049, 3: -0.05}
        result = apply_sticky_selection(values, margin=0.01, mode='max')
        assert result[1] == 0.025  # Halved because within margin

    def test_clear_min_unchanged(self):
        values = {1: 0.05, 2: -0.05, 3: 0.02}
        result = apply_sticky_selection(values, margin=0.01, mode='min')
        assert result[2] == -0.05  # Clear winner untouched

    def test_single_element(self):
        values = {1: 0.05}
        result = apply_sticky_selection(values, margin=0.01, mode='max')
        assert result == values


class TestOrientationPipeline:
    """End-to-end: DiceOrientation → stickiness → top/bottom selection."""

    @pytest.fixture(scope='class')
    def orient(self):
        return DiceOrientation(_CONFIG_PATH)

    def _run_pipeline(self, orient, imu_quat):
        """Simulate what orientation_callback does (sans ROS)."""
        result = orient.compute(imu_quat)

        # Apply stickiness on face_z (same as chassis.py)
        sticky_z = apply_sticky_selection(result['face_z'], margin=0.01, mode='max')
        sticky_z = apply_sticky_selection(sticky_z, margin=0.01, mode='min')

        # Build orientations list (same format as chassis.py)
        orientations = []
        for sid in sorted(sticky_z.keys()):
            up_alignment = np.clip(sticky_z[sid] / 0.0508, -1.0, 1.0)
            orientations.append({
                'screen_id': sid,
                'up_alignment': float(up_alignment),
                'z_position': float(result['face_z'][sid]),
            })

        top = max(orientations, key=lambda x: x['up_alignment'])
        bottom = min(orientations, key=lambda x: x['up_alignment'])
        return top, bottom, orientations, result

    def test_identity_quaternion_top_screen(self, orient):
        """Identity IMU quat should produce a definite top and bottom screen."""
        q = np.array([0.0, 0.0, 0.0, 1.0])
        top, bottom, orientations, result = self._run_pipeline(orient, q)
        # Must identify valid screens
        assert 1 <= top['screen_id'] <= 6
        assert 1 <= bottom['screen_id'] <= 6
        assert top['screen_id'] != bottom['screen_id']

    def test_top_bottom_consistent_with_compute(self, orient):
        """Pipeline top/bottom should match DiceOrientation.compute() in clear cases."""
        # Use a quaternion that gives a clear top screen (not near an edge)
        # 45-degree tilt around X axis
        q = Rotation.from_euler('x', 0.3).as_quat()
        top, bottom, _, result = self._run_pipeline(orient, q)
        assert top['screen_id'] == result['top_screen']
        assert bottom['screen_id'] == result['bottom_screen']

    def test_all_six_screens_present(self, orient):
        q = np.array([0.0, 0.0, 0.0, 1.0])
        _, _, orientations, _ = self._run_pipeline(orient, q)
        screen_ids = {o['screen_id'] for o in orientations}
        assert screen_ids == {1, 2, 3, 4, 5, 6}

    def test_up_alignments_bounded(self, orient):
        """All up_alignment values should be in [-1, 1]."""
        rng = np.random.default_rng(99)
        for _ in range(50):
            q = Rotation.random(random_state=rng).as_quat()
            _, _, orientations, _ = self._run_pipeline(orient, q)
            for o in orientations:
                assert -1.0 <= o['up_alignment'] <= 1.0


class TestEdgeDebouncing:
    """Verify edge debouncing logic (consecutive-frame requirement)."""

    def test_rotation_requires_consecutive_frames(self):
        """Rotation should not change until edge is detected N consecutive times."""
        edge_detection_frames = 2
        consecutive_count = 0
        current_rotation = 0
        last_edge = None

        edge_to_rotation = {'bottom': 0, 'right': 1, 'top': 2, 'left': 3}

        # Simulate: detect 'right' once, then 'left' once — should not change
        for detected_edge in ['right', 'left']:
            if detected_edge == last_edge:
                consecutive_count += 1
            else:
                consecutive_count = 1
            last_edge = detected_edge

            if consecutive_count >= edge_detection_frames:
                current_rotation = edge_to_rotation[detected_edge]

        assert current_rotation == 0  # No change (no consecutive)

    def test_rotation_changes_after_consecutive(self):
        """Rotation should change after N consecutive same-edge detections."""
        edge_detection_frames = 2
        consecutive_count = 0
        current_rotation = 0
        last_edge = None

        edge_to_rotation = {'bottom': 0, 'right': 1, 'top': 2, 'left': 3}

        # Simulate: detect 'right' twice consecutively
        for detected_edge in ['right', 'right']:
            if detected_edge == last_edge:
                consecutive_count += 1
            else:
                consecutive_count = 1
            last_edge = detected_edge

            if consecutive_count >= edge_detection_frames:
                current_rotation = edge_to_rotation[detected_edge]

        assert current_rotation == 1  # Changed to 'right' rotation

    def test_interrupted_sequence_resets(self):
        """A different edge interrupting the sequence resets the counter."""
        edge_detection_frames = 3
        consecutive_count = 0
        current_rotation = 0
        last_edge = None

        edge_to_rotation = {'bottom': 0, 'right': 1, 'top': 2, 'left': 3}

        # Simulate: right, right, left, right, right — should not change
        for detected_edge in ['right', 'right', 'left', 'right', 'right']:
            if detected_edge == last_edge:
                consecutive_count += 1
            else:
                consecutive_count = 1
            last_edge = detected_edge

            if consecutive_count >= edge_detection_frames:
                current_rotation = edge_to_rotation[detected_edge]

        assert current_rotation == 0  # Never hit 3 consecutive
```

**Step 2: Run tests to verify they pass**

Run: `cd /Users/danielhou/Code/DiceMaster/DiceMaster_Central/dicemaster_central && python3 -m pytest tests/test_chassis_orientation.py -v`
Expected: All 9 tests PASS (these test the pipeline logic, not the chassis.py integration yet)

**Step 3: Commit**

```bash
cd /Users/danielhou/Code/DiceMaster/DiceMaster_Central/dicemaster_central
git add tests/test_chassis_orientation.py
git commit -m "test: add chassis orientation pipeline tests (no ROS dependency)"
```

---

## Task 2: Add DiceOrientation initialization to ChassisNode

Add `DiceOrientation` import, construction in `__init__`, and a helper method to extract the IMU quaternion as a numpy array.

**Files:**
- Modify: `dicemaster_central/hw/chassis.py:1-15` (imports)
- Modify: `dicemaster_central/hw/chassis.py:76-192` (`__init__`)

**Step 1: Add imports at top of chassis.py**

After the existing `import numpy as np` line (line 14), add:

```python
from dicemaster_central.hw.orientation_math import DiceOrientation
```

Also add at the top of the file, alongside existing `os` usage patterns:

```python
from ament_index_python.packages import get_package_share_directory
```

**Step 2: Add DiceOrientation initialization in `__init__`**

After the TF2 setup block (after line 134), add:

```python
        # Vectorized orientation math (replaces per-tick TF lookups)
        _pkg_share = get_package_share_directory('dicemaster_central')
        _config_path = os.path.join(_pkg_share, 'dice_geometry.yaml')
        self._dice_orientation = DiceOrientation(_config_path)
```

**Step 3: Add IMU quaternion extraction helper**

Add this method to ChassisNode (after `imu_callback`, around line 216):

```python
    def _get_imu_quaternion(self) -> np.ndarray:
        """Extract the current IMU quaternion as [x, y, z, w] numpy array."""
        with self.pose_lock:
            o = self.current_pose.orientation
            return np.array([o.x, o.y, o.z, o.w])
```

**Step 4: Verify file is syntactically valid**

Run: `cd /Users/danielhou/Code/DiceMaster/DiceMaster_Central/dicemaster_central && python3 -c "import ast; ast.parse(open('dicemaster_central/hw/chassis.py').read()); print('OK')"`
Expected: `OK`

Note: Full import will fail on macOS (no rclpy), but syntax check confirms no typos.

**Step 5: Commit**

```bash
git add dicemaster_central/hw/chassis.py
git commit -m "feat: add DiceOrientation init and IMU quaternion helper to chassis node"
```

---

## Task 3: Replace `_get_all_screen_orientations()` with DiceOrientation.compute()

Replace 6 TF lookups with a single `compute()` call. Keep stickiness logic intact.

**Files:**
- Modify: `dicemaster_central/hw/chassis.py` — rewrite `_get_all_screen_orientations()`

**Step 1: Rewrite `_get_all_screen_orientations`**

Replace the entire method (lines 368-398) with:

```python
    def _get_all_screen_orientations(self):
        """Get orientations for all screens using vectorized orientation math."""
        imu_quat = self._get_imu_quaternion()
        self._last_orientation_result = self._dice_orientation.compute(imu_quat)
        result = self._last_orientation_result

        face_z = result['face_z']

        # Apply stickiness to face_z values (reduces jitter near ambiguous orientations)
        sticky_z = self._apply_sticky_selection(face_z, margin=0.01, mode='max')
        sticky_z = self._apply_sticky_selection(sticky_z, margin=0.01, mode='min')

        # Build orientation data (same format as before)
        orientations = []
        for sid in sorted(sticky_z.keys()):
            up_alignment = np.clip(sticky_z[sid] / 0.0508, -1.0, 1.0)
            orientations.append({
                'screen_id': sid,
                'up_alignment': float(up_alignment),
                'z_position': float(face_z[sid]),
                'frame_name': f'screen_{sid}_link',
            })

        return orientations
```

Note: We store `self._last_orientation_result` so that `_calculate_screen_rotation_from_edges` can use the precomputed `top_edge_z` without recomputing.

**Step 2: Verify syntax**

Run: `cd /Users/danielhou/Code/DiceMaster/DiceMaster_Central/dicemaster_central && python3 -c "import ast; ast.parse(open('dicemaster_central/hw/chassis.py').read()); print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add dicemaster_central/hw/chassis.py
git commit -m "feat: replace face z TF lookups with DiceOrientation.compute()"
```

---

## Task 4: Replace edge rotation to use compute() data, top screen only

Rewrite `_calculate_screen_rotation_from_edges` to use `compute()['top_edge_z']` instead of TF lookups. Only compute edges for the top screen. Preserve debouncing logic.

**Files:**
- Modify: `dicemaster_central/hw/chassis.py` — rewrite `_calculate_screen_rotation_from_edges()`
- Modify: `dicemaster_central/hw/chassis.py` — update `orientation_callback()` to only compute rotation for top screen

**Step 1: Rewrite `_calculate_screen_rotation_from_edges`**

Replace the entire method (lines 422-492) with:

```python
    def _calculate_screen_rotation_from_edges(self, screen_id):
        """Calculate screen rotation based on which edge is lowest (closest to gravity).

        Uses precomputed edge z values from DiceOrientation.compute().
        Only meaningful for the current top screen.
        Requires N consecutive same-edge detections before changing rotation.
        """
        result = self._last_orientation_result
        if result is None:
            return self.screen_edge_rotations.get(screen_id, ConfigRotation.ROTATION_0)

        # Use top_edge_z from compute() — already has the 4 edge z-values
        edge_positions = result['top_edge_z']

        # Apply stickiness to edge selection
        sticky_edges = self._apply_sticky_selection(edge_positions, margin=0.005, mode='min')

        # Find the lowest edge (most aligned with gravity)
        current_lowest_edge = min(sticky_edges.keys(), key=sticky_edges.get)

        # Debouncing: require consecutive detections before changing rotation
        detection_history = self.screen_edge_detection_history[screen_id]

        if len(detection_history) > 0 and detection_history[-1] == current_lowest_edge:
            self.screen_edge_consecutive_count[screen_id] += 1
        else:
            self.screen_edge_consecutive_count[screen_id] = 1

        detection_history.append(current_lowest_edge)
        if len(detection_history) > self.edge_detection_frames:
            detection_history.pop(0)

        consecutive_count = self.screen_edge_consecutive_count[screen_id]
        if consecutive_count >= self.edge_detection_frames:
            edge_to_rotation = {
                'bottom': ConfigRotation.ROTATION_0,
                'right': ConfigRotation.ROTATION_90,
                'top': ConfigRotation.ROTATION_180,
                'left': ConfigRotation.ROTATION_270,
            }
            new_rotation = edge_to_rotation.get(current_lowest_edge, ConfigRotation.ROTATION_0)
            current_rotation = self.screen_edge_rotations.get(screen_id, ConfigRotation.ROTATION_0)
            if new_rotation != current_rotation:
                self.screen_edge_rotations[screen_id] = new_rotation
                return new_rotation
            return current_rotation
        else:
            return self.screen_edge_rotations.get(screen_id, ConfigRotation.ROTATION_0)
```

**Step 2: Update `orientation_callback` to only compute rotation for top screen**

Replace the loop in `orientation_callback` (lines 274-286) with:

```python
        # Find top and bottom screens
        top_screen = max(screen_orientations, key=lambda x: x['up_alignment'])
        bottom_screen = min(screen_orientations, key=lambda x: x['up_alignment'])

        # Compute edge rotation for top screen only (edges only meaningful for top face)
        top_screen_id = top_screen['screen_id']
        new_rotation = self._calculate_screen_rotation_from_edges(top_screen_id)

        # Apply stickiness per screen — update rotation state for all screens
        for orientation in screen_orientations:
            screen_id = orientation['screen_id']
            old_alignment = self.screen_up_alignments.get(screen_id, -1.0)
            alignment_change = abs(orientation['up_alignment'] - old_alignment)

            if alignment_change > self.rotation_threshold:
                if screen_id == top_screen_id:
                    self.screen_rotations[screen_id] = new_rotation
                self.screen_up_alignments[screen_id] = orientation['up_alignment']
```

**Step 3: Verify syntax**

Run: `cd /Users/danielhou/Code/DiceMaster/DiceMaster_Central/dicemaster_central && python3 -c "import ast; ast.parse(open('dicemaster_central/hw/chassis.py').read()); print('OK')"`
Expected: `OK`

**Step 4: Commit**

```bash
git add dicemaster_central/hw/chassis.py
git commit -m "feat: replace edge TF lookups with compute() data, top screen only"
```

---

## Task 5: Remove dead code and clean up

Remove methods that are no longer called, and remove debug `print()` statements.

**Files:**
- Modify: `dicemaster_central/hw/chassis.py`

**Step 1: Delete `_get_screen_z_position` method**

Remove the entire `_get_screen_z_position` method (lines 292-313). It is no longer called.

**Step 2: Delete `_calculate_up_alignment` method**

Remove the entire `_calculate_up_alignment` method (lines 315-319). Up alignment is now computed inline from `face_z / 0.0508` or directly from `DiceOrientation`.

**Step 3: Delete `_get_screen_edge_positions` method**

Remove the entire `_get_screen_edge_positions` method (lines 400-420). Edge positions now come from `compute()['top_edge_z']`.

**Step 4: Remove the debug `print()` on line 267**

Replace:
```python
            print("No screen orientations detected, skipping publishing")
```
With:
```python
            self.get_logger().debug("No screen orientations detected, skipping publishing")
```

**Step 5: Initialize `_last_orientation_result` in `__init__`**

Add after the `DiceOrientation` construction:
```python
        self._last_orientation_result = None
```

**Step 6: Remove unused `perf_counter` import and usage**

Remove `from time import perf_counter` from imports (line 17), and remove the `st = perf_counter()` lines in `orientation_callback` (line 255) and `_get_all_screen_orientations` (line 370) since they're assigned but never read.

**Step 7: Verify syntax**

Run: `cd /Users/danielhou/Code/DiceMaster/DiceMaster_Central/dicemaster_central && python3 -c "import ast; ast.parse(open('dicemaster_central/hw/chassis.py').read()); print('OK')"`
Expected: `OK`

**Step 8: Run existing orientation_math tests to ensure no regressions**

Run: `cd /Users/danielhou/Code/DiceMaster/DiceMaster_Central/dicemaster_central && python3 -m pytest tests/test_orientation_math.py tests/test_chassis_orientation.py -v`
Expected: All tests pass (8 orientation_math + 9 chassis_orientation = 17 total)

**Step 9: Commit**

```bash
git add dicemaster_central/hw/chassis.py
git commit -m "refactor: remove dead TF lookup methods and debug prints from chassis"
```

---

## Summary of changes

| Method | Before | After |
|--------|--------|-------|
| `_get_screen_z_position()` | 1 TF lookup × 6 screens | **Deleted** — `compute()['face_z']` |
| `_calculate_up_alignment()` | Manual `z/0.0508` | **Deleted** — inline `np.clip(z/0.0508, -1, 1)` |
| `_get_all_screen_orientations()` | 6 TF lookups | 1 `DiceOrientation.compute()` call |
| `_get_screen_edge_positions()` | 4 TF lookups per screen | **Deleted** — `compute()['top_edge_z']` |
| `_calculate_screen_rotation_from_edges()` | Calls `_get_screen_edge_positions()` | Reads `self._last_orientation_result['top_edge_z']` |
| `orientation_callback()` loop | Computes edges for all 6 screens | Computes edges for top screen only |
| **Total TF lookups per tick** | **30** | **0** |
