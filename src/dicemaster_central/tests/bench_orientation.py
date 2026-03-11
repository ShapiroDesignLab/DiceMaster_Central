#!/usr/bin/env python3
"""Benchmark: TF-style URDF chain walks vs vectorized DiceOrientation.

Simulates one orientation tick (what runs at 10Hz on the Pi):
  - Old method: 6 face lookups + 24 edge lookups = 30 chain walks
  - New method: DiceOrientation.compute() (2 batch Rotation.apply calls)

Also benchmarks compute_all_edges() (24 edges, for comparison).
"""

import importlib.util
import os
import sys
import time

import numpy as np
from scipy.spatial.transform import Rotation

# ---------------------------------------------------------------------------
# Import without pulling in rclpy
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
EDGE_NAMES = _mod.EDGE_NAMES
NUM_SCREENS = _mod.NUM_SCREENS

# Reuse the ground truth from the test file
import xml.etree.ElementTree as ET

_RESOURCE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'resource'
)
_URDF_PATH = os.path.join(_RESOURCE_DIR, 'dice.urdf')
_CONFIG_PATH = os.path.join(_RESOURCE_DIR, 'dice_geometry.yaml')


class URDFChainWalker:
    """Simulates robot_state_publisher + TF lookups by walking the URDF chain."""

    def __init__(self, urdf_path: str):
        tree = ET.parse(urdf_path)
        root = tree.getroot()
        self._joints = {}
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

    def _get_chain(self, link_name: str):
        chain = []
        current = link_name
        while current != 'imu_link':
            parent, xyz, rpy = self._joints[current]
            chain.append((xyz, rpy))
            current = parent
        chain.reverse()
        return chain

    def get_frame_z(self, link_name: str, imu_quat: np.ndarray) -> float:
        pos = np.zeros(3)
        rot = Rotation.from_quat(imu_quat)
        for xyz, rpy in self._get_chain(link_name):
            pos = pos + rot.apply(xyz)
            rot = rot * Rotation.from_euler('xyz', rpy)
        return pos[2]


def bench_old_method(walker, quats):
    """Simulate the old chassis.py: 6 face lookups + 24 edge lookups per tick."""
    for q in quats:
        # 6 face z-position lookups
        for sid in range(1, 7):
            walker.get_frame_z(f'screen_{sid}_link', q)
        # 24 edge z-position lookups (4 edges × 6 screens)
        for sid in range(1, 7):
            for edge in EDGE_NAMES:
                walker.get_frame_z(f'screen_{sid}_edge_{edge}', q)


def bench_old_method_top_only(walker, quats):
    """Old method but only computing edges for top screen (fairer comparison)."""
    for q in quats:
        # 6 face z-position lookups
        face_z = {}
        for sid in range(1, 7):
            face_z[sid] = walker.get_frame_z(f'screen_{sid}_link', q)
        top = max(face_z, key=face_z.get)
        # 4 edge lookups for top screen only
        for edge in EDGE_NAMES:
            walker.get_frame_z(f'screen_{top}_edge_{edge}', q)


def bench_new_compute(orient, quats):
    """New method: DiceOrientation.compute() — 6 faces + 4 top edges."""
    for q in quats:
        orient.compute(q)


def bench_new_all_edges(orient, quats):
    """New method: compute() + compute_all_edges() — all 6×4 edges."""
    for q in quats:
        orient.compute(q)
        orient.compute_all_edges(q)


def run_benchmark(name, func, *args, n_warmup=50, n_iters=1000):
    """Run a benchmark function, return (total_sec, per_tick_us)."""
    # Generate fresh quaternions
    rng = np.random.default_rng(123)
    quats = Rotation.random(n_warmup + n_iters, random_state=rng).as_quat()

    # Warmup
    func(*args, quats[:n_warmup])

    # Timed run
    start = time.perf_counter()
    func(*args, quats[n_warmup:])
    elapsed = time.perf_counter() - start

    per_tick_us = (elapsed / n_iters) * 1e6
    return elapsed, per_tick_us


def main():
    print("Loading URDF and config...")
    walker = URDFChainWalker(_URDF_PATH)
    orient = DiceOrientation(_CONFIG_PATH)

    n_iters = 2000
    print(f"\nBenchmarking {n_iters} orientation ticks (simulating 10Hz × {n_iters/10:.0f}s)\n")
    print(f"{'Method':<45} {'Total (s)':>10} {'Per tick (μs)':>14} {'Speedup':>8}")
    print("-" * 80)

    # Old method: all 30 lookups (what chassis.py actually does)
    t_old_all, us_old_all = run_benchmark(
        "Old: 30 chain walks", bench_old_method, walker, n_iters=n_iters
    )
    print(f"{'Old: 6 faces + 24 edges (30 lookups)':<45} {t_old_all:>10.3f} {us_old_all:>14.1f} {'1.0x':>8}")

    # Old method: top-only edges (fairer comparison to new compute())
    t_old_top, us_old_top = run_benchmark(
        "Old: 10 chain walks", bench_old_method_top_only, walker, n_iters=n_iters
    )
    print(f"{'Old: 6 faces + 4 top edges (10 lookups)':<45} {t_old_top:>10.3f} {us_old_top:>14.1f} {us_old_all/us_old_top:>7.1f}x")

    # New method: compute() only (6 faces + 4 top edges)
    t_new, us_new = run_benchmark(
        "New: compute()", bench_new_compute, orient, n_iters=n_iters
    )
    speedup_vs_old = us_old_all / us_new
    speedup_vs_fair = us_old_top / us_new
    print(f"{'New: compute() (2 batch calls)':<45} {t_new:>10.3f} {us_new:>14.1f} {speedup_vs_old:>7.1f}x")

    # New method: compute() + all edges (for completeness)
    t_new_all, us_new_all = run_benchmark(
        "New: compute() + all edges", bench_new_all_edges, orient, n_iters=n_iters
    )
    speedup_all = us_old_all / us_new_all
    print(f"{'New: compute() + all 24 edges (3 batch calls)':<45} {t_new_all:>10.3f} {us_new_all:>14.1f} {speedup_all:>7.1f}x")

    print()
    print("Summary:")
    print(f"  Old method (30 lookups):     {us_old_all:>8.1f} μs/tick")
    print(f"  New compute() (production):  {us_new:>8.1f} μs/tick")
    print(f"  Speedup:                     {speedup_vs_old:>8.1f}x")
    print()
    print(f"  At 10Hz: old = {us_old_all/1000:.2f}ms / 100ms tick ({us_old_all/1000:.1f}% of budget)")
    print(f"           new = {us_new/1000:.2f}ms / 100ms tick ({us_new/1000:.1f}% of budget)")
    print()
    print("  Note: This benchmarks pure Python math. On the Pi, the old method")
    print("  also has TF mutex locks, buffer management, timeout handling, and")
    print("  ROS2 executor overhead that add significant constant cost per lookup.")
    print("  The real-world speedup will be larger than shown here.")


if __name__ == '__main__':
    main()
