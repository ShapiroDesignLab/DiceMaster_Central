# CPU Optimization Log — IMU + Chassis Pipeline

**Platform:** Raspberry Pi 4 (ARM Cortex-A72, 4 cores), ROS2 Humble, Debian Bookworm

## Baseline

Full IMU pipeline (imu_hardware → Madgwick filter → chassis) consumed ~102% of a single core, nearly saturating it.

| Process | CPU (per-core %) | Notes |
|---------|-----------------|-------|
| chassis.py | ~43% | TF2 broadcasting + MultiThreadedExecutor + 50Hz timer |
| imu_hardware.py | ~34% | MultiThreadedExecutor + 14 individual I2C reads + numpy |
| imu_filter_madgwick | ~25% | Publishing filtered IMU + TF at 50Hz |
| **Total** | **~102%** | |

## Optimizations Applied

### 1. TF2 Removal from Chassis (commit cc8f458)

Removed `tf_buffer`, `tf_listener`, `tf_broadcaster`, `static_tf_broadcaster` from chassis.py. Nothing in the system consumed TF transforms — they were only useful for RViz debugging. Replaced all TF lookups with `DiceOrientation.compute()` which does the same math directly.

Also switched chassis to `SingleThreadedExecutor` (no concurrent callbacks), merged `MotionDetectorNode` into chassis (eliminates a duplicate DDS subscription), and removed the 50Hz timer (orientation computed in IMU callback instead).

**Savings:** ~36% per-core from TF removal, ~4% from SingleThreadedExecutor

### 2. Disable Madgwick TF Publishing (commit ef6a235)

Set `publish_tf: False` in `imu.launch.py`. The Madgwick filter was broadcasting TF at 50Hz that nothing consumed.

**Savings:** ~20% per-core (eliminates one 50Hz DDS pub+sub pair)

### 3. Madgwick Publish Rate Decoupling (commit 203ac23 + local C++ patch)

Patched `imu_filter_madgwick` to add a `publish_rate` parameter. When set (e.g., `20.0`), the filter still updates its internal state on every incoming IMU message (50Hz) for accuracy, but only publishes the filtered output at the configured rate. Set to 20Hz — a dice doesn't need 50Hz orientation updates.

**Files modified (C++ patch, not yet tracked in git — needs imu_tools fork):**
- `deps/imu_tools/imu_filter_madgwick/src/imu_filter_ros.cpp` — time-gated `shouldPublish()` method
- `deps/imu_tools/imu_filter_madgwick/include/imu_filter_madgwick/imu_filter_ros.h` — added `publish_rate_` and `last_publish_time_` members

**Savings:** Chassis subscription drops from 50Hz to 20Hz DDS overhead

### 4. IMU Hardware Node Optimization (commit 94990b4)

- **SingleThreadedExecutor** instead of MultiThreadedExecutor (node has zero concurrent callbacks)
- **Batch I2C read**: single `read_i2c_block_data(0x3B, 14)` instead of 14 individual `read_byte_data()` calls. MPU6050 registers are contiguous.
- **struct.unpack** instead of manual bit shifting
- **Plain float math** in hot path instead of numpy (numpy kept for one-time calibration only)
- Precomputed scaling constants (`_ACCEL_TO_MS2`, `_GYRO_TO_RADS`)

**Savings:** ~14% per-core on imu_hardware.py

## Final Result

| Process | Before | After | Change |
|---------|--------|-------|--------|
| chassis.py | ~43% | ~20% | **-23%** |
| imu_hardware.py | ~34% | ~20% | **-14%** |
| imu_filter_madgwick | ~25% | ~17% | **-8%** |
| **Total** | **~102%** | **~57%** | **-45%** |

## Root Cause: DDS Per-Message Overhead

The dominant remaining cost is ROS2 DDS middleware overhead. Each 50Hz pub+sub pair costs ~20-24% of a single core on Pi 4 regardless of message size. This is per-message serialization, transport, and deserialization overhead in FastDDS/CycloneDDS.

Benchmarked rate vs CPU for a single pub+sub pair:

| Rate | CPU (per-core %) |
|------|-----------------|
| 50 Hz | ~26.6% |
| 30 Hz | ~14.8% |
| 20 Hz | ~12.6% |
| 10 Hz | ~7.0% |

Other findings:
- FastDDS vs CycloneDDS: no significant difference (~27% each at 50Hz)
- QoS BEST_EFFORT depth=1: saves ~4% vs RELIABLE depth=10
- ROS_LOCALHOST_ONLY: no significant savings

## Future Optimization Opportunities

1. **Fork imu_tools** — Track the publish_rate patch in git properly
2. **Composable nodes** — Load Madgwick filter as a component node (already supports `RCLCPP_COMPONENTS_REGISTER_NODE`). Eliminates inter-process DDS for filter consumers
3. **C++ IMU hardware node** — Rewrite as composable node, load in same container as Madgwick with `use_intra_process_comms: true`. Would eliminate the 50Hz DDS hop between IMU and filter entirely
4. **Single C++ node** — Read I2C + run Madgwick internally + publish only filtered output. Entire pipeline under 5% CPU
5. **Microcontroller offload** — ESP32/Pi Pico runs IMU read + Madgwick, sends filtered data over UART to Pi at low rate. Pipeline essentially free on Pi
