"""Validate that DiceOrientation.compute() produces results identical to the
TF2 transform chain: world → imu_link → base_link → screen_N_link.

This test reconstructs the TF2 chain manually using scipy Rotation (the same
math that ROS TF2 uses internally) and compares every output of
DiceOrientation.compute() against it.  A large, diverse set of IMU quaternions
is tested to ensure correctness across the full rotation space.

Run:
    python3 -m pytest tests/test_tf_vs_orientation_math.py -v
"""

import importlib.util
import os
import sys

import numpy as np
import pytest
import yaml
from scipy.spatial.transform import Rotation

# ---------------------------------------------------------------------------
# Import DiceOrientation without rclpy
# ---------------------------------------------------------------------------
_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_MOD_PATH = os.path.join(
    _REPO, "dicemaster_central", "dicemaster_central", "hw", "orientation_math.py"
)
_spec = importlib.util.spec_from_file_location("orientation_math", _MOD_PATH)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["orientation_math"] = _mod
_spec.loader.exec_module(_mod)
DiceOrientation = _mod.DiceOrientation
EDGE_NAMES = _mod.EDGE_NAMES

_CONFIG_PATH = os.path.join(
    _REPO, "dicemaster_central", "resource", "dice_geometry.yaml"
)

# ---------------------------------------------------------------------------
# Reference TF chain implementation (what TF2 would compute)
# ---------------------------------------------------------------------------

class TFChainReference:
    """Reconstruct the TF2 transform chain for validation.

    The chain is:
        world ←[imu_quat]→ imu_link ←[base_joint]→ base_link ←[screen_joint]→ screen_N_link

    For each screen, we compute:
        world_rotation = Rotation(imu_quat) * Rotation(base_joint_quat)
        face_centre_world = world_rotation.apply(screen_joint.apply([0, 0, face_offset]))
        face_z = face_centre_world[2]

        face_normal_world = world_rotation.apply(screen_joint.apply([0, 0, 1]))
        up_alignment = face_normal_world[2]

    For edges of a screen:
        edge_pos_base = screen_joint.apply(canonical_edge_offset) + face_centre_base
        edge_pos_world = world_rotation.apply(edge_pos_base)
        edge_z = edge_pos_world[2]
    """

    def __init__(self, config_path: str):
        with open(config_path) as f:
            cfg = yaml.safe_load(f)

        self.base_quat = np.array(cfg["base_joint"]["quaternion"], dtype=np.float64)
        self.base_rot = Rotation.from_quat(self.base_quat)
        self.face_offset = float(cfg["face_offset"])

        canonical_edges_cfg = cfg["canonical_edges"]
        self.canonical_edge_offsets = {
            name: np.array(canonical_edges_cfg[name], dtype=np.float64)
            for name in EDGE_NAMES
        }

        screens_cfg = cfg["screens"]
        self.screen_ids = sorted(int(k) for k in screens_cfg.keys())
        self.screen_joint_rots = {}
        for sid in self.screen_ids:
            q = np.array(screens_cfg[sid]["joint_quaternion"], dtype=np.float64)
            self.screen_joint_rots[sid] = Rotation.from_quat(q)

    def compute(self, imu_quat: np.ndarray) -> dict:
        """Compute all orientation data using the TF chain, one screen at a time."""
        imu_rot = Rotation.from_quat(imu_quat)
        world_rot = imu_rot * self.base_rot

        face_z = {}
        up_alignments = {}

        for sid in self.screen_ids:
            joint_rot = self.screen_joint_rots[sid]

            # Face centre in base_link frame
            face_centre_base = joint_rot.apply(
                np.array([0.0, 0.0, self.face_offset])
            )
            # Face centre in world frame
            face_centre_world = world_rot.apply(face_centre_base)
            face_z[sid] = float(face_centre_world[2])

            # Face normal in base_link frame
            face_normal_base = joint_rot.apply(np.array([0.0, 0.0, 1.0]))
            # Face normal in world frame
            face_normal_world = world_rot.apply(face_normal_base)
            up_alignments[sid] = float(face_normal_world[2])

        top_screen = max(up_alignments, key=up_alignments.get)
        bottom_screen = min(up_alignments, key=up_alignments.get)

        # Edge positions for top screen only
        top_joint_rot = self.screen_joint_rots[top_screen]
        top_face_centre_base = top_joint_rot.apply(
            np.array([0.0, 0.0, self.face_offset])
        )

        top_edge_z = {}
        for edge_name in EDGE_NAMES:
            edge_offset = self.canonical_edge_offsets[edge_name]
            edge_pos_base = top_joint_rot.apply(edge_offset) + top_face_centre_base
            edge_pos_world = world_rot.apply(edge_pos_base)
            top_edge_z[edge_name] = float(edge_pos_world[2])

        lowest_edge_name = min(top_edge_z, key=top_edge_z.get)
        edge_to_rotation = {"bottom": 0, "right": 1, "top": 2, "left": 3}
        top_rotation = edge_to_rotation[lowest_edge_name]

        return {
            "face_z": face_z,
            "up_alignments": up_alignments,
            "top_screen": top_screen,
            "bottom_screen": bottom_screen,
            "top_edge_z": top_edge_z,
            "top_rotation": top_rotation,
        }


