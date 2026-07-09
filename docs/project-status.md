# Project Status — Known State

This file tracks the tested/untested boundary of the codebase so a new developer
knows how much to trust the current `main`.

## Last hardware-verified state

**Commit `439089c`** — _"Working game horayyy"_ (Aug 12, 2025) is the last state
confirmed working end-to-end on real dice hardware.

## Untested since Aug 12, 2025

Everything below `439089c` has been developed and unit-tested but **not yet
verified on hardware**. This includes two large refactors:

- **Event-driven screen bus** — `BusEventLoop` replaced the old
  PriorityQueue + transmission-thread design. Affects the entire screen
  pipeline (`hw/screen/`). See `docs/api/display_media.md`.
- **Madgwick IMU pipeline** — the custom Kalman filter was replaced by
  `imu_tools`' Madgwick filter, and the chassis node was rebuilt TF2-free.
  See `docs/api/motion_detection.md`.
- **`dice` SDK** — new Python game-authoring SDK
  (`src/dice/`) wrapping the ROS2 plumbing. See `docs/creator/`.
- **Self-contained colcon workspace** — repo restructured so `src/` holds all
  packages and build artifacts are gitignored. See `docs/setup/rpi_setup.md`.

### Next hardware bring-up checklist

When next on hardware, verify in this order and update this file:

1. `colcon build --symlink-install` completes on the Pi.
2. All expected nodes start (`docs/runbooks/deploy.md` → "Verify").
3. `/imu/data` produces orientation; `/imu/motion` reacts to shakes.
4. Each of the 6 screens displays text, image, and GIF content.
5. Rotating the dice keeps content upright on the active screens.

## Full commit history

For the complete list of commits made since `439089c`, use git:

```bash
git log --oneline 439089c..HEAD
```
