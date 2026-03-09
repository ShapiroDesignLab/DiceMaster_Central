"""Validation tests for DiceOrientation against ground-truth URDF transforms.

Walks the full URDF joint chain (equivalent to robot_state_publisher + TF
lookups) and compares every computed value from DiceOrientation against
the ground truth for 200 random quaternions uniformly sampled on SO(3).
"""

import importlib.util
import os
import sys
import xml.etree.ElementTree as ET

import numpy as np
import pytest
from scipy.spatial.transform import Rotation

# Import orientation_math directly by file path to avoid pulling in
# rclpy-dependent modules through the dicemaster_central package __init__.
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
EDGE_NAMES = _mod.EDGE_NAMES
NUM_SCREENS = _mod.NUM_SCREENS

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_RESOURCE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'resource'
)
_URDF_PATH = os.path.join(_RESOURCE_DIR, 'dice.urdf')
_CONFIG_PATH = os.path.join(_RESOURCE_DIR, 'dice_geometry.yaml')

NUM_RANDOM_QUATS = 200
RNG_SEED = 42

# The URDF uses truncated rpy values (e.g. 1.5708 for pi/2, 3.14159 for pi).
# The YAML quaternions are derived from the same rpy values but via a different
# code path (direct conversion vs chained euler compositions).  This produces
# numerical differences of ~1e-8 in positions and ~1e-6 in alignment sums.
_Z_TOLERANCE = 1e-6       # position comparison (face z, edge z)
_ALIGN_SUM_TOLERANCE = 1e-5  # opposite-pair alignment sum


# ---------------------------------------------------------------------------
# URDFGroundTruth: walks the full joint chain
# ---------------------------------------------------------------------------

class URDFGroundTruth:
    """Parse the URDF and compute frame transforms by walking the joint chain.

    Joint chain:
        world -> imu_link (dynamic: apply imu_quat)
          -> base_link (fixed: base_joint origin xyz + rpy)
            -> screen_N_link (fixed: screen_N_joint origin xyz + rpy)
              -> screen_N_edge_X (fixed: edge joint origin xyz, rpy="0 0 0")
    """

    def __init__(self, urdf_path: str):
        tree = ET.parse(urdf_path)
        root = tree.getroot()

        # Parse all joints: parent -> child with xyz and rpy.
        self._joints = {}  # child_link -> (parent_link, xyz, rpy)
        for joint_elem in root.findall('joint'):
            child_link = joint_elem.find('child').get('link')
            parent_link = joint_elem.find('parent').get('link')
            origin = joint_elem.find('origin')
            if origin is not None:
                xyz = np.array([float(v) for v in origin.get('xyz', '0 0 0').split()])
                rpy = np.array([float(v) for v in origin.get('rpy', '0 0 0').split()])
            else:
                xyz = np.zeros(3)
                rpy = np.zeros(3)
            self._joints[child_link] = (parent_link, xyz, rpy)

    def _get_chain(self, link_name: str) -> list:
        """Walk from link_name back to imu_link, returning list of
        (child_link, xyz, rpy) from imu_link outward."""
        chain = []
        current = link_name
        while current != 'imu_link':
            if current not in self._joints:
                raise ValueError(f'Cannot find joint for link: {current}')
            parent, xyz, rpy = self._joints[current]
            chain.append((current, xyz, rpy))
            current = parent
        chain.reverse()
        return chain

    def get_frame_transform(self, link_name: str, imu_quat: np.ndarray):
        """Compute world-frame position and rotation of a link given an IMU quaternion.

        Returns (position, rotation) where position is (3,) and rotation is a Rotation.
        """
        # Start at imu_link in world frame.
        pos = np.zeros(3)
        rot = Rotation.from_quat(imu_quat)

        # Walk the chain, applying each fixed joint.
        for child, xyz, rpy in self._get_chain(link_name):
            pos = pos + rot.apply(xyz)
            rot = rot * Rotation.from_euler('xyz', rpy)

        return pos, rot

    def get_frame_z(self, link_name: str, imu_quat: np.ndarray) -> float:
        """Get the z-position of a link in world frame."""
        pos, _ = self.get_frame_transform(link_name, imu_quat)
        return pos[2]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope='module')
def ground_truth():
    return URDFGroundTruth(_URDF_PATH)


@pytest.fixture(scope='module')
def dice_orientation():
    return DiceOrientation(_CONFIG_PATH)


@pytest.fixture(scope='module')
def random_quats():
    """200 uniformly random unit quaternions on SO(3), seeded for reproducibility."""
    rng = np.random.default_rng(RNG_SEED)
    rotations = Rotation.random(NUM_RANDOM_QUATS, random_state=rng)
    return rotations.as_quat()  # (200, 4) in [x, y, z, w] order


# ---------------------------------------------------------------------------
# Test classes
# ---------------------------------------------------------------------------

class TestFaceZPositions:
    """For 200 random quaternions x 6 screens, compare face_z from
    DiceOrientation.compute() against URDFGroundTruth.get_frame_z('screen_N_link', q).
    """

    def test_face_z_matches_urdf(self, dice_orientation, ground_truth, random_quats):
        for qi in range(NUM_RANDOM_QUATS):
            q = random_quats[qi]
            result = dice_orientation.compute(q)
            for sid in range(1, NUM_SCREENS + 1):
                expected_z = ground_truth.get_frame_z(f'screen_{sid}_link', q)
                actual_z = result['face_z'][sid]
                assert abs(actual_z - expected_z) < _Z_TOLERANCE, (
                    f'face_z mismatch for screen {sid}, quat index {qi}: '
                    f'expected {expected_z}, got {actual_z}'
                )


