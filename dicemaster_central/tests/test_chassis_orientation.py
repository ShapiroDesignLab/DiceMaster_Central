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
