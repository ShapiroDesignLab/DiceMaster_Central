# DiceMaster Architecture

This document provides a high-level technical overview of the DiceMaster system.
For operational details, see the linked references.

## Table of Contents
1. [System Architecture](#system-architecture)
2. [Communication Protocol](#communication-protocol)
3. [ROS2 Node Architecture](#ros2-node-architecture)
4. [Message Flow](#message-flow)
5. [Configuration System](#configuration-system)

---

## System Architecture

### High-Level Component Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                     Raspberry Pi Central                        │
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐     │
│  │ Game Manager │    │   Chassis    │    │     IMU      │     │
│  │    Node      │    │    Node      │    │   Pipeline   │     │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘     │
│         │                   │                    │              │
│         │ /screen_X_cmd     │ /chassis/*         │ /imu/*       │
│         │                   │                    │              │
│  ┌──────▼───────────────────▼────────────────────▼─────┐       │
│  │           Screen Bus Managers (3 instances)         │       │
│  │   Bus 0    │    Bus 1    │    Bus 3                │       │
│  │ (Scr 1,6)  │  (Scr 3,5)  │  (Scr 2,4)              │       │
│  └──────┬──────────────┬──────────────┬────────────────┘       │
│         │              │              │                         │
│         │ SPI          │ SPI          │ SPI                     │
└─────────┼──────────────┼──────────────┼─────────────────────────┘
          │              │              │
    ┌─────▼──┐     ┌─────▼──┐     ┌─────▼──┐
    │ ESP32  │     │ ESP32  │     │ ESP32  │
    │ Screen │     │ Screen │     │ Screen │
    │  1 & 6 │     │  3 & 5 │     │  2 & 4 │
    └────────┘     └────────┘     └────────┘
```

### Component Responsibilities

**Game Manager** (`game_manager.py`):
- Discovers strategies and games from configured directories
- Manages strategy lifecycle (start/stop)
- Provides `/game_control` service for game switching
- Uses `MultiThreadedExecutor` to manage strategy nodes

**Chassis Node** (`chassis.py`):
- Subscribes to `/imu/data` (filtered IMU data)
- Publishes TF transforms for all 6 screens
- Publishes `/chassis/orientation` (top/bottom screen IDs)
- Publishes `/chassis/screen_{id}_pose` (individual screen rotation)
- Detects which screens are facing up/down based on gravity

**IMU Pipeline** (`imu.launch.py`):
- `imu_hardware.py`: Reads MPU6050 over I2C, publishes `/imu/data_raw`
- `imu_filter_madgwick`: Third-party filter, outputs `/imu/data` with orientation
- `motion_detector.py`: Analyzes filtered data, publishes `/imu/motion`

**Screen Bus Managers** (`screen_bus_manager.py`):
- One instance per SPI bus (3 buses: 0, 1, 3)
- Manages 2 screens per bus (using CAN-bus-like addressing)
- Subscribes to `/screen_{id}_cmd` for each screen on its bus
- Handles message queuing with priority (PriorityQueue)
- Processes media (text/images/GIFs) into protocol messages
- Transmits via SPI with DMA alignment (4-byte boundaries)

**Strategy Nodes**:
- User-defined game logic (inherit from `BaseStrategy`)
- Subscribe to sensor topics (`/imu/motion`, `/chassis/orientation`)
- Publish to `/screen_{id}_cmd` topics
- Managed by game manager executor

---

## Communication Protocol

**Primary documentation**: `docs/api/` (see `display_media.md`, `motion_detection.md`)

**Implementation**: `src/dicemaster_central/dicemaster_central/media_typing/protocol.py`

### Message Header (5 bytes)

```
Byte 0: SOF (Start of Frame) = 0x7E
Byte 1: Message Type (see MessageType enum)
Byte 2: Screen ID (bit-masked for CAN-bus behavior)
Byte 3-4: Payload length (BIG_ENDIAN, uint16)
```

### Screen ID Bit Masking

The Screen ID field (Byte 2) implements CAN-bus-like addressing:
- Each screen has ID 0-7
- Bit k corresponds to screen k
- Screen only processes if its bit is set: `(screen_id_byte >> k) & 1`
- Example: `0x05` (binary 0b00000101) targets screens 0 and 2
- Allows multi-screen broadcast

**Implementation**: `protocol.py:screen_id_to_bitmask()`

### Message Types

| Value | Name | Description |
|---|---|---|
| `0x01` | `TEXT_BATCH` | Text display with multiple text items |
| `0x02` | `IMAGE_TRANSFER_START` | Begin image transfer (includes chunk 0) |
| `0x03` | `IMAGE_CHUNK` | Subsequent image chunks |
| `0x04` | `IMAGE_TRANSFER_END` | (Deprecated - timeout-based now) |
| `0x05` | `BACKLIGHT_ON` | Turn screen backlight on |
| `0x06` | `BACKLIGHT_OFF` | Turn screen backlight off |
| `0x07` | `PING_REQUEST` | Check screen connectivity |
| `0x08` | `PING_RESPONSE` | Response from screen |
| `0x09` | `ACKNOWLEDGMENT` | Success acknowledgment |
| `0x0A` | `ERROR_MESSAGE` | Error response with code |

### Text and Image Formats

Text assets are JSON files; images are JPEG; GIFs are directories with `.gif.d` extension.
See `docs/api/display_media.md` for full format specifications.

### DMA Alignment

All SPI messages are padded to 4-byte boundaries for DMA compatibility.
See `protocol.py:pad_to_alignment()`.

---

## ROS2 Node Architecture

### Node Hierarchy

```
Main Launch (dicemaster.launch.py)
├── IMU Launch (imu.launch.py)
│   ├── imu_hardware (Node)
│   ├── imu_filter_madgwick (External Node)
│   └── motion_detector (Node)
├── Chassis Launch (chassis.launch.py)
│   └── chassis (Node)
├── Screens Launch (screens.launch.py)
│   ├── screen_bus_manager_0 (Node)
│   ├── screen_bus_manager_1 (Node)
│   └── screen_bus_manager_3 (Node)
└── Managers Launch (managers.launch.py)
    └── game_manager (Node)
        └── strategy_{game_name} (Child Node, dynamic)
```

### Topic Namespace

```
/imu/
  ├── data_raw (sensor_msgs/Imu) - Raw from hardware
  ├── data (sensor_msgs/Imu) - Filtered with orientation
  └── motion (MotionDetection) - Motion detection results

/chassis/
  ├── orientation (ChassisOrientation) - Top/bottom screen IDs
  └── screen_{1-6}_pose (ScreenPose) - Individual screen rotation

/screen_{1-6}_cmd (ScreenMediaCmd) - Command to display content

/game_control (Service: DiceGameControl) - Game management
```

### Custom Message Types

| Message | Key Fields | Purpose |
|---|---|---|
| `ScreenMediaCmd` | `screen_id`, `media_type`, `file_path` | Command a screen to display content |
| `ChassisOrientation` | `top_screen_id`, `bottom_screen_id` | Which faces are up/down |
| `ScreenPose` | `screen_id`, `rotation`, `up_alignment`, `is_facing_up` | Individual screen orientation |
| `MotionDetection` | `rotation_*`, `shaking`, `rotation_intensity`, `shake_intensity` | IMU motion events |
| `DiceGameControl` (srv) | `command`, `game_name` / `success`, `available_games` | Game lifecycle control |

**Location**: `src/dicemaster_central/dicemaster_central_msgs/`

---

## Message Flow

### Typical Game Interaction Flow

```
1. System Startup
   dicemaster.launch.py
   └→ All nodes launch and initialize

2. IMU Pipeline
   MPU6050 → imu_hardware → /imu/data_raw
   └→ imu_filter_madgwick → /imu/data (with orientation)
      └→ motion_detector → /imu/motion (shake detection)
      └→ chassis → /chassis/orientation, /chassis/screen_{id}_pose

3. Game Manager
   game_manager discovers games/strategies
   └→ Launches default game's strategy node
      └→ Strategy subscribes to /imu/motion, /chassis/orientation

4. User Shakes Dice
   IMU detects motion → /imu/motion published
   └→ Strategy's _motion_callback() triggered
      └→ Strategy decides to change display
         └→ Publishes ScreenMediaCmd to /screen_{id}_cmd

5. Screen Display
   screen_bus_manager receives ScreenMediaCmd
   └→ Queues media request to Screen object
      └→ Screen processes asset file (JSON/JPG)
         └→ Converts to protocol messages
            └→ Queues in PriorityQueue
               └→ Transmission thread sends via SPI
                  └→ ESP32 receives and displays

6. User Rotates Dice
   IMU detects rotation → chassis recalculates orientation
   └→ Publishes new /chassis/screen_{id}_pose
      └→ Screen object receives rotation update
         └→ Re-sends last content with new rotation
            └→ Display updates orientation
```

### Data Flow Diagram

```
┌─────────────┐
│  MPU6050    │ I2C
│   (IMU)     │
└──────┬──────┘
       │ Raw sensor data
       ▼
┌─────────────────┐
│ imu_hardware    │ /imu/data_raw
│                 │ (sensor_msgs/Imu)
└──────┬──────────┘
       │
       ▼
┌────────────────────┐
│ imu_filter_madgwick│ /imu/data
│ (3rd party)        │ (sensor_msgs/Imu + orientation)
└──────┬─────────────┘
       │
       ├────────────────────┐
       │                    │
       ▼                    ▼
┌─────────────┐      ┌─────────────┐
│   chassis   │      │motion_detect│
│             │      │             │
└──────┬──────┘      └──────┬──────┘
       │                    │
       │ /chassis/*         │ /imu/motion
       │                    │
       └────────┬───────────┘
                │
                ▼
        ┌──────────────┐
        │   Strategy   │
        │   (Game)     │
        └──────┬───────┘
               │ /screen_{id}_cmd
               │ (ScreenMediaCmd)
               ▼
      ┌─────────────────┐
      │ Screen Bus Mgr  │
      │   (1 per bus)   │
      └────────┬────────┘
               │ SPI Protocol
               ▼
          ┌────────┐
          │ ESP32  │
          │ Screen │
          └────────┘
```

---

## Configuration System

**Location**: `src/dicemaster_central/dicemaster_central/config.py`

Key configuration classes:
- `DiceConfig` — top-level config (SPI, screens, IMU, game settings)
- `SPIConfig` — SPI bus parameters (speed, mode, buffer size)
- `SPIBusConfig` — per-bus config (bus ID, chip select)
- `ScreenConfig` — per-screen config (ID, bus, default orientation)
- `IMUConfig` — I2C bus, address, calibration, polling rate
- `GameConfig` — game/strategy discovery paths, default game

### Modifying Configuration

**To change screen assignments**:
1. Edit `dice_config.screen_configs` in `config.py`
2. Update `bus_id` for each screen
3. Rebuild: `colcon build --symlink-install`
4. Restart system

**To add a new SPI bus**:
1. Add to `bus_configs`:
   ```python
   4: SPIBusConfig(bus_id=4)
   ```
2. Add bus ID to `active_spi_controllers`
3. Assign screens to new bus in `screen_configs`

**To change default game**:
1. Edit `GameConfig.default_game` in `config.py`
2. Rebuild and restart

---

## References

| Topic | Where to look |
|---|---|
| RPi setup & deployment | `docs/setup/rpi_setup.md` |
| Hardware interfaces (SPI/I2C) | `docs/setup/rpi_hw_config.md` |
| Auto-start service | `docs/setup/auto_start.md` |
| Testing & debugging | `docs/setup/dev_setup.md` |
| Screen display API | `docs/api/display_media.md` |
| IMU API | `docs/api/motion_detection.md` |
| Creating games & strategies | `docs/creator/game.md`, `docs/creator/strategy.md` |
| Protocol source | `src/dicemaster_central/dicemaster_central/media_typing/protocol.py` |
