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

**Status:** This patch was applied locally but has been reverted in favor of
the C++ rewrite which made the savings negligible. The upstream imu_tools
submodule (at `src/imu_tools`) is used unmodified.

**Savings (when active):** Chassis subscription drops from 50Hz to 20Hz DDS overhead

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

## Transport Layer Benchmark: CycloneDDS + iceoryx Shared Memory

Tested CycloneDDS with iceoryx shared memory transport vs default FastRTPS.
Iceoryx requires a RouDi daemon process and `CYCLONEDDS_URI` config with
`<SharedMemory><Enable>true</Enable></SharedMemory>`.

| Process | FastRTPS | CycloneDDS + SHM | Diff |
|---------|----------|-------------------|------|
| imu_hardware.py | 25.3% | 26.0% | +0.7% |
| imu_filter_madgwick | 6.6% | 5.5% | -1.1% |
| chassis.py | 26.9% | 26.1% | -0.8% |
| **Total** | **58.8%** | **57.6%** | **-1.2%** |

**Verdict: No meaningful difference.** Shared memory eliminates network copying
but that was already negligible for local-only communication. The bottleneck is
the rclpy executor/callback overhead and DDS serialization layer, not the
transport. Stick with default FastRTPS to avoid RouDi operational complexity.

## C++ Rewrite

Rewrote imu_hardware and chassis nodes in C++ (`dicemaster_cpp` package). The Python nodes are preserved but the launch files now use the C++ versions.

**Files:**
- `dicemaster_cpp/src/imu_hardware_node.cpp` — C++ IMU node with I2C_RDWR ioctl, simulate mode for benchmarking without hardware
- `dicemaster_cpp/src/chassis_node.cpp` — C++ chassis with orientation, motion detection, edge rotation
- `dicemaster_cpp/src/dice_orientation.cpp` — Full port of orientation_math.py using Eigen
- `dicemaster_cpp/include/dicemaster_cpp/dice_orientation.hpp` — Header

**Benchmark at 50Hz (simulate mode, no physical IMU):**

| Process | Python (optimized) | C++ | Change |
|---------|-------------------|-----|--------|
| imu_hardware | ~20% | 4.5% | **-15.5%** |
| imu_filter_madgwick | ~17% | 7.0% | **-10%** |
| chassis | ~20% | 6.4% | **-13.6%** |
| **Total** | **~57%** | **~18%** | **-39%** |

The C++ pipeline uses **~18% of one core** at 50Hz, down from the original Python baseline of ~102%. That's a **5.7x total reduction**.

The IMU node has a `simulate` parameter that auto-enables when no MPU6050 is detected (or can be set explicitly with `simulate:=true`). This generates synthetic IMU data with realistic noise so the full pipeline can be benchmarked without hardware.

## Future Optimization Opportunities

1. **Fork imu_tools** — Track the publish_rate patch in git properly
2. **Composable nodes** — Load Madgwick filter + imu_hardware_cpp + chassis_cpp as component nodes in a single process with `use_intra_process_comms: true`. Would eliminate all inter-process DDS hops. Estimated total: <5% CPU
3. **Microcontroller offload** — ESP32/Pi Pico runs IMU read + Madgwick, sends filtered data over UART to Pi at low rate. Pipeline essentially free on Pi
