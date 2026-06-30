# DiceMaster_Central

Raspberry Pi ROS2 runtime for the [DiceMaster](https://github.com/DanielHou315/DiceMaster) programmable dice — coordinates game logic, reads IMU motion/orientation, and streams media commands to 6 ESP32-powered screens over SPI.

For overall system architecture, see the [root repository](https://github.com/DanielHou315/DiceMaster).

## System Role

```
 Game (dice Python SDK)
       │
       ▼
 Chassis Node ◀── IMU (MPU-6050, I2C)
       │
       ▼
 Screen Bus (SPI master) ──▶ 6× ESP32 screens (DiceMaster_ESPScreen)
```

## Quick Start

See [docs/setup/rpi_setup.md](docs/setup/rpi_setup.md) for full setup and deployment instructions.

## Hardware

- Raspberry Pi 4 (or Compute Module 4)
- MPU-6050 6-axis IMU (I2C, address 0x68)
- 6× SPI connections to ESP32 Qualia boards (one SPI bus per pair, CS lines per board)
- Wire protocol: see [docs/protocol.md](https://github.com/DanielHou315/DiceMaster/blob/main/docs/protocol.md) in the root repository

## Documentation

| Section | Contents |
|---|---|
| [docs/api/architecture.md](docs/api/architecture.md) | System architecture, node hierarchy, message flow, configuration |
| [docs/api/display_media.md](docs/api/display_media.md) | Screen display API reference |
| [docs/api/motion_detection.md](docs/api/motion_detection.md) | IMU motion detection API |
| [docs/setup/rpi_setup.md](docs/setup/rpi_setup.md) | Raspberry Pi setup, ROS2 install, build, launch |
| [docs/setup/rpi_hw_config.md](docs/setup/rpi_hw_config.md) | SPI and I2C hardware configuration |
| [docs/setup/auto_start.md](docs/setup/auto_start.md) | Auto-start systemd service setup |
| [docs/setup/dev_setup.md](docs/setup/dev_setup.md) | Development setup, testing, debugging |
| [docs/creator/game.md](docs/creator/game.md) | How to create a new game |
| [docs/creator/strategy.md](docs/creator/strategy.md) | How to create a new strategy |

---

## Changes Since Aug 12, 2025 (NOT TESTED)

> **⚠ The following commits were made after the last known-working state (`439089c` — "Working game horayyy") and have not been tested on hardware:**
>
> - `1ec056c` Ignore converted games output directory
> - `3d8a6f0` Add project documentation framework (ADRs, architecture, runbooks)
> - `b1e8224` refactor: migrate example strategies to dice.* API
> - `44189ec` test: add full game lifecycle integration test for dice ROS2 wrapper
> - `05d0495` feat: add dice timer, assets, log, and strategy modules (ROS2)
> - `01a166c` feat: add dice screen, motion, and orientation modules (ROS2)
> - `e3e312d` feat: scaffold dice ROS2 wrapper package with runtime and test fixtures
> - `12702ff` feat(screen): event-driven bus loop replaces polling threads
> - `205b005` fix(screen): pre-merge cleanup — consistent list API, stop() guard, GIF comment, test margin
> - `8336dd8` test(screen): add integration smoke tests for BusEventLoop end-to-end
> - `2e278ab` fix(screen): guard stop() against double-call, document rotation type contract
> - `84ca61c` refactor(screen): replace PriorityQueue+transmission_thread with BusEventLoop
> - `8f7b80a` fix(screen): clear stale content on empty GIF, warn on unexpected resend type, clean imports
> - `f8dab27` refactor(screen): remove threads/timer, add process_media/advance_gif_frame API
> - `6419ad7` fix(screen): stop() warns if thread alive, fix stale now in GIF deadline, remove unused imports
> - `55ab580` feat(screen): add BusEventLoop with condition-variable event dispatch
> - `71609c9` fix(test): use plain imports in test_event_loop_config (rely on conftest stubs)
> - `a31cc6c` feat(config): add bus_min_interval_s to SPIBusConfig
> - `cfe4042` docs: trim README to entry point with documentation routing table
> - `28eaf43` Add C++ screen bus node architecture stub
> - `f9ee36a` docs: remove old docs structure (developer_guide, setup.md, user_guides/, configure/)
> - `b18a906` docs: fix architecture.md - add References to ToC, split creator rows, remove deployment steps
> - `de070b9` docs: add docs/api/architecture.md (distilled from developer_guide)
> - `70621fb` docs: add docs/creator/ with game and strategy guides
> - `3ca8e13` docs: add docs/setup/rpi_setup.md (merged from setup.md + developer_guide deployment)
> - `3414fc9` docs: add docs/setup/ files (hw_config, auto_start, dev_setup)
> - `c3790c4` docs: add restructure spec and implementation plan
> - `668db2f` Replace time.time() with monotonic counter for queue ordering
> - `fedde97` Remove redundant screen_id check in transmission worker
> - `9c97160` Use NORMAL priority for GIF frames instead of HIGH
> - `e566d13` Fix rotation updates not reaching SPI wire payload
> - `4d0ee7d` Use BytesIO instead of temp file for GIF frame validation
> - `db865c8` Fix GIF double I/O: build protocol messages from already-loaded frames_data
> - `3639651` Move src/dicemaster_central/docs/ to docs/
> - `6b079cd` Consolidate scripts into scripts/
> - `ef291f7` Remove cpu-optimization-log.md
> - `b15ebd5` Consolidate tests, docs, and rviz into proper locations
> - `0dac7fd` Skip imu_tools meta-package in colcon build (needs rviz)
> - `6db76a1` Restructure repo as self-contained colcon workspace
> - `61dfcb8` Switch auto-launch to C++ IMU and chassis nodes
> - `4f4ca88` Add simulate mode to C++ IMU node for benchmarking without hardware
> - `75eecc0` Fix C++ IMU node: use SMBus ioctl instead of raw I2C read/write
> - `2c6f5c5` Fix ament_index_cpp include order in chassis_node.cpp
> - `379105f` Add C++ IMU hardware and chassis nodes for CPU benchmarking
> - `a87a3e0` Add CycloneDDS + iceoryx shared memory benchmark to optimization log
> - `85e0049` Add CPU optimization log documenting IMU pipeline improvements
> - `94990b4` Optimize IMU hardware node: SingleThreadedExecutor + batch I2C read
> - `203ac23` Set Madgwick publish_rate to 20Hz in launch config
> - `ef6a235` Disable Madgwick TF publishing to reduce CPU overhead
> - `cc8f458` chore: update launch files and deps for TF2-free chassis
> - `374db97` fix: cache shake_intensity, remove unused threshold constant
> - `49790a6` Integrate motion detection into chassis node
> - `e570506` fix: add rclpy.shutdown, fix init types, move logger outside lock
> - `426db52` refactor: remove TF2 infrastructure from chassis node
> - `b194d26` test: add TF chain validation (571 quats, 3527 tests) and TF2-free plan
> - `eda3a9e` fix: skip rviz_imu_plugin in colcon build for headless Pi
> - `067e1cc` feat: add self-contained ROS workspace setup
> - `af27944` refactor: remove unused rclpy.duration import
> - `7a176a3` refactor: remove dead TF lookup methods and debug prints from chassis
> - `c9e2e75` feat: replace edge TF lookups with compute() data, top screen only
> - `3c832bc` feat: replace face z TF lookups with DiceOrientation.compute()
> - `2230893` fix: correct dice_geometry.yaml resource path in chassis node
> - `f95a846` feat: add DiceOrientation init and IMU quaternion helper to chassis node
> - `9d750df` test: add chassis orientation pipeline tests (no ROS dependency)
> - `69dda03` Add orientation math benchmark: 57x speedup over chain walks
> - `5c80193` Add orientation math validation tests against URDF ground truth
> - `eb087ab` Fix edge positions missing face centre offset
> - `aa429eb` Add vectorized orientation math module
> - `58c4c2a` Add URDF-to-YAML config extractor for dice geometry
> - `f33f411` Log IMU signal loss and restore only once each
> - `481f0ee` Add CLAUDE.md and .claude/ to gitignore
> - `8bf2875` updated documentation
