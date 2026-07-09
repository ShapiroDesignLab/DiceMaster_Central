# Development Setup & Debugging

## Remote Development

The Raspberry Pi (`dice1`) is the only machine with the real IMU, SPI buses, and
screens. The normal loop is: **edit locally → push → pull on the Pi → test on the
Pi.** Because the workspace is built with `--symlink-install`, Python-only edits
need no rebuild — only `.msg`/`.srv`/`setup.py`/C++ changes do.

### Prerequisites

- SSH access to the Pi. Add a host alias to `~/.ssh/config` so `ssh dice1` works:

  ```
  Host dice1
      HostName <pi-address-or-zerotier-ip>
      User dice
  ```

- The Pi already has ROS2 Humble at `~/ros2_humble/` and the workspace cloned at
  `~/DiceMaster/` with submodules, previously built with `--symlink-install`.

### Everyday loop

```bash
# 1. Edit locally on macOS, then commit & push from the submodule
git add <files> && git commit -m "..." && git push

# 2. Pull on the Pi (per submodule you changed)
ssh dice1 'cd ~/DiceMaster/DiceMaster_Central && git pull'

# 3. Rebuild ONLY if a .msg/.srv/setup.py/C++ file changed (see table below)
ssh dice1 'cd ~/DiceMaster/DiceMaster_Central && \
  source ~/ros2_humble/install/setup.bash && colcon build --symlink-install'

# 4. Run tests on the Pi
ssh dice1 'cd ~/DiceMaster/DiceMaster_Central && python3 -m pytest src/dicemaster_central/tests/'

# 5. Restart the running system
ssh dice1 'sudo systemctl restart dicemaster'   # or relaunch manually — see docs/runbooks/deploy.md
```

For the full deploy/restart/verify procedure (systemd, expected node list,
troubleshooting) see `docs/runbooks/deploy.md`.

### Tips

- Run long-lived launches inside `tmux`/`screen` on the Pi so they survive the
  SSH session closing.
- VS Code Remote-SSH works against `dice1` if you want to edit and run in one
  place instead of the push/pull loop.
- Keep the local checkout as the source of truth; avoid editing directly on the
  Pi so history stays clean.

## Running Tests

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

## Manual Testing

### Test IMU Pipeline

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

### Test Chassis Orientation

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

### Test Screen Display

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

### Test Game Manager

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

## ROS2 Introspection

### ROS2 Introspection

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

### Logging

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

## Common Issues

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

## Development Workflow

### Making Changes

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

### Adding New Games

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

### Version Control

**Submodule structure**:
- Main repo: DiceMaster (meta-repo)
- Submodules: DiceMaster_Central, DiceMaster_ESPScreen, DiceMaster_ROS_workspace

**Update submodules**:
```bash
cd DiceMaster
git submodule update --remote --merge
```
