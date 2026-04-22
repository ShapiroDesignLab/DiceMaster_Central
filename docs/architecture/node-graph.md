# ROS2 Node Graph

This document describes the ROS2 nodes in DiceMaster_Central, the topics they publish and subscribe to, and the message types used.

## Node Hierarchy

```
dicemaster.launch.py
├── imu.launch.py
│   ├── imu_hardware            (Node)
│   ├── imu_filter_madgwick     (External Node — imu_tools)
│   └── motion_detector         (Node)
├── chassis.launch.py
│   └── dice_chassis_node       (Node)
├── screens.launch.py
│   ├── screen_bus_manager_0    (Node)
│   ├── screen_bus_manager_1    (Node)
│   └── screen_bus_manager_3    (Node)
└── managers.launch.py
    └── game_manager            (Node)
        └── strategy_{game_name} (Child Node — added dynamically to executor)
```

---

## Nodes

### imu_hardware

**Source:** `src/dicemaster_central/dicemaster_central/hw/imu/imu_hardware.py`
**Class:** `IMUHardwareNode`
**ROS2 name:** `imu_hardware`

Reads raw accelerometer and gyroscope data from an MPU6050 over I2C (bus 6, address 0x68 by default). Applies calibration biases loaded from `~/.dicemaster/imu_calibration/`. Publishes at `polling_rate` Hz (default 50 Hz).

| Direction | Topic | Type |
|---|---|---|
| Publishes | `/imu/data_raw` | `sensor_msgs/Imu` |
| Service | `/imu/calibrate` | `std_srvs/Empty` |

---

### imu_filter_madgwick

**Source:** `src/imu_tools/imu_filter_madgwick/` (vendored third-party package)
**ROS2 name:** `imu_filter_madgwick`

Fuses raw IMU data using the Madgwick filter algorithm to produce a filtered `Imu` message with orientation (quaternion). Configured in `imu.launch.py` with `use_mag: false`, `gain: 0.1`, `world_frame: enu`.

| Direction | Topic | Type |
|---|---|---|
| Subscribes | `/imu/data_raw` | `sensor_msgs/Imu` |
| Publishes | `/imu/data` | `sensor_msgs/Imu` |

---

### motion_detector

**Source:** `src/dicemaster_central/dicemaster_central/hw/imu/motion_detector.py`
**Class:** `MotionDetectorNode`
**ROS2 name:** `motion_detector`

Analyzes filtered IMU data to detect shaking. Maintains rolling history buffers (50 samples) for acceleration and angular velocity magnitudes. Detects shaking via acceleration standard deviation (threshold 5.0) and mean gyro magnitude (threshold 5.0 rad/s). Publishes a `MotionDetection` message on every IMU callback.

| Direction | Topic | Type |
|---|---|---|
| Subscribes | `/imu/data` | `sensor_msgs/Imu` |
| Publishes | `/imu/motion` | `dicemaster_central_msgs/MotionDetection` |

Note: `dice_chassis_node` also contains an embedded motion detector that publishes to `/imu/motion`. In the current launch configuration, both nodes may be active; check `imu.launch.py` and `chassis.launch.py` to confirm which is active in your deployment.

---

### dice_chassis_node

**Source:** `src/dicemaster_central/dicemaster_central/hw/chassis.py`
**Class:** `ChassisNode`
**ROS2 name:** `dice_chassis_node`

Subscribes to filtered IMU data and computes the orientation of all 6 screens using precomputed geometry (`resource/dice_geometry.yaml`). Determines which screen is facing up and which is facing down, and computes the in-plane rotation of the top screen by finding the lowest edge. Publishes at 10 Hz (configurable via `orientation_rate` parameter).

Includes stickiness logic to suppress jitter near ambiguous orientations (configurable via `rotation_threshold`, default 0.7) and edge debouncing (configurable via `edge_detection_frames`, default 2 consecutive detections required before confirming a rotation change).

| Direction | Topic | Type |
|---|---|---|
| Subscribes | `/imu/data` | `sensor_msgs/Imu` |
| Subscribes | `/data/imu` | `sensor_msgs/Imu` (alternate topic, same callback) |
| Publishes | `/chassis/orientation` | `dicemaster_central_msgs/ChassisOrientation` |
| Publishes | `/chassis/screen_1_pose` | `dicemaster_central_msgs/ScreenPose` |
| Publishes | `/chassis/screen_2_pose` | `dicemaster_central_msgs/ScreenPose` |
| Publishes | `/chassis/screen_3_pose` | `dicemaster_central_msgs/ScreenPose` |
| Publishes | `/chassis/screen_4_pose` | `dicemaster_central_msgs/ScreenPose` |
| Publishes | `/chassis/screen_5_pose` | `dicemaster_central_msgs/ScreenPose` |
| Publishes | `/chassis/screen_6_pose` | `dicemaster_central_msgs/ScreenPose` |
| Publishes | `/imu/motion` | `dicemaster_central_msgs/MotionDetection` |

