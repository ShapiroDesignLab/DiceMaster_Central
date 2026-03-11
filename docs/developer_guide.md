# DiceMaster Developer & Maintenance Guide

This document provides in-depth technical information for developers maintaining the DiceMaster system.

## Table of Contents

1. [System Architecture Overview](#system-architecture-overview)
2. [Communication Protocol](#communication-protocol)
3. [ROS2 Node Architecture](#ros2-node-architecture)
4. [Launch System](#launch-system)
5. [Configuration System](#configuration-system)
6. [Hardware Interfaces](#hardware-interfaces)
7. [Message Flow](#message-flow)
8. [Protocol Implementation](#protocol-implementation)
9. [Testing & Debugging](#testing--debugging)
10. [Deployment](#deployment)

---

## System Architecture Overview

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

### Protocol Specification Location

**Primary documentation**: `docs/protocol.md`

**Implementation**: `dicemaster_central/media_typing/protocol.py`

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

### Message Types (MessageType enum)

Defined in `constants.py:MessageType`:

```python
TEXT_BATCH = 0x01           # Text display with multiple text items
IMAGE_TRANSFER_START = 0x02 # Begin image transfer (includes chunk 0)
IMAGE_CHUNK = 0x03          # Subsequent image chunks
IMAGE_TRANSFER_END = 0x04   # (Deprecated - timeout-based now)
BACKLIGHT_ON = 0x05         # Turn screen backlight on
BACKLIGHT_OFF = 0x06        # Turn screen backlight off
PING_REQUEST = 0x07         # Check screen connectivity
PING_RESPONSE = 0x08        # Response from screen
ACKNOWLEDGMENT = 0x09       # Success acknowledgment
ERROR_MESSAGE = 0x0A        # Error response with code
```

### Text Batch Format

**Header** (6 bytes):
```
Bytes 0-1: Background color (RGB565, uint16 big-endian)
Byte 2: Number of text items (uint8)
Byte 3: Rotation (0=0°, 1=90°, 2=180°, 3=270°)
Bytes 4-5: Reserved
```

**Text Item** (8 bytes + text):
```
Bytes 0-1: X cursor position (uint16 big-endian)
Bytes 2-3: Y cursor position (uint16 big-endian)
Byte 4: Font ID (see FontID enum)
Bytes 5-6: Font color (RGB565, uint16 big-endian)
Byte 7: Text length in bytes (uint8, max 255)
Bytes 8+: UTF-8 encoded text
```

**Encoding**: `protocol.py:encode_text_entry()`

### Image Transfer Format

**ImageStart Message** (9 bytes header + chunk 0 data):
```
Byte 0: Image ID (0-255)
Byte 1: Format (4 bits) | Resolution (4 bits)
  - Format: 1=JPEG, 2=RGB565
  - Resolution: 1=480x480, 2=240x240
Bytes 2-3: Delay time (uint16, 0-65535 ms)
Bytes 4-6: Total image size (uint24, up to 16MB)
Byte 7: Number of chunks (includes embedded chunk 0)
Byte 8: Rotation (0-3)
Bytes 9+: Chunk 0 data (embedded in start message)
```

**ImageChunk Message** (7 bytes header + data):
```
Byte 0: Image ID
Byte 1: Chunk ID (starts from 1, chunk 0 is in ImageStart)
Bytes 2-4: Starting location in image (uint24)
Bytes 5-6: Chunk length (uint16)
Bytes 7+: Image data
```

**Timeout**: Images auto-expire if not fully received within `100ms × num_chunks`

**Chunking**:
- Chunk size calculated considering SPI buffer (8192 bytes) and DMA alignment (4 bytes)
- `calculate_effective_chunk_size()`: Returns ~8169 bytes for regular chunks
- `calculate_effective_chunk_size_for_image_start()`: Returns ~8166 bytes for embedded chunk 0

### Error Codes

Defined in `constants.py:ErrorCode`:

**General** (0x00-0x0F):
- `0x00`: SUCCESS
- `0x01`: UNKNOWN_MSG_TYPE
- `0x02`: INVALID_FORMAT
- `0x04`: IMAGE_ID_MISMATCH
- `0x15`: SCREEN_ID_MISMATCH (CAN-bus filtering)

**Header Errors** (0x10-0x1F):
- `0x10`: HEADER_TOO_SHORT
- `0x11`: INVALID_SOF_MARKER
- `0x12`: INVALID_MESSAGE_TYPE

**Text Errors** (0x20-0x2F):
- `0x20`: TEXT_PAYLOAD_TOO_SHORT
- `0x21`: TEXT_TOO_MANY_ITEMS
- `0x22`: TEXT_INVALID_ROTATION

**Image Errors** (0x30-0x4F):
- `0x30`: IMAGE_START_TOO_SHORT
- `0x40`: IMAGE_CHUNK_TOO_SHORT

### DMA Alignment Requirements

All SPI messages must be padded to 4-byte boundaries for DMA compatibility:

```python
def pad_to_alignment(data: bytearray, alignment: int = 4) -> bytearray:
    padding_needed = (alignment - (len(data) % alignment)) % alignment
    if padding_needed > 0:
        data.extend(b'\x00' * padding_needed)
    return data
```

**Implementation**: Every protocol message's `encode()` method calls `pad_to_alignment()`

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

### Custom Message Definitions

Located in `DiceMaster_Central/dicemaster_central_msgs/`:

**ScreenMediaCmd.msg**:
```
int32 screen_id     # Target screen (1-6)
int32 media_type    # ContentType enum (0=TEXT, 1=IMAGE, 2=GIF)
string file_path    # Absolute path to asset file
```

**ChassisOrientation.msg**:
```
uint8 top_screen_id                    # Screen facing up (1-6)
uint8 bottom_screen_id                 # Screen facing down (1-6)
builtin_interfaces/Time stamp          # Timestamp
```

**ScreenPose.msg**:
```
uint8 screen_id                        # Screen ID (1-6)
uint8 rotation                         # Rotation (0=0°, 1=90°, 2=180°, 3=270°)
float32 up_alignment                   # -1.0 to 1.0 (1.0 = facing up)
bool is_facing_up                      # Is primary "up" screen
builtin_interfaces/Time stamp          # Timestamp
```

**MotionDetection.msg**:
```
std_msgs/Header header                 # Timestamp and frame
bool rotation_x_positive               # Rotation detections (6 axes)
bool rotation_x_negative
... (other rotation axes)
bool shaking                           # Shake detected
float64 rotation_intensity             # 0.0-1.0
float64 shake_intensity                # 0.0-1.0
float64 stillness_factor               # 1.0 = perfectly still
```

**DiceGameControl.srv**:
```
# Request
string command       # "start", "stop", "list"
string game_name     # For start command

---
# Response
bool success
string message
string[] available_games
string current_game
```

### Node Details

#### IMU Hardware Node

**File**: `dicemaster_central/hw/imu/imu_hardware.py`

**Function**: Interfaces with MPU6050 IMU via I2C

**Configuration** (from `dice_config.imu_config`):
- `i2c_bus`: 6 (default)
- `i2c_address`: 0x68
- `calibration_duration`: 5.0 seconds
- `polling_rate`: 50 Hz

**Calibration**:
- Stores bias in `~/.dicemaster/imu_calibration.json`
- Service: `/imu/calibrate` (std_srvs/Empty)
- Auto-loads calibration on startup if available

**Scaling**:
- Accelerometer: ±2g range (scale factor 16384.0)
- Gyroscope: ±250°/s range (scale factor 131.0)

**Output**: `/imu/data_raw` (sensor_msgs/Imu) at 50 Hz

#### Motion Detector Node

**File**: `dicemaster_central/hw/imu/motion_detector.py`

**Function**: Detects shake patterns from filtered IMU data

**Algorithm**:
- Maintains 50-sample rolling history of acceleration and gyro magnitudes
- Shake detection: High variance in acceleration OR sustained gyro velocity
- Thresholds:
  - `shake_accel_threshold`: 13.0 m/s² (above gravity)
  - `shake_gyro_threshold`: 5.0 rad/s
  - `shake_variance_threshold`: 5.0

**Input**: `/imu/data` (filtered)

**Output**: `/imu/motion` (MotionDetection) at filter rate

#### Chassis Node

**File**: `dicemaster_central/hw/chassis.py`

**Function**: Determines screen orientation from IMU and publishes TF transforms

**Key Features**:
- Publishes TF tree: `world` → `base_link` → 6 `screen_{id}_link` frames
- Detects top/bottom screens by comparing screen Z-axis with gravity vector
- Calculates rotation for each screen based on gravity direction
- Hysteresis to prevent oscillation during transitions

**Outputs**:
- TF transforms (tf2_ros)
- `/chassis/orientation` (ChassisOrientation) - Top/bottom IDs
- `/chassis/screen_{1-6}_pose` (ScreenPose) - Individual rotations

**Screen Color Mapping** (from URDF):
```python
SCREEN_COLORS = {
    1: "Red", 2: "Green", 3: "Blue",
    4: "Yellow", 5: "Magenta", 6: "Cyan"
}
```

#### Screen Bus Manager Node

**File**: `dicemaster_central/hw/screen/screen_bus_manager.py` (242 lines)

**Function**: Manages SPI communication for screens on a single bus

**Architecture**:
- One instance per SPI bus (3 buses: 0, 1, 3)
- Each bus manages 2 screens with different chip select (CS) pins
- Multi-threaded: Main ROS thread + transmission worker thread

**Components**:

1. **Message Queue** (PriorityQueue):
   - Queued messages sorted by priority then timestamp
   - Priority levels (MessagePriority enum):
     - CRITICAL = 1 (ping, errors)
     - HIGH = 2 (text, single images)
     - NORMAL = 5 (GIF frames)
     - LOW = 8 (background tasks)

2. **Screen Objects** (Screen class):
   - One per screen on the bus
   - Handles media processing in separate thread
   - Manages GIF playback with timers
   - Subscribes to `/chassis/screen_{id}_pose` for rotation updates
   - Re-sends content when rotation changes

3. **SPI Device** (SPIDevice class):
   - Wraps `spidev` library
   - Configuration:
     - `max_speed_hz`: 9600000 (9.6 MHz)
     - `mode`: 0
     - `bits_per_word`: 8
     - `max_buffer_size`: 8192 bytes

**Media Processing Pipeline**:

```
ScreenMediaCmd → Screen.queue_media_request()
    ↓
Screen._processing_worker() (thread)
    ↓
Load asset file (JSON/JPG/GIF.d)
    ↓
Convert to Media object (TextGroup/Image/GIF)
    ↓
Generate protocol messages (TextBatchMessage/ImageStartMessage/ImageChunkMessage)
    ↓
Screen.push_to_bus_manager()
    ↓
ScreenBusManager.queue_protocol_message()
    ↓
PriorityQueue
    ↓
ScreenBusManager._transmission_worker() (thread)
    ↓
Encode to bytes with DMA padding
    ↓
SPIDevice.xfer() → ESP32
```

**GIF Playback**:
- GIF directory format: `animation.gif.d/0.jpg, 1.jpg, 2.jpg, ...`
- Each frame pre-encoded as protocol messages
- ROS timer cycles through frames at configured rate
- Default: 100ms per frame (from `constants.py:GIF_FRAME_TIME`)

#### Game Manager Node

**File**: `dicemaster_central/managers/game_manager.py`

**Function**: Discovers and manages game/strategy lifecycle

**Discovery Process**:

1. **Strategy Discovery** (`_discover_strategies()`):
   - Scans `default_strategy_locations` from config
   - For each directory: looks for `{name}/{name}.py`
   - Uses `load_strategy()` to dynamically import
   - Verifies class inherits from `BaseStrategy`
   - Stores in `self.strategies` dict

2. **Game Discovery** (`_discover_games()`):
   - Scans `default_game_locations` from config
   - For each directory: looks for `config.json` and `assets/`
   - Parses config, verifies referenced strategy exists
   - Creates `DiceGame` objects
   - Stores in `self.games` dict

**Lifecycle Management**:

**Start Game**:
```python
def start_game(self, game_name: str):
    game = self.games[game_name]
    strategy_class = self.strategies[game.strategy_name]

    # Instantiate strategy node with game parameters
    strategy_node = strategy_class(
        game_name=game.game_name,
        config_file=game.config_path,
        assets_path=game.assets_path,
        **game.strategy_node_kwargs
    )

    # Add to executor (MultiThreadedExecutor)
    self.executor.add_node(strategy_node)

    # Store reference
    self.current_strategy_node = strategy_node
    self.current_game_name = game_name
```

**Stop Game**:
```python
def stop_game(self):
    if self.current_strategy_node:
        # Call strategy's cleanup
        self.current_strategy_node.stop_strategy()

        # Remove from executor
        self.executor.remove_node(self.current_strategy_node)

        # Destroy node
        self.current_strategy_node.destroy_node()
        self.current_strategy_node = None
```

**Service Interface** (`/game_control`):
- Commands: `"start"`, `"stop"`, `"list"`
- Handler: `handle_game_control()` callback

**Auto-Launch**:
- If `dice_config.game_config.default_game` is set, auto-starts 1 second after initialization
- Uses deferred timer to avoid executor deadlock

---

## Launch System

### Launch File Hierarchy

**Main Entry**: `dicemaster.launch.py`

Includes (in order):
1. `imu.launch.py` - IMU hardware, filter, motion detection
2. `chassis.launch.py` - Chassis node for orientation
3. `screens.launch.py` - Screen bus managers (dynamic based on config)
4. `managers.launch.py` - Game manager

### Launch File Details

#### dicemaster.launch.py

**Type**: Composite launch file

**Function**: Includes all subsystem launch files

**Structure**:
```python
def generate_launch_description():
    return LaunchDescription([
        IncludeLaunchDescription(imu.launch.py),
        IncludeLaunchDescription(chassis.launch.py),
        IncludeLaunchDescription(screens.launch.py),
        IncludeLaunchDescription(managers.launch.py),
    ])
```

**Usage**:
```bash
ros2 launch dicemaster_central dicemaster.launch.py
```

#### imu.launch.py

**Nodes**:
1. `imu_hardware` (dicemaster_central)
2. `imu_filter_madgwick` (imu_filter_madgwick package)
3. `motion_detector` (dicemaster_central)

**Parameters** (for Madgwick filter):
- `use_mag`: false (no magnetometer)
- `gain`: 0.1 (filter convergence rate)
- `world_frame`: 'enu' (East-North-Up)
- `publish_tf`: true
- `stateless`: false (maintains state)

#### screens.launch.py

**Dynamic Launch**: Reads `dice_config.active_spi_controllers` and spawns nodes

**Example** (3 buses):
```python
active_buses = [0, 1, 3]
for bus_id in active_buses:
    nodes.append(Node(
        package='dicemaster_central',
        executable='screen_bus_manager.py',
        name=f'screen_bus_manager_{bus_id}',
        arguments=[str(bus_id)],
    ))
```

**Mapping** (from `dice_config.screen_configs`):
- Bus 0: Screens 1, 6
- Bus 1: Screens 3, 5
- Bus 3: Screens 2, 4

#### managers.launch.py

**Nodes**:
1. `game_manager` (dicemaster_central)

**Simple launcher** - no parameters needed (reads from `dice_config`)

### Auto-Start Configuration

For production deployment (auto-start on boot):

**Systemd Service** (follow `docs/auto_start.readme.md`):
```ini
[Unit]
Description=DiceMaster Service
After=network.target

[Service]
Type=simple
User=dice
WorkingDirectory=/home/dice/DiceMaster/DiceMaster_ROS_workspace
ExecStart=/bin/bash -c "source /home/dice/ros2_humble/install/setup.bash && source install/setup.bash && ros2 launch dicemaster_central dicemaster.launch.py"
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

---

## Configuration System

### Primary Configuration File

**Location**: `dicemaster_central/dicemaster_central/config.py`

### Configuration Classes

#### DiceConfig (Main Config)

**SPI Configuration** (`SPIConfig`):
```python
@dataclass
class SPIConfig:
    max_speed_hz: int = 9600000      # 9.6 MHz
    mode: int = 0                     # SPI mode 0
    bits_per_word: int = 8
    max_buffer_size: int = 8192       # 8KB chunks
    num_devices_per_bus: int = 2
```

**SPI Bus Configuration** (`SPIBusConfig`):
```python
bus_configs: Dict[int, SPIBusConfig] = {
    0: SPIBusConfig(bus_id=0),
    1: SPIBusConfig(bus_id=1),
    3: SPIBusConfig(bus_id=3)
}
```
- `bus_id`: Linux SPI bus number (`/dev/spidev{bus_id}.{dev}`)
- `use_dev`: Chip select (CS) device number (default 0)

**Screen Configuration** (`ScreenConfig`):
```python
screen_configs: Dict[int, ScreenConfig] = {
    1: ScreenConfig(id=1, bus_id=0, default_orientation=Rotation(0), description="Screen 1"),
    2: ScreenConfig(id=2, bus_id=3, default_orientation=Rotation(3), description="Screen 2"),
    # ... screens 3-6
}
```
- `id`: Screen ID (1-6)
- `bus_id`: Which SPI bus this screen is on
- `default_orientation`: Physical mounting orientation offset
- `description`: Human-readable label

**IMU Configuration** (`IMUConfig`):
```python
@dataclass
class IMUConfig:
    i2c_bus = 6                       # I2C bus number
    i2c_address: int = 0x68           # MPU6050 address
    calibration_duration: float = 5.0 # Calibration time
    polling_rate: int = 50            # Hz
```

#### GameConfig

**Game & Strategy Locations**:
```python
class GameConfig:
    default_game_locations = [
        os.path.expanduser("~/.dicemaster/games"),
        os.path.join(EXAMPLE_DIR, "games")
    ]
    default_strategy_locations = [
        os.path.expanduser("~/.dicemaster/strategies"),
        os.path.join(EXAMPLE_DIR, "strategies")
    ]
    default_game = "chinese_quizlet"
```

**Discovery Order**: User directory (`~/.dicemaster/`) checked first, then examples

### Constants (constants.py)

All enums and protocol constants are defined here:

**Key Constants**:
- `ContentTypeExts`: File extension mappings for asset validation
  ```python
  ContentTypeExts = {
      ContentType.TEXT: ['json'],
      ContentType.IMAGE: ['jpg', 'jpeg', 'png'],
      ContentType.GIF: []  # Directories with .gif.d extension
  }
  ```
- `MAX_TEXT_NUM_BYTES`: 255 (max text length per item)
- `GIF_FRAME_TIME`: 100 (ms per frame)

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

## Hardware Interfaces

### SPI Interface

**Physical Connection**:
- 3 SPI buses: 0, 1, 3
- Each bus has 2 chip select (CS) pins
- Total: 6 screens (2 per bus)

**Linux Device Paths**:
- Bus 0: `/dev/spidev0.0`, `/dev/spidev0.1`
- Bus 1: `/dev/spidev1.0`, `/dev/spidev1.1`
- Bus 3: `/dev/spidev3.0`, `/dev/spidev3.1`

**Enable SPI**:
```bash
sudo raspi-config
# Interface Options → SPI → Enable
```

**Custom py-spidev**:
- Standard py-spidev has 4KB buffer limit
- Custom build needed for 8KB buffer (for JPEG chunks)
- Source: https://github.com/doceme/py-spidev
- Installation:
  ```bash
  git clone https://github.com/doceme/py-spidev.git
  cd py-spidev
  # Edit spidev_module.c: SPIDEV_MAXPATH to 8192
  pip install -e . --break-system-packages
  ```

**SPI Device Wrapper** (`spi_device.py`):
```python
class SPIDevice:
    def __init__(self, bus_id, bus_dev_id, spi_config, verbose=False):
        self.spi = spidev.SpiDev()
        self.spi.open(bus_id, bus_dev_id)
        self.spi.max_speed_hz = spi_config.max_speed_hz
        self.spi.mode = spi_config.mode
        self.spi.bits_per_word = spi_config.bits_per_word

    def xfer(self, data: bytes) -> bytes:
        """Transfer data via SPI"""
        return bytes(self.spi.xfer2(list(data)))
```

### I2C Interface (IMU)

**Device**: MPU6050 6-axis IMU

**Physical Connection**:
- I2C Bus 6 (configurable in `dice_config.imu_config`)
- Address: 0x68

**Enable I2C**:
```bash
sudo raspi-config
# Interface Options → I2C → Enable
```

**Linux Device Path**: `/dev/i2c-6`

**Library**: `smbus2` (Python package)

**Configuration Registers** (in `imu_hardware.py`):
- `PWR_MGMT_1` (0x6B): Power management
- `GYRO_CONFIG` (0x1B): Gyroscope range (±250°/s)
- `ACCEL_CONFIG` (0x1C): Accelerometer range (±2g)
- `ACCEL_XOUT_H` (0x3B): Start of data registers

**Data Registers** (14 bytes total):
```
0x3B-0x3C: Accel X (int16)
0x3D-0x3E: Accel Y
0x3F-0x40: Accel Z
0x41-0x42: Temperature
0x43-0x44: Gyro X (int16)
0x45-0x46: Gyro Y
0x47-0x48: Gyro Z
```

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

## Protocol Implementation

### Media Type Processing

#### Text Processing

**Input**: JSON file (e.g., `greeting.json`)

**Format**:
```json
{
    "bg_color": "0x0000",
    "texts": [
        {
            "x_cursor": 100,
            "y_cursor": 200,
            "font_name": "tf",
            "font_color": "0xFFFF",
            "text": "Hello World"
        }
    ]
}
```

**Processing** (in `media_types.py:TextGroup`):

1. **Validation** (Pydantic):
   - Verify RGB565 hex format for colors
   - Validate cursor positions (0-479)
   - Map font names to IDs using `FONT_NAME_TO_ID`
   - Check text length (max 255 bytes UTF-8)

2. **Conversion**:
   ```python
   text_entry = TextEntry(
       x_cursor=100,
       y_cursor=200,
       font_id=FontID.TF,  # 1
       font_color=0xFFFF,
       text="Hello World"
   )
   ```

3. **Protocol Message Generation** (`to_msg()`):
   ```python
   message = TextBatchMessage(
       screen_id=screen_id,
       bg_color=0x0000,
       rotation=Rotation.ROTATION_0,
       text_entries=[text_entry]
   )
   ```

4. **Encoding** (`TextBatchMessage.encode()`):
   ```python
   payload = bytearray()
   # Header
   payload.extend(struct.pack('>H', self.bg_color))  # 2 bytes
   payload.append(len(self.text_entries))             # 1 byte
   payload.append(self.rotation)                      # 1 byte
   payload.extend(b'\x00\x00')                        # 2 bytes reserved

   # Encode each text entry
   for entry in self.text_entries:
       payload.extend(encode_text_entry(entry))

   # Create full message with header
   return self._create_message(payload)  # Adds 5-byte header + padding
   ```

#### Image Processing

**Input**: JPEG file (e.g., `cat_1.jpg`)

**Processing** (in `media_types.py:Image`):

1. **Load Image**:
   ```python
   with open(file_path, 'rb') as f:
       image_data = f.read()
   ```

2. **Calculate Chunks**:
   ```python
   chunk_size_start = calculate_effective_chunk_size_for_image_start(8192)  # ~8166
   chunk_size_regular = calculate_effective_chunk_size(8192)  # ~8169

   total_size = len(image_data)
   num_chunks = calculate_num_chunks(total_size, chunk_size_start, chunk_size_regular)
   ```

3. **Generate Messages**:

   **ImageStart** (includes chunk 0):
   ```python
   chunk_0_data = image_data[:chunk_size_start]

   message = ImageStartMessage(
       screen_id=screen_id,
       image_id=0,  # Auto-assigned
       format=ImageFormat.JPEG,
       resolution=ImageResolution.SQ480,
       delay_time=0,
       total_size=total_size,
       num_chunks=num_chunks,
       rotation=Rotation.ROTATION_0,
       chunk_0_data=chunk_0_data
   )
   ```

   **ImageChunk** (chunks 1+):
   ```python
   for chunk_id in range(1, num_chunks):
       start = chunk_size_start + (chunk_id - 1) * chunk_size_regular
       end = start + chunk_size_regular
       chunk_data = image_data[start:end]

       message = ImageChunkMessage(
           screen_id=screen_id,
           image_id=0,
           chunk_id=chunk_id,
           start_location=start,
           chunk_data=chunk_data
       )
   ```

4. **Transmission**:
   - All messages queued with priority HIGH
   - Sent sequentially via SPI
   - ESP32 reassembles based on chunk IDs
   - Timeout: 100ms × num_chunks (auto-invalidate if incomplete)

#### GIF Processing

**Input**: GIF directory (e.g., `animation.gif.d/`)

**Structure**:
```
animation.gif.d/
├── 0.jpg
├── 1.jpg
├── 2.jpg
└── 3.jpg
```

**Processing** (in `media_types.py:GIF`):

1. **Load Frames**:
   ```python
   frame_files = sorted([f for f in os.listdir(gif_dir) if f.endswith('.jpg')])
   frames = []
   for frame_file in frame_files:
       with open(os.path.join(gif_dir, frame_file), 'rb') as f:
           frames.append(f.read())
   ```

2. **Generate Frame Messages**:
   ```python
   all_frame_messages = []
   for frame_id, frame_data in enumerate(frames):
       # Each frame becomes a list of messages (ImageStart + ImageChunks)
       frame_messages = generate_image_messages(
           screen_id,
           frame_data,
           image_id=frame_id,
           delay_time=GIF_FRAME_TIME  # 100ms
       )
       all_frame_messages.append(frame_messages)
   ```

3. **Playback** (in `screen.py`):
   ```python
   def _gif_timer_callback(self):
       """Timer callback to cycle through GIF frames"""
       with self.gif_lock:
           # Get current frame's messages
           frame_messages = self.gif_messages[self.gif_frame_index]

           # Send to bus manager
           self.push_to_bus_manager(frame_messages, priority=MessagePriority.NORMAL)

           # Advance to next frame
           self.gif_frame_index = (self.gif_frame_index + 1) % len(self.gif_messages)
   ```

4. **Timer Management**:
   ```python
   # Start GIF playback
   self.gif_timer = self.node.create_timer(
       GIF_FRAME_TIME / 1000.0,  # Convert ms to seconds
       self._gif_timer_callback
   )

   # Stop GIF playback
   if self.gif_timer:
       self.destroy_timer(self.gif_timer)
       self.gif_timer = None
   ```

### Thread Safety

**Screen Bus Manager**:
- **Main Thread**: ROS callbacks (subscriptions)
- **Transmission Thread**: SPI communication worker
- **Synchronization**: PriorityQueue (thread-safe by default)

**Screen Object**:
- **Main Thread**: ROS callbacks (pose updates)
- **Processing Thread**: Media processing worker
- **GIF Timer Thread**: Frame cycling
- **Synchronization**:
  - `Queue` for media requests (thread-safe)
  - `threading.Lock` for GIF state (`gif_lock`)

**Best Practices**:
- Never call `self.spi.xfer()` from ROS callback (blocks)
- Use queues to pass data between threads
- Lock shared state (GIF playback variables)

---

## Testing & Debugging

### Unit Tests

**Location**: `DiceMaster_Central/dicemaster_central/tests/`

**Running Tests**:
```bash
cd DiceMaster_Central/dicemaster_central
python3 -m pytest tests/ -v
```

**Test Files**:

**test_protocol.py** (16662 lines - comprehensive):
- Protocol encoding/decoding
- Message validation
- Error handling
- DMA alignment verification

**test_screen.py**:
- Screen media command publishing
- Test publisher for manual screen testing

**test_spi2.py**:
- SPI device communication
- Hardware interface verification

**test_remote_logger.py**:
- Remote logging functionality

### Manual Testing

#### Test IMU Pipeline

**Monitor raw IMU data**:
```bash
ros2 topic echo /imu/data_raw
```

**Monitor filtered data**:
```bash
ros2 topic echo /imu/data
```

**Monitor motion detection**:
```bash
ros2 topic echo /imu/motion
```

**Trigger calibration**:
```bash
ros2 service call /imu/calibrate std_srvs/srv/Empty
```

#### Test Chassis Orientation

**Monitor orientation**:
```bash
ros2 topic echo /chassis/orientation
```

**Monitor individual screen pose**:
```bash
ros2 topic echo /chassis/screen_1_pose
```

**View TF tree**:
```bash
ros2 run tf2_tools view_frames
# Generates frames.pdf
```

#### Test Screen Display

**Send test text to screen 1**:
```bash
ros2 topic pub /screen_1_cmd dicemaster_central_msgs/msg/ScreenMediaCmd "{screen_id: 1, media_type: 0, file_path: '/full/path/to/greeting.json'}" --once
```

**Send test image**:
```bash
ros2 topic pub /screen_1_cmd dicemaster_central_msgs/msg/ScreenMediaCmd "{screen_id: 1, media_type: 1, file_path: '/full/path/to/image.jpg'}" --once
```

**Test with pipeline_test strategy**:
- Cycles through all screens with notifications
- Good for verifying all screens work
```bash
# Set default_game = "test" in config.py
ros2 launch dicemaster_central dicemaster.launch.py
```

#### Test Game Manager

**List available games**:
```bash
ros2 service call /game_control dicemaster_central_msgs/srv/DiceGameControl "{command: 'list', game_name: ''}"
```

**Start specific game**:
```bash
ros2 service call /game_control dicemaster_central_msgs/srv/DiceGameControl "{command: 'start', game_name: 'hello_dice'}"
```

**Stop current game**:
```bash
ros2 service call /game_control dicemaster_central_msgs/srv/DiceGameControl "{command: 'stop', game_name: ''}"
```

### Debugging Tools

#### ROS2 Introspection

**List all nodes**:
```bash
ros2 node list
```

**List all topics**:
```bash
ros2 topic list
```

**Node info**:
```bash
ros2 node info /game_manager
```

**Topic info**:
```bash
ros2 topic info /screen_1_cmd
```

**Topic bandwidth**:
```bash
ros2 topic bw /imu/data
```

**Topic rate**:
```bash
ros2 topic hz /imu/data
```

#### Logging

**View all logs**:
```bash
ros2 topic echo /rosout
```

**Filter by node**:
```bash
ros2 topic echo /rosout | grep "game_manager"
```

**Log levels** (in Python nodes):
```python
self.get_logger().debug("Debug message")
self.get_logger().info("Info message")
self.get_logger().warn("Warning message")
self.get_logger().error("Error message")
self.get_logger().fatal("Fatal message")
```

**Set log level at runtime**:
```bash
ros2 run rqt_logger_level rqt_logger_level
```

#### Common Issues & Solutions

**Issue**: Screen not updating
- **Check**: Topic activity: `ros2 topic hz /screen_1_cmd`
- **Check**: Screen bus manager logs for errors
- **Check**: File path is absolute and exists
- **Check**: SPI bus is enabled and accessible

**Issue**: IMU data not publishing
- **Check**: I2C bus enabled: `ls /dev/i2c-*`
- **Check**: IMU address detected: `i2cdetect -y 6`
- **Check**: imu_hardware node running: `ros2 node list | grep imu`
- **Check**: Calibration loaded (look for warning in logs)

**Issue**: Motion detection not working
- **Check**: motion_detector subscribed to correct topic
- **Check**: `/imu/data` has orientation data (not just raw)
- **Check**: Shake thresholds in `motion_detector.py` (may need tuning)

**Issue**: Game not auto-starting
- **Check**: `default_game` in config.py matches actual game name
- **Check**: Game discovered: `ros2 service call /game_control ... command: 'list'`
- **Check**: Strategy file named correctly: `{name}/{name}.py`

**Issue**: SPI communication fails
- **Check**: Custom py-spidev installed: `pip show spidev`
- **Check**: Buffer size: Should be 8192, not 4096
- **Check**: SPI device permissions: `ls -l /dev/spidev*`
- **Fix**: Add user to `spi` group: `sudo usermod -a -G spi dice`

---

## Deployment

### Production Setup

#### Raspberry Pi Configuration

**1. Flash OS**:
- Raspbian OS 64-bit Lite (or Full for GUI)
- Username: `dice` (required for auto-start scripts)
- Enable SSH in pi-imager

**2. Initial Setup**:
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y git python3-pip

# Enable SPI and I2C
sudo raspi-config
# Interface Options → Enable SPI
# Interface Options → Enable I2C
```

**3. Install ROS2 Humble**:
- Build from source (Debian is tier-3 support)
- Install to `/home/dice/ros2_humble`
- Follow: https://docs.ros.org/en/humble/Installation/Alternatives/Ubuntu-Development-Setup.html

**4. Add to .bashrc**:
```bash
echo 'source /home/dice/ros2_humble/install/setup.bash' >> ~/.bashrc
```

**5. Clone Repository**:
```bash
cd ~
git clone git@github.com:ShapiroDesignLab/DiceMaster.git --recursive
```

**6. Build Workspace**:
```bash
cd DiceMaster/DiceMaster_ROS_workspace
mkdir -p src
ln -s ../../DiceMaster_Central src/dicemaster_central
ln -s ../../DiceMaster_Central/dicemaster_central_msgs src/dicemaster_central_msgs

# Source ROS
source /home/dice/ros2_humble/install/setup.bash

# Build
colcon build --symlink-install
```

**7. Install Custom py-spidev**:
```bash
git clone https://github.com/doceme/py-spidev.git
cd py-spidev
# Edit spidev_module.c line 22: #define SPIDEV_MAXPATH 8192
pip install -e . --break-system-packages
```

**8. Install Python Dependencies**:
```bash
cd ~/DiceMaster/DiceMaster_Central/dicemaster_central
pip install -r requirements.txt --break-system-packages
```

#### Auto-Start with Systemd

**Create service file**: `/etc/systemd/system/dicemaster.service`
```ini
[Unit]
Description=DiceMaster Dice System
After=network.target

[Service]
Type=simple
User=dice
WorkingDirectory=/home/dice/DiceMaster/DiceMaster_ROS_workspace
ExecStart=/bin/bash -c "source /home/dice/ros2_humble/install/setup.bash && source install/setup.bash && ros2 launch dicemaster_central dicemaster.launch.py"
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Enable service**:
```bash
sudo systemctl daemon-reload
sudo systemctl enable dicemaster.service
sudo systemctl start dicemaster.service
```

**Check status**:
```bash
sudo systemctl status dicemaster.service
```

**View logs**:
```bash
sudo journalctl -u dicemaster.service -f
```

### Development Workflow

#### Making Changes

**Edit Python code**:
- Changes to `dicemaster_central/dicemaster_central/*.py` take effect immediately (symlink install)
- No rebuild needed for Python files

**Edit config**:
- Edit `config.py`
- Rebuild: `colcon build --symlink-install`
- Restart launch

**Edit launch files**:
- Changes to `*.launch.py` take effect immediately
- No rebuild needed

**Edit messages**:
- Edit `*.msg` or `*.srv` files
- Rebuild: `colcon build`
- Restart all nodes

#### Adding New Games

**User deployment** (no rebuild needed):
```bash
mkdir -p ~/.dicemaster/games/my_game/assets
mkdir -p ~/.dicemaster/strategies/my_strategy

# Create files
nano ~/.dicemaster/games/my_game/config.json
nano ~/.dicemaster/strategies/my_strategy/my_strategy.py

# Restart to discover
ros2 service call /game_control ... command: 'list'
```

**Example deployment**:
```bash
cp -r DiceMaster_Central/dicemaster_central/examples/games/hello_dice ~/.dicemaster/games/
cp -r DiceMaster_Central/dicemaster_central/examples/strategies/hello_strategy ~/.dicemaster/strategies/
```

#### Version Control

**Submodule structure**:
- Main repo: DiceMaster (meta-repo)
- Submodules: DiceMaster_Central, DiceMaster_ESPScreen, DiceMaster_ROS_workspace

**Update submodules**:
```bash
cd DiceMaster
git submodule update --remote --merge
```

**Commit changes**:
```bash
# In submodule
cd DiceMaster_Central
git add .
git commit -m "Add new feature"
git push

# In main repo
cd ..
git add DiceMaster_Central
git commit -m "Update DiceMaster_Central submodule"
git push
```

### Troubleshooting Production

**System won't boot**:
- Check journalctl: `sudo journalctl -xe`
- Disable auto-start: `sudo systemctl disable dicemaster.service`
- Debug manually: `ros2 launch dicemaster_central dicemaster.launch.py`

**High CPU usage**:
- Check node CPU: `top` and look for ROS processes
- Reduce IMU polling rate in config
- Reduce GIF frame rate

**Memory issues**:
- Check memory: `free -h`
- Reduce number of simultaneous GIF playbacks
- Lower image resolution (240x240 instead of 480x480)

**SPI errors**:
- Check dmesg: `dmesg | grep spi`
- Verify custom py-spidev: `python3 -c "import spidev; print(spidev.__file__)"`
- Reduce SPI speed: Edit `max_speed_hz` in config.py

---

## Additional Resources

### Code References

**Protocol Implementation**:
- `dicemaster_central/media_typing/protocol.py`: Low-level protocol encoding
- `dicemaster_central/media_typing/media_types.py`: High-level media objects
- `docs/protocol.md`: Protocol specification

**Hardware Interfaces**:
- `dicemaster_central/hw/screen/spi_device.py`: SPI wrapper
- `dicemaster_central/hw/imu/imu_hardware.py`: IMU interface
- `dicemaster_central/hw/chassis.py`: Orientation detection

**Game System**:
- `dicemaster_central/games/strategy.py`: BaseStrategy class
- `dicemaster_central/games/game.py`: Game loading
- `dicemaster_central/managers/game_manager.py`: Game lifecycle

### External Dependencies

**ROS2 Packages**:
- `imu_filter_madgwick`: IMU orientation filter
- `tf2_ros`: Transform library
- `sensor_msgs`: Standard sensor messages

**Python Packages**:
- `spidev`: SPI interface (custom build)
- `smbus2`: I2C interface
- `pydantic`: Data validation
- `Pillow`: Image processing
- `numpy`: Numerical operations

### Documentation Files

- `CLAUDE.md`: Quick reference for development
- `docs/beginner_game_guide.md`: Game creation tutorial
- `docs/protocol.md`: SPI protocol specification
- `docs/hardware.md`: Hardware assembly
- `docs/software.md`: Software installation
- `DiceMaster_Central/dicemaster_central/docs/architecture.md`: Architecture overview
- `DiceMaster_Central/dicemaster_central/launch/README.md`: Launch system

---

## Appendix: File Structure

```
DiceMaster/
├── DiceMaster_Central/                      (Submodule)
│   ├── dicemaster_central/                  (ROS2 Package)
│   │   ├── dicemaster_central/              (Python Package)
│   │   │   ├── config.py                    (Configuration)
│   │   │   ├── constants.py                 (Enums and constants)
│   │   │   ├── games/                       (Game system)
│   │   │   │   ├── game.py                  (Game loading)
│   │   │   │   └── strategy.py              (BaseStrategy)
│   │   │   ├── hw/                          (Hardware interfaces)
│   │   │   │   ├── screen/
│   │   │   │   │   ├── screen_bus_manager.py
│   │   │   │   │   ├── screen.py
│   │   │   │   │   └── spi_device.py
│   │   │   │   ├── imu/
│   │   │   │   │   ├── imu_hardware.py
│   │   │   │   │   └── motion_detector.py
│   │   │   │   └── chassis.py
│   │   │   ├── managers/                    (System managers)
│   │   │   │   └── game_manager.py
│   │   │   ├── media_typing/                (Protocol implementation)
│   │   │   │   ├── media_types.py
│   │   │   │   └── protocol.py
│   │   │   └── utils/                       (Utilities)
│   │   │       ├── data_loader.py
│   │   │       └── notification_builder.py
│   │   ├── launch/                          (Launch files)
│   │   │   ├── dicemaster.launch.py
│   │   │   ├── imu.launch.py
│   │   │   ├── chassis.launch.py
│   │   │   ├── screens.launch.py
│   │   │   └── managers.launch.py
│   │   ├── examples/                        (Example games)
│   │   │   ├── games/
│   │   │   │   ├── chinese_quizlet/
│   │   │   │   └── test/
│   │   │   └── strategies/
│   │   │       ├── shake_quizlet/
│   │   │       └── pipeline_test/
│   │   ├── tests/                           (Unit tests)
│   │   ├── package.xml                      (ROS2 package manifest)
│   │   └── setup.py                         (Python package setup)
│   └── dicemaster_central_msgs/             (Custom messages)
│       ├── msg/
│       │   ├── ScreenMediaCmd.msg
│       │   ├── ChassisOrientation.msg
│       │   ├── ScreenPose.msg
│       │   └── MotionDetection.msg
│       └── srv/
│           └── DiceGameControl.srv
├── DiceMaster_ESPScreen/                    (Submodule - ESP32 firmware)
├── DiceMaster_ROS_workspace/                (Submodule - ROS workspace)
└── docs/                                    (Documentation)
    ├── protocol.md
    ├── hardware.md
    ├── software.md
    ├── beginner_game_guide.md
    └── developer_guide.md (this file)
```

---

**Document Version**: 1.0
**Last Updated**: 2025
**Maintainer**: DiceMaster Team, U-M Shapiro Design Lab