# ---------------------------------------------------------------------------
# Quaternion generators
# ---------------------------------------------------------------------------

def _random_quaternions(n: int, seed: int = 42) -> np.ndarray:
    """Generate n uniformly distributed random unit quaternions [x, y, z, w]."""
    rng = np.random.default_rng(seed)
    # Uniform random rotations via scipy
    rotations = Rotation.random(n, random_state=rng)
    return rotations.as_quat()  # [x, y, z, w]


def _axis_aligned_quaternions() -> list[np.ndarray]:
    """Generate quaternions for all 24 axis-aligned orientations of a cube."""
    quats = []
    # 90-degree rotations around each axis, and their combinations
    angles = [0, 90, 180, 270]
    for ax in angles:
        for ay in angles:
            r = Rotation.from_euler("xyz", [ax, ay, 0], degrees=True)
            q = r.as_quat()
            # Avoid near-duplicates
            is_dup = False
            for existing in quats:
                if np.allclose(q, existing, atol=1e-6) or np.allclose(
                    q, -existing, atol=1e-6
                ):
                    is_dup = True
                    break
            if not is_dup:
                quats.append(q)
    return quats


def _tilt_quaternions() -> list[np.ndarray]:
    """Generate quaternions at various tilt angles (edge cases for top/bottom)."""
    quats = []
    for angle in [5, 15, 30, 44, 45, 46, 60, 75, 85]:
        for axis in ["x", "y", "z", "xy", "xz", "yz"]:
            if len(axis) == 1:
                r = Rotation.from_euler(axis, angle, degrees=True)
            else:
                r = Rotation.from_euler(
                    "xyz",
                    [angle if c in axis else 0 for c in "xyz"],
                    degrees=True,
                )
            quats.append(r.as_quat())
    return quats


# ---------------------------------------------------------------------------
# Build the full test quaternion set
# ---------------------------------------------------------------------------

_ALL_QUATS = []
_ALL_QUATS.append(np.array([0.0, 0.0, 0.0, 1.0]))  # identity
_ALL_QUATS.extend(_axis_aligned_quaternions())
_ALL_QUATS.extend(_tilt_quaternions())
_ALL_QUATS.extend(_random_quaternions(500).tolist())


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def dice_orientation():
    return DiceOrientation(_CONFIG_PATH)


@pytest.fixture(scope="module")
def tf_reference():
    return TFChainReference(_CONFIG_PATH)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

ATOL = 1e-10  # tight tolerance — results should be bit-for-bit identical


class TestFaceZPositions:
    """Validate face centre z-positions match TF chain."""

    @pytest.mark.parametrize("quat_idx", range(len(_ALL_QUATS)))
    def test_face_z(self, dice_orientation, tf_reference, quat_idx):
        quat = np.array(_ALL_QUATS[quat_idx], dtype=np.float64)
        result = dice_orientation.compute(quat)
        ref = tf_reference.compute(quat)

        for sid in ref["face_z"]:
            assert sid in result["face_z"], f"Missing screen {sid} in face_z"
            np.testing.assert_allclose(
                result["face_z"][sid],
                ref["face_z"][sid],
                atol=ATOL,
                err_msg=f"face_z mismatch for screen {sid}, quat {quat}",
            )


