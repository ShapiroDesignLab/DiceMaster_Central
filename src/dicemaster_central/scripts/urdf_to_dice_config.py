#!/usr/bin/env python3
"""Extract dice geometry from URDF into a compact YAML config.

Parses the dice URDF to extract fixed-joint transforms (RPY -> quaternion),
face offsets, and canonical edge positions, replacing runtime TF lookups
with precomputed constants.

Usage:
    python3 urdf_to_dice_config.py resource/dice.urdf -o resource/dice_geometry.yaml
"""

import argparse
import math
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from scipy.spatial.transform import Rotation


NUM_SCREENS = 6
EDGE_NAMES = ('top', 'left', 'bottom', 'right')
OFFSET_TOLERANCE = 1e-6  # metres — all face offsets must match within this


def parse_origin(joint_element):
    """Extract xyz and rpy from a joint's <origin> element.

    Returns (xyz, rpy) as tuples of floats.  Missing attributes default to
    all-zeros per the URDF spec.
    """
    origin = joint_element.find('origin')
    if origin is None:
        return (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)

    xyz_str = origin.get('xyz', '0 0 0')
    rpy_str = origin.get('rpy', '0 0 0')

    xyz = tuple(float(v) for v in xyz_str.split())
    rpy = tuple(float(v) for v in rpy_str.split())
    return xyz, rpy


def rpy_to_quaternion(rpy):
    """Convert (roll, pitch, yaw) in radians to [x, y, z, w] quaternion."""
    rot = Rotation.from_euler('xyz', rpy)
    q = rot.as_quat()  # SciPy default order: [x, y, z, w]
    return [round(float(v), 10) for v in q]


def build_joint_map(tree):
    """Return {joint_name: Element} for every joint in the URDF."""
    return {j.get('name'): j for j in tree.iter('joint')}


def extract_base_joint(joint_map):
    """Return the base_joint quaternion (imu_link -> base_link)."""
    joint = joint_map.get('base_joint')
    if joint is None:
        raise ValueError("URDF missing 'base_joint'")
    _, rpy = parse_origin(joint)
    return rpy_to_quaternion(rpy)


def extract_screens(joint_map):
    """Return per-screen data: {screen_id: {'quaternion': [...], 'offset': float}}.

    Also validates that all face offsets have equal magnitude.
    """
    screens = {}
    offsets = []

    for n in range(1, NUM_SCREENS + 1):
        name = f'screen_{n}_joint'
        joint = joint_map.get(name)
        if joint is None:
            raise ValueError(f"URDF missing '{name}'")

        xyz, rpy = parse_origin(joint)
        quat = rpy_to_quaternion(rpy)
        offset = math.sqrt(sum(v * v for v in xyz))
        offsets.append(offset)
        screens[n] = {'quaternion': quat, 'offset': offset}

    # Validate uniform offset magnitude
    ref = offsets[0]
    for i, off in enumerate(offsets[1:], start=2):
        if abs(off - ref) > OFFSET_TOLERANCE:
            raise ValueError(
                f"Screen 1 offset ({ref}) != screen {i} offset ({off})"
            )

    return screens, round(ref, 6)


def extract_edges(joint_map, screen_id):
    """Return {edge_name: [x, y, z]} for one screen's edge joints."""
    edges = {}
    for edge in EDGE_NAMES:
        name = f'screen_{screen_id}_edge_{edge}_joint'
        joint = joint_map.get(name)
        if joint is None:
            raise ValueError(f"URDF missing '{name}'")
        xyz, _ = parse_origin(joint)
        edges[edge] = [round(float(v), 6) for v in xyz]
    return edges


def extract_canonical_edges(joint_map):
    """Extract edges from screen_1 and verify all screens share them."""
    canonical = extract_edges(joint_map, 1)

    for n in range(2, NUM_SCREENS + 1):
        edges_n = extract_edges(joint_map, n)
        for edge in EDGE_NAMES:
            if edges_n[edge] != canonical[edge]:
                raise ValueError(
                    f"Screen {n} edge '{edge}' {edges_n[edge]} "
                    f"differs from screen 1 {canonical[edge]}"
                )

    return canonical


def format_yaml(base_quat, face_offset, canonical_edges, screens):
    """Render the config as a YAML string (hand-formatted for readability)."""
    lines = []

    # --- base_joint ---
    lines.append('base_joint:')
    lines.append(f'  quaternion: {_fmt_list(base_quat)}')
    lines.append('')

    # --- face_offset ---
    lines.append(f'face_offset: {face_offset}')
    lines.append('')

    # --- canonical_edges ---
    lines.append('canonical_edges:')
    for edge in EDGE_NAMES:
        lines.append(f'  {edge}: {_fmt_list(canonical_edges[edge])}')
    lines.append('')

    # --- screens ---
    lines.append('screens:')
    for n in sorted(screens):
        lines.append(f'  {n}:')
        lines.append(f'    joint_quaternion: {_fmt_list(screens[n]["quaternion"])}')
    lines.append('')

    # --- default parameters ---
    lines.append('parameters:')
    lines.append('  rotation_threshold: 0.7')
    lines.append('  edge_detection_frames: 2')
    lines.append('  orientation_rate: 10.0')
    lines.append('  publish_tf: true')
    lines.append('')

    return '\n'.join(lines)


def _fmt_list(values):
    """Format a list of numbers as a YAML inline list."""
    formatted = ', '.join(_fmt_num(v) for v in values)
    return f'[{formatted}]'


def _fmt_num(v):
    """Format a number: integers without decimals, floats trimmed."""
    if v == int(v) and abs(v) < 1e12:
        return str(int(v))
    return f'{v:.10g}'


def main():
    parser = argparse.ArgumentParser(
        description='Extract dice geometry from URDF into YAML config.'
    )
    parser.add_argument('urdf', type=Path, help='Path to dice.urdf')
    parser.add_argument(
        '-o', '--output', type=Path, default=None,
        help='Output YAML path (default: stdout)',
    )
    args = parser.parse_args()

    if not args.urdf.exists():
        print(f'Error: URDF not found: {args.urdf}', file=sys.stderr)
        sys.exit(1)

    tree = ET.parse(args.urdf)
    joint_map = build_joint_map(tree)

    base_quat = extract_base_joint(joint_map)
    screens, face_offset = extract_screens(joint_map)
    canonical_edges = extract_canonical_edges(joint_map)

    yaml_str = format_yaml(base_quat, face_offset, canonical_edges, screens)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(yaml_str)
        print(f'Wrote {args.output}')
    else:
        print(yaml_str)


if __name__ == '__main__':
    main()
