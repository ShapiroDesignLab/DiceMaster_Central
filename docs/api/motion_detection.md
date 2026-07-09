# Motion Detection API

How the dice senses shaking and orientation, and what a game can subscribe to.

This document describes the current Madgwick-filter pipeline. Source of truth:
- `src/dicemaster_central/dicemaster_central/hw/imu/imu_hardware.py` (MPU-6050 reader)
- `src/dicemaster_central/dicemaster_central/hw/imu/motion_detector.py` (shake detection)
- `src/imu_tools/` (third-party Madgwick filter)
- `src/dicemaster_central/dicemaster_central/hw/chassis.py` (orientation → screen poses)

For game authors: use the `dice.motion` and `dice.orientation` SDK
(`docs/creator/strategy.md`) rather than subscribing to these topics directly.

---

## Pipeline

```
MPU-6050 (I2C 0x68)
   │  raw accel + gyro
   ▼
imu_hardware            →  /imu/data_raw   (sensor_msgs/Imu)
   │
   ▼
imu_filter_madgwick     →  /imu/data       (sensor_msgs/Imu, now with orientation quaternion)
   │
   ├──────────────► motion_detector  →  /imu/motion    (MotionDetection)
   │
   └──────────────► chassis          →  /chassis/orientation, /chassis/screen_{id}_pose
```

The Madgwick filter (`imu_filter_madgwick`, launched from `imu.launch.py`) is
configured with `use_mag: false`, `gain: 0.1`, `world_frame: 'enu'`. It converts
raw IMU data into an orientation-bearing `/imu/data`.

---

## `MotionDetectorNode` → `/imu/motion`

`motion_detector.py`. Subscribes to `/imu/data`, publishes
`dicemaster_central_msgs/msg/MotionDetection` on `/imu/motion` on every incoming
IMU sample.

### What it detects

It keeps a rolling history (`history_size = 50`) of acceleration and gyro
magnitudes and derives:

- **`shaking`** (bool) — true when recent acceleration variance exceeds
  `shake_variance_threshold` (5.0) **or** mean gyro magnitude exceeds
  `shake_gyro_threshold` (5.0 rad/s). Needs ≥20 samples of history first.
- **`shake_intensity`** (0.0–1.0) — normalized blend of acceleration std-dev
  and gyro activity over the last 10 samples.
- **`stillness_factor`** (0.0–1.0) — `1.0 - shake_intensity`; 1.0 means
  perfectly still.

Tunable constants live at the top of `MotionDetectorNode.__init__`:
`shake_accel_threshold`, `shake_gyro_threshold`, `shake_variance_threshold`,
`history_size`.

### `MotionDetection` message fields

```
std_msgs/Header header

# Rotation detection — WIRED BUT NOT IMPLEMENTED (always False / 0.0)
bool    rotation_x_positive / rotation_x_negative
bool    rotation_y_positive / rotation_y_negative
bool    rotation_z_positive / rotation_z_negative
float64 rotation_intensity

# Active fields
bool    shaking
float64 shake_intensity     # 0.0–1.0
float64 stillness_factor    # 0.0–1.0, 1.0 = perfectly still
```

> **Note:** the `rotation_*` booleans and `rotation_intensity` are present in the
> message but the detector currently hard-codes them to `False` / `0.0`
> (see `get_motion_summary()` — marked "Future feature"). Orientation is handled
> by the chassis node instead (below), not by these fields. Don't rely on the
> rotation fields of `/imu/motion`.

---

## Orientation → `chassis` node

Shaking and orientation are separate concerns. Orientation (which face is up,
how each screen is rotated relative to gravity) is computed by `chassis.py` from
`/imu/data`, not by the motion detector. It publishes:

- `/chassis/orientation` (`ChassisOrientation`) — top/bottom screen IDs
- `/chassis/screen_{id}_pose` (`ScreenPose`) — per-screen rotation `0–3`,
  `up_alignment`, `is_facing_up`

The screen pipeline consumes `/chassis/screen_{id}_pose` to keep displayed
content upright (see `docs/api/display_media.md`). Orientation math is in
`hw/orientation_math.py`; see also `docs/decisions/` and the chassis tests.

---

## Debugging

```bash
ros2 topic echo /imu/data_raw --once     # hardware reading anything?
ros2 topic echo /imu/data --once         # filter producing orientation?
ros2 topic echo /imu/motion              # shake detection output
ros2 topic hz   /imu/data                # sample rate sanity check
ros2 topic echo /chassis/orientation --once
```

| Symptom | Check |
|---|---|
| No `/imu/data_raw` | I2C enabled? `ls /dev/i2c-*`, `i2cdetect -y <bus>` for 0x68 |
| `/imu/data_raw` but no `/imu/data` | is `imu_filter_madgwick` running? `ros2 node list` |
| Never detects shakes | thresholds in `motion_detector.py` may need tuning for your hardware |
| Orientation wrong | that's the chassis node, not the motion detector — check `chassis.py` |

See `docs/setup/rpi_hw_config.md` for I2C setup and `docs/setup/dev_setup.md`
for the broader debugging toolkit.