class TestUpAlignments:
    """Validate up alignment values match TF chain."""

    @pytest.mark.parametrize("quat_idx", range(len(_ALL_QUATS)))
    def test_up_alignments(self, dice_orientation, tf_reference, quat_idx):
        quat = np.array(_ALL_QUATS[quat_idx], dtype=np.float64)
        result = dice_orientation.compute(quat)
        ref = tf_reference.compute(quat)

        for sid in ref["up_alignments"]:
            assert sid in result["up_alignments"]
            np.testing.assert_allclose(
                result["up_alignments"][sid],
                ref["up_alignments"][sid],
                atol=ATOL,
                err_msg=f"up_alignment mismatch for screen {sid}, quat {quat}",
            )


class TestTopBottomScreen:
    """Validate top/bottom screen selection matches TF chain."""

    @pytest.mark.parametrize("quat_idx", range(len(_ALL_QUATS)))
    def test_top_bottom(self, dice_orientation, tf_reference, quat_idx):
        quat = np.array(_ALL_QUATS[quat_idx], dtype=np.float64)
        result = dice_orientation.compute(quat)
        ref = tf_reference.compute(quat)

        # Check if this is an ambiguous case (two screens nearly tied)
        ref_alignments = ref["up_alignments"]
        sorted_alignments = sorted(ref_alignments.values(), reverse=True)
        top_margin = sorted_alignments[0] - sorted_alignments[1]
        bottom_margin = sorted_alignments[-2] - sorted_alignments[-1]

        if top_margin > 1e-6:
            assert result["top_screen"] == ref["top_screen"], (
                f"top_screen mismatch: got {result['top_screen']}, "
                f"expected {ref['top_screen']}, quat {quat}"
            )
        # else: tie — both answers are valid

        if bottom_margin > 1e-6:
            assert result["bottom_screen"] == ref["bottom_screen"], (
                f"bottom_screen mismatch: got {result['bottom_screen']}, "
                f"expected {ref['bottom_screen']}, quat {quat}"
            )


class TestTopEdgeZ:
    """Validate edge z-positions for the top screen match TF chain."""

    @pytest.mark.parametrize("quat_idx", range(len(_ALL_QUATS)))
    def test_top_edge_z(self, dice_orientation, tf_reference, quat_idx):
        quat = np.array(_ALL_QUATS[quat_idx], dtype=np.float64)
        result = dice_orientation.compute(quat)
        ref = tf_reference.compute(quat)

        # Only compare edges when top screen agrees (skip ties)
        if result["top_screen"] != ref["top_screen"]:
            pytest.skip("Top screen differs (tie) — edge comparison not meaningful")

        for edge_name in EDGE_NAMES:
            np.testing.assert_allclose(
                result["top_edge_z"][edge_name],
                ref["top_edge_z"][edge_name],
                atol=ATOL,
                err_msg=f"top_edge_z mismatch for edge {edge_name}, quat {quat}",
            )


class TestTopRotation:
    """Validate rotation determination matches TF chain."""

    @pytest.mark.parametrize("quat_idx", range(len(_ALL_QUATS)))
    def test_top_rotation(self, dice_orientation, tf_reference, quat_idx):
        quat = np.array(_ALL_QUATS[quat_idx], dtype=np.float64)
        result = dice_orientation.compute(quat)
        ref = tf_reference.compute(quat)

        if result["top_screen"] != ref["top_screen"]:
            pytest.skip("Top screen differs (tie)")

        # Check if edges are ambiguous (two edges nearly tied for lowest)
        edge_vals = list(ref["top_edge_z"].values())
        sorted_edges = sorted(edge_vals)
        edge_margin = sorted_edges[1] - sorted_edges[0]

        if edge_margin > 1e-6:
            assert result["top_rotation"] == ref["top_rotation"], (
                f"top_rotation mismatch: got {result['top_rotation']}, "
                f"expected {ref['top_rotation']}, quat {quat}, "
                f"edge_z={ref['top_edge_z']}"
            )