---

### screen_bus_manager_0 / _1 / _3

**Source:** `src/dicemaster_central/dicemaster_central/hw/screen/screen_bus_manager.py`
**Class:** `ScreenBusManager`
**ROS2 names:** `screen_bus_manager_0`, `screen_bus_manager_1`, `screen_bus_manager_3`

One node per SPI bus. Each node owns a `SPIDevice` for its bus and `Screen` objects for the screens assigned to that bus (from `dice_config.screen_configs`). Media commands are enqueued to a `BusEventLoop` background thread that serializes SPI transmissions with per-bus rate limiting.

Screen-to-bus assignments (from `config.py`):

| Bus | Screens |
|---|---|
| Bus 0 (`screen_bus_manager_0`) | Screen 1, Screen 6 |
| Bus 1 (`screen_bus_manager_1`) | Screen 3, Screen 5 |
| Bus 3 (`screen_bus_manager_3`) | Screen 2, Screen 4 |

For `screen_bus_manager_0` (screens 1 and 6):

| Direction | Topic | Type |
|---|---|---|
| Subscribes | `/screen_1_cmd` | `dicemaster_central_msgs/ScreenMediaCmd` |
| Subscribes | `/screen_6_cmd` | `dicemaster_central_msgs/ScreenMediaCmd` |
| Subscribes | `/chassis/screen_1_pose` | `dicemaster_central_msgs/ScreenPose` |
| Subscribes | `/chassis/screen_6_pose` | `dicemaster_central_msgs/ScreenPose` |

For `screen_bus_manager_1` (screens 3 and 5):

| Direction | Topic | Type |
|---|---|---|
| Subscribes | `/screen_3_cmd` | `dicemaster_central_msgs/ScreenMediaCmd` |
| Subscribes | `/screen_5_cmd` | `dicemaster_central_msgs/ScreenMediaCmd` |
| Subscribes | `/chassis/screen_3_pose` | `dicemaster_central_msgs/ScreenPose` |
| Subscribes | `/chassis/screen_5_pose` | `dicemaster_central_msgs/ScreenPose` |

For `screen_bus_manager_3` (screens 2 and 4):

| Direction | Topic | Type |
|---|---|---|
| Subscribes | `/screen_2_cmd` | `dicemaster_central_msgs/ScreenMediaCmd` |
| Subscribes | `/screen_4_cmd` | `dicemaster_central_msgs/ScreenMediaCmd` |
| Subscribes | `/chassis/screen_2_pose` | `dicemaster_central_msgs/ScreenPose` |
| Subscribes | `/chassis/screen_4_pose` | `dicemaster_central_msgs/ScreenPose` |

---

### game_manager

**Source:** `src/dicemaster_central/dicemaster_central/managers/game_manager.py`
**Class:** `GameManager`
**ROS2 name:** `game_manager`

Discovers strategies from `~/.dicemaster/strategies/` and `examples/strategies/`, and games from `~/.dicemaster/games/` and `examples/games/` on startup. Auto-starts the default game (`GameConfig.default_game`, currently `chinese_quizlet`) after a 1-second deferred timer to avoid executor deadlock. Provides a `DiceGameControl` service for runtime game switching.

| Direction | Topic/Service | Type |
|---|---|---|
| Service | `/game_control` | `dicemaster_central_msgs/DiceGameControl` |

Service commands:

| Command | Request fields | Response fields |
|---|---|---|
| `list` | — | `available_games`, `current_game`, `success`, `message` |
| `start` | `game_name` | `success`, `message`, `current_game` |
| `stop` | — | `success`, `message` |
| `restart` | — | `success`, `message`, `current_game` |

---

### strategy_{game_name}

**Source:** User-defined, inherits from `BaseStrategy` in `src/dicemaster_central/dicemaster_central/games/strategy.py`
**ROS2 name:** `strategy_{game_name}` (e.g. `strategy_chinese_quizlet`)

Dynamically created and added to the `MultiThreadedExecutor` by `GameManager.start_game()`. The strategy subscribes to sensor topics and publishes `ScreenMediaCmd` messages to drive the display. Exact topics depend on the strategy implementation.

