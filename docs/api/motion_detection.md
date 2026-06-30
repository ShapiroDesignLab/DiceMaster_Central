# Motion Detection API

> **Note**: This document was written against an earlier IMU implementation that used a
> quaternion-based Kalman filter and published custom `IMUPose`, `IMUCalibration`, and
> `MotionDetection` messages with a Kalman filter backend. The current implementation uses
> the Madgwick filter from `imu_tools` and a simpler `MotionDetectorNode` that does not
> expose a Kalman filter, calibration topics, or the `/imu/pose_legacy` / `/imu/accel` /
> `/imu/angvel` compatibility topics listed below.
>
> Until the current IMU pipeline is re-documented, refer to the source directly:
> `src/dicemaster_central/dicemaster_central/hw/imu/motion_detector.py`

---

## Current Behaviour (brief)

- Subscribes to: `/imu/data` (`sensor_msgs/Imu`) — filtered output from `imu_filter_madgwick`
- Publishes to: `/imu/motion` (`dicemaster_central_msgs/MotionDetection`)
- Detects: `shaking` (bool), `shake_intensity` (float), `stillness_factor` (float)
- Rotation detection fields (`rotation_x_positive`, etc.) are wired in the message but currently always `False` (future feature)

## Archived Content (pre-refactor, untested against current code)

The description below documents the Kalman-filter-based implementation that predated the
Madgwick/`imu_tools` refactor. Topics, parameters, and message types listed here may not exist
in the current codebase.
