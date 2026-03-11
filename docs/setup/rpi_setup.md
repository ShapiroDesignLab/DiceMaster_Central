# Raspberry Pi Setup

## Flash & Configure OS

**1. Flash OS**:
- Raspbian OS 64-bit Lite (or Full for GUI)
- Username: `dice` (required for auto-start scripts)
- Enable SSH in pi-imager
- (Optional) Install ZeroTier for private VPN access

**2. Initial Setup**:
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y git python3-pip

# Enable SPI and I2C
sudo raspi-config
# Interface Options → Enable SPI
# Interface Options → Enable I2C
```

Configure SPI and I2C interfaces — see [docs/setup/rpi_hw_config.md](rpi_hw_config.md)

## Install ROS2 Humble

Since Debian is tier-3 supported, compile from source:
- Build from source to `/home/dice/ros2_humble`
- Follow: https://docs.ros.org/en/humble/Installation/Alternatives/Ubuntu-Development-Setup.html

Add to `.bashrc`:
```bash
echo 'source /home/dice/ros2_humble/install/setup.bash' >> ~/.bashrc
```

Source for current session:
```bash
source ~/ros2_humble/install/setup.bash
```

## Build DiceMaster

```bash
git clone git@github.com:ShapiroDesignLab/DiceMaster.git --recursive
cd DiceMaster/DiceMaster_Central
./scripts/setup_workspace.sh
```

This repo is a self-contained colcon workspace. Packages live in `src/`, build artifacts go to `build/`/`install/`/`log/` (gitignored).

Alternatively, set up the workspace manually:
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

## Install Custom py-spidev

Extended SPI buffer support for screen communication:
```bash
git clone https://github.com/doceme/py-spidev.git
cd py-spidev
# Edit spidev_module.c line 22: #define SPIDEV_MAXPATH 8192
pip install -e . --break-system-packages
```

## Install Python Dependencies

```bash
cd ~/DiceMaster/DiceMaster_Central/dicemaster_central
pip install -r requirements.txt --break-system-packages
```

## Configure Auto-Start

See [docs/setup/auto_start.md](auto_start.md) for systemd service setup.

## Launch System

### Node Order

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

### Rebuild Triggers

| Change Type | Action Required |
|---|---|
| Python code (`*.py`) | None — takes effect immediately (symlink install) |
| Config (`config.py`) | `colcon build --symlink-install`, then restart launch |
| Launch files (`*.launch.py`) | None — takes effect immediately |
| Messages (`*.msg` / `*.srv`) | `colcon build`, then restart all nodes |

## Version Control

**Submodule structure**:
- Main repo: DiceMaster (meta-repo)
- Submodules: DiceMaster_Central, DiceMaster_ESPScreen, DiceMaster_ROS_workspace

**Update submodules**:
```bash
cd DiceMaster
git submodule update --remote --merge
```