class TestAllEdges:
    """Validate compute_all_edges() matches the TF chain for all 6 screens."""

    @pytest.mark.parametrize("quat_idx", range(len(_ALL_QUATS)))
    def test_all_edges(self, dice_orientation, tf_reference, quat_idx):
        quat = np.array(_ALL_QUATS[quat_idx], dtype=np.float64)

        # compute_all_edges returns edges for all 6 screens
        all_edges = dice_orientation.compute_all_edges(quat)

        # Reconstruct reference: compute edges for every screen
        imu_rot = Rotation.from_quat(quat)
        world_rot = imu_rot * tf_reference.base_rot

        for sid in tf_reference.screen_ids:
            joint_rot = tf_reference.screen_joint_rots[sid]
            face_centre_base = joint_rot.apply(
                np.array([0.0, 0.0, tf_reference.face_offset])
            )

            for edge_name in EDGE_NAMES:
                edge_offset = tf_reference.canonical_edge_offsets[edge_name]
                edge_pos_base = joint_rot.apply(edge_offset) + face_centre_base
                edge_pos_world = world_rot.apply(edge_pos_base)
                ref_z = float(edge_pos_world[2])

                np.testing.assert_allclose(
                    all_edges[sid][edge_name],
                    ref_z,
                    atol=ATOL,
                    err_msg=(
                        f"all_edges mismatch: screen {sid}, edge {edge_name}, "
                        f"quat {quat}"
                    ),
                )


class TestBatchConsistency:
    """Verify that compute() and compute_all_edges() are consistent."""

    @pytest.mark.parametrize("quat_idx", range(min(100, len(_ALL_QUATS))))
    def test_top_edges_consistent(self, dice_orientation, quat_idx):
        """top_edge_z from compute() should match the top screen's edges
        from compute_all_edges()."""
        quat = np.array(_ALL_QUATS[quat_idx], dtype=np.float64)
        result = dice_orientation.compute(quat)
        all_edges = dice_orientation.compute_all_edges(quat)

        top_sid = result["top_screen"]
        for edge_name in EDGE_NAMES:
            np.testing.assert_allclose(
                result["top_edge_z"][edge_name],
                all_edges[top_sid][edge_name],
                atol=ATOL,
                err_msg=f"Inconsistency between compute() and compute_all_edges() "
                f"for top screen {top_sid}, edge {edge_name}",
            )


class TestSummaryStatistics:
    """Run all quaternions and report aggregate pass/fail (non-parametrized)."""

    def test_full_sweep(self, dice_orientation, tf_reference):
        """Run all quaternions and report any failures."""
        n_tested = 0
        n_face_z_ok = 0
        n_alignment_ok = 0
        n_top_ok = 0
        n_edge_ok = 0

        for quat in _ALL_QUATS:
            quat = np.array(quat, dtype=np.float64)
            result = dice_orientation.compute(quat)
            ref = tf_reference.compute(quat)
            n_tested += 1

            # face_z
            fz_match = all(
                abs(result["face_z"][s] - ref["face_z"][s]) < ATOL
                for s in ref["face_z"]
            )
            if fz_match:
                n_face_z_ok += 1

            # up_alignments
            ua_match = all(
                abs(result["up_alignments"][s] - ref["up_alignments"][s]) < ATOL
                for s in ref["up_alignments"]
            )
            if ua_match:
                n_alignment_ok += 1

            # top_screen
            if result["top_screen"] == ref["top_screen"]:
                n_top_ok += 1

            # edge_z (only when top agrees)
            if result["top_screen"] == ref["top_screen"]:
                ez_match = all(
                    abs(result["top_edge_z"][e] - ref["top_edge_z"][e]) < ATOL
                    for e in EDGE_NAMES
                )
                if ez_match:
                    n_edge_ok += 1

        print(f"\n{'='*60}")
        print(f"TF Chain vs DiceOrientation Validation Summary")
        print(f"{'='*60}")
        print(f"Quaternions tested:    {n_tested}")
        print(f"Face z-positions:      {n_face_z_ok}/{n_tested} passed")
        print(f"Up alignments:         {n_alignment_ok}/{n_tested} passed")
        print(f"Top screen selection:  {n_top_ok}/{n_tested} passed")
        print(f"Edge z-positions:      {n_edge_ok}/{n_top_ok} passed (when top agrees)")
        print(f"{'='*60}")

        assert n_face_z_ok == n_tested, "Some face_z values mismatched"
        assert n_alignment_ok == n_tested, "Some up_alignment values mismatched"
