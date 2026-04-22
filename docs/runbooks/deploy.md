# Runbook: Deploy to Raspberry Pi (dice1)

## Prerequisites

- SSH access to `dice1` configured in `~/.ssh/config`
- The Pi has ROS2 Humble built at `~/ros2_humble/` and sourced in `~/.bashrc`
- The workspace at `~/DiceMaster/DiceMaster_Central/` was previously built with `--symlink-install`
- The `dicemaster` systemd service is present if auto-start is configured (see `docs/setup/auto_start.md`)

## Steps

### 1. Commit and push your changes locally

```bash
# From /Users/danielhou/Code/DiceMaster/DiceMaster_Central (or the submodule root)
git add <changed files>
git commit -m "your message"
git push
```

### 2. Pull the changes on the Pi

SSH to `dice1` and pull in the submodule directory:

```bash
ssh dice1 'cd ~/DiceMaster/DiceMaster_Central && git pull'
```

Because `--symlink-install` was used during the initial build, Python source files are symlinked into the install tree. The pull updates the source files directly, so no rebuild is needed for Python-only changes.

### 3. Determine whether a rebuild is required

A rebuild (`colcon build --symlink-install`) is only needed if any of the following changed:

| Changed file type | Rebuild required? |
|---|---|
| `*.py` (Python source, strategies, drivers) | No |
| `*.launch.py` (launch files) | No |
| `config.py` | No (symlinked); restart nodes to apply |
| `setup.py` or `package.xml` | Yes |
| `*.msg` or `*.srv` (message/service definitions in `dicemaster_central_msgs`) | Yes |
| C++ source in `dicemaster_cpp` | Yes |

If a rebuild is needed:

```bash
ssh dice1 'cd ~/DiceMaster/DiceMaster_Central && source ~/ros2_humble/install/setup.bash && colcon build --symlink-install'
```

### 4. Restart the running system

If DiceMaster is running under systemd:

```bash
ssh dice1 'sudo systemctl restart dicemaster'
```

Check that it came back up:

```bash
ssh dice1 'sudo systemctl status dicemaster'
```

If running manually in a terminal (no systemd), kill the existing launch and restart:

```bash
ssh dice1 'pkill -f dicemaster.launch.py'
# Then start a new session or use a persistent terminal (tmux/screen)
ssh dice1 'source ~/ros2_humble/install/setup.bash && source ~/DiceMaster/DiceMaster_Central/install/setup.bash && ros2 launch dicemaster_central dicemaster.launch.py'
```

### 5. Verify the system is running

Check that all expected nodes are alive:

```bash
ssh dice1 'source ~/ros2_humble/install/setup.bash && source ~/DiceMaster/DiceMaster_Central/install/setup.bash && ros2 node list'
```

Expected nodes (at minimum):

```
/dice_chassis_node
/game_manager
/imu_hardware
/motion_detector
/screen_bus_manager_0
/screen_bus_manager_1
/screen_bus_manager_3
```

Check active topics:

```bash
ssh dice1 'source ~/ros2_humble/install/setup.bash && source ~/DiceMaster/DiceMaster_Central/install/setup.bash && ros2 topic list'
```

## Verify

- `ros2 node list` shows all 7+ expected nodes
- `ros2 topic echo /imu/motion --once` returns a `MotionDetection` message
- `ros2 topic echo /chassis/orientation --once` returns a `ChassisOrientation` message
- The screens display content (or the default idle state)

## Troubleshooting

**Nodes are not appearing after restart**
Check systemd logs: `ssh dice1 'sudo journalctl -u dicemaster -n 50'`
Or check ROS2 launch output if running manually.

**`ros2: command not found` on the Pi**
The ROS2 environment is not sourced in the current shell. Add `source ~/ros2_humble/install/setup.bash` to `~/.bashrc`, or prefix commands with it explicitly.

**Message type mismatch errors after a `.msg` change**
A rebuild and full node restart is required. Old nodes may have stale message definitions in memory. Run `sudo systemctl restart dicemaster` after rebuilding.

**Screen bus manager node crashes on startup**
Usually indicates an SPI device permission issue or the SPI interface is not enabled. Verify with `ls /dev/spidev*` on the Pi and check `docs/setup/rpi_hw_config.md`.

**Strategy not loaded / default game not starting**
Check that `GameConfig.default_game` in `config.py` matches a directory name under `~/.dicemaster/games/` or `examples/games/`. Check `ros2 topic echo /game_control` or logs from the `game_manager` node.