class TestUpAlignment:
    """Verify up_alignment equals face_z / face_offset clamped to [-1, 1]."""

    def test_up_alignment_equals_face_z_over_offset(self, dice_orientation, random_quats):
        face_offset = 0.0508  # from dice_geometry.yaml

        for qi in range(NUM_RANDOM_QUATS):
            q = random_quats[qi]
            result = dice_orientation.compute(q)
            for sid in range(1, NUM_SCREENS + 1):
                fz = result['face_z'][sid]
                expected_alignment = np.clip(fz / face_offset, -1.0, 1.0)
                actual_alignment = result['up_alignments'][sid]
                assert abs(actual_alignment - expected_alignment) < 1e-9, (
                    f'up_alignment mismatch for screen {sid}, quat index {qi}: '
                    f'expected {expected_alignment}, got {actual_alignment}'
                )


class TestTopBottomScreen:
    """Verify top screen has highest face_z, bottom has lowest face_z."""

    def test_top_has_highest_z(self, dice_orientation, random_quats):
        for qi in range(NUM_RANDOM_QUATS):
            q = random_quats[qi]
            result = dice_orientation.compute(q)
            face_z = result['face_z']
            top_z = face_z[result['top_screen']]
            for sid, z in face_z.items():
                assert top_z >= z - 1e-12, (
                    f'Top screen {result["top_screen"]} z={top_z} is not highest; '
                    f'screen {sid} has z={z}, quat index {qi}'
                )

    def test_bottom_has_lowest_z(self, dice_orientation, random_quats):
        for qi in range(NUM_RANDOM_QUATS):
            q = random_quats[qi]
            result = dice_orientation.compute(q)
            face_z = result['face_z']
            bottom_z = face_z[result['bottom_screen']]
            for sid, z in face_z.items():
                assert bottom_z <= z + 1e-12, (
                    f'Bottom screen {result["bottom_screen"]} z={bottom_z} is not lowest; '
                    f'screen {sid} has z={z}, quat index {qi}'
                )


class TestEdgeZPositions:
    """For 200 random quaternions x 6 screens x 4 edges, compare
    compute_all_edges() against URDFGroundTruth.get_frame_z('screen_N_edge_X', q).
    """

    def test_all_edge_z_matches_urdf(self, dice_orientation, ground_truth, random_quats):
        for qi in range(NUM_RANDOM_QUATS):
            q = random_quats[qi]
            all_edges = dice_orientation.compute_all_edges(q)
            for sid in range(1, NUM_SCREENS + 1):
                for edge_name in EDGE_NAMES:
                    link_name = f'screen_{sid}_edge_{edge_name}'
                    expected_z = ground_truth.get_frame_z(link_name, q)
                    actual_z = all_edges[sid][edge_name]
                    assert abs(actual_z - expected_z) < _Z_TOLERANCE, (
                        f'edge_z mismatch for screen {sid} edge {edge_name}, '
                        f'quat index {qi}: expected {expected_z}, got {actual_z}'
                    )


class TestEdgeRotation:
    """For 200 random quaternions, verify top screen's rotation matches
    which edge has lowest z per ground truth."""

    def test_rotation_matches_lowest_edge(self, dice_orientation, ground_truth, random_quats):
        edge_to_rotation = {'bottom': 0, 'right': 1, 'top': 2, 'left': 3}

        for qi in range(NUM_RANDOM_QUATS):
            q = random_quats[qi]
            result = dice_orientation.compute(q)
            top_screen = result['top_screen']

            # Get ground-truth edge z positions for the top screen.
            edge_z = {}
            for edge_name in EDGE_NAMES:
                link_name = f'screen_{top_screen}_edge_{edge_name}'
                edge_z[edge_name] = ground_truth.get_frame_z(link_name, q)

            # Lowest edge determines expected rotation.
            lowest_edge = min(edge_z, key=edge_z.get)
            expected_rotation = edge_to_rotation[lowest_edge]

            assert result['top_rotation'] == expected_rotation, (
                f'Rotation mismatch for quat index {qi}: '
                f'top_screen={top_screen}, lowest_edge={lowest_edge}, '
                f'expected rotation={expected_rotation}, got {result["top_rotation"]}, '
                f'edge_z={edge_z}'
            )


class TestKnownOrientations:
    """Identity quaternion sanity check and opposite face pair tests."""

    def test_identity_quaternion(self, dice_orientation, ground_truth):
        """With identity IMU quaternion, check that face_z values match URDF."""
        q_identity = np.array([0.0, 0.0, 0.0, 1.0])
        result = dice_orientation.compute(q_identity)

        for sid in range(1, NUM_SCREENS + 1):
            expected_z = ground_truth.get_frame_z(f'screen_{sid}_link', q_identity)
            actual_z = result['face_z'][sid]
            assert abs(actual_z - expected_z) < _Z_TOLERANCE, (
                f'Identity quat: face_z mismatch for screen {sid}: '
                f'expected {expected_z}, got {actual_z}'
            )

    def test_opposite_face_pairs(self, dice_orientation, random_quats):
        """Opposite face pairs (1/6, 2/4, 3/5) should have opposite up_alignments
        (sum approximately 0)."""
        opposite_pairs = [(1, 6), (2, 4), (3, 5)]

        for qi in range(NUM_RANDOM_QUATS):
            q = random_quats[qi]
            result = dice_orientation.compute(q)
            alignments = result['up_alignments']

            for a, b in opposite_pairs:
                total = alignments[a] + alignments[b]
                assert abs(total) < _ALIGN_SUM_TOLERANCE, (
                    f'Opposite pair ({a}, {b}) alignments do not sum to 0: '
                    f'{alignments[a]} + {alignments[b]} = {total}, quat index {qi}'
                )