Typical strategy subscriptions (example: `ShakeQuizletStrategy`):

| Direction | Topic | Type |
|---|---|---|
| Subscribes (indirectly via `motion.on_shake`) | `/imu/motion` | `dicemaster_central_msgs/MotionDetection` |
| Subscribes (indirectly via `orientation.on_change`) | `/chassis/orientation` | `dicemaster_central_msgs/ChassisOrientation` |
| Publishes | `/screen_{id}_cmd` | `dicemaster_central_msgs/ScreenMediaCmd` |

---

## Custom Message Types

All message definitions are in `src/dicemaster_central_msgs/msg/` and `srv/`.

### ScreenMediaCmd.msg

Instructs a screen bus manager to display content on a screen.

| Field | Type | Description |
|---|---|---|
| `screen_id` | `int32` | Target screen (1–6) |
| `media_type` | `string` | `"text"`, `"image"`, or `"gif"` |
| `file_path` | `string` | Absolute path to the asset file or directory |

### ChassisOrientation.msg

Reports which screen faces are currently up and down.

| Field | Type | Description |
|---|---|---|
| `top_screen_id` | `int32` | Screen ID with highest up-alignment (facing up) |
| `bottom_screen_id` | `int32` | Screen ID with lowest up-alignment (facing down) |
| `stamp` | `builtin_interfaces/Time` | Timestamp |

### ScreenPose.msg

Reports the orientation state of a single screen.

| Field | Type | Description |
|---|---|---|
| `screen_id` | `int32` | Screen ID (1–6) |
| `rotation` | `int32` | In-plane rotation (0=0°, 1=90°, 2=180°, 3=270°) |
| `up_alignment` | `float32` | Dot product with up vector, range −1.0 to 1.0 |
| `is_facing_up` | `bool` | True if this screen is the top face and up_alignment > 0.7 |
| `stamp` | `builtin_interfaces/Time` | Timestamp |

### MotionDetection.msg

Reports shake detection results from the IMU pipeline.

| Field | Type | Description |
|---|---|---|
| `header` | `std_msgs/Header` | Timestamp and frame |
| `shaking` | `bool` | True if shaking is currently detected |
| `shake_intensity` | `float32` | Shake magnitude, 0.0 (still) to 1.0 (intense) |
| `stillness_factor` | `float32` | 1.0 − shake_intensity |

### DiceGameControl.srv

Service for runtime game management.

Request:

| Field | Type | Description |
|---|---|---|
| `command` | `string` | `"list"`, `"start"`, `"stop"`, or `"restart"` |
| `game_name` | `string` | Required for `"start"` |

Response:

| Field | Type | Description |
|---|---|---|
| `success` | `bool` | Whether the command succeeded |
| `message` | `string` | Human-readable result or error |
| `available_games` | `string[]` | Populated by `"list"` command |
| `current_game` | `string` | Name of the currently running game |

---

## Full Topic Summary

```
/imu/data_raw          sensor_msgs/Imu              imu_hardware → imu_filter_madgwick
/imu/data              sensor_msgs/Imu              imu_filter_madgwick → dice_chassis_node, motion_detector
/imu/motion            MotionDetection              dice_chassis_node (or motion_detector) → strategy_*

/chassis/orientation   ChassisOrientation           dice_chassis_node → strategy_*
/chassis/screen_1_pose ScreenPose                   dice_chassis_node → screen_bus_manager_0
/chassis/screen_2_pose ScreenPose                   dice_chassis_node → screen_bus_manager_3
/chassis/screen_3_pose ScreenPose                   dice_chassis_node → screen_bus_manager_1
/chassis/screen_4_pose ScreenPose                   dice_chassis_node → screen_bus_manager_3
/chassis/screen_5_pose ScreenPose                   dice_chassis_node → screen_bus_manager_1
/chassis/screen_6_pose ScreenPose                   dice_chassis_node → screen_bus_manager_0

/screen_1_cmd          ScreenMediaCmd               strategy_* → screen_bus_manager_0
/screen_2_cmd          ScreenMediaCmd               strategy_* → screen_bus_manager_3
/screen_3_cmd          ScreenMediaCmd               strategy_* → screen_bus_manager_1
/screen_4_cmd          ScreenMediaCmd               strategy_* → screen_bus_manager_3
/screen_5_cmd          ScreenMediaCmd               strategy_* → screen_bus_manager_1
/screen_6_cmd          ScreenMediaCmd               strategy_* → screen_bus_manager_0

/game_control          DiceGameControl (service)    game_manager
```
