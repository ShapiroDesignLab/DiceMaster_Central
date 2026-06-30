# Launch Files

This directory contains ROS2 launch files for `dicemaster_central`.

## Files

| File | Purpose |
|---|---|
| `dicemaster.launch.py` | Top-level entry point — includes all subsystem launch files in order |
| `imu.launch.py` | Starts IMU hardware node, Madgwick filter, and motion detector |
| `chassis.launch.py` | Starts chassis node (orientation math, game coordination) |
| `screens.launch.py` | Dynamically spawns one `screen_bus_manager` node per active SPI bus |
| `managers.launch.py` | Starts the game manager node |
| `remote_logger.launch.py` | Optional remote logging sink for development/debugging |

## Usage

```bash
# Source ROS2 and workspace overlay first
source ~/ros2_humble/install/setup.bash
source install/setup.bash

# Launch everything
ros2 launch dicemaster_central dicemaster.launch.py

# Or launch a subsystem individually
ros2 launch dicemaster_central imu.launch.py
```

## Notes

- This workspace's `colcon.defaults.json` applies `--symlink-install` automatically, so launch file edits take effect without rebuilding.
- Python node changes also take effect without rebuilding (symlink install).
- Message definition or `setup.py` changes require a full `colcon build`.
