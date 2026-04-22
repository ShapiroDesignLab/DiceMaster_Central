# Runbook: Local Development Setup

## Prerequisites

- ROS2 Humble installed and sourced (`source ~/ros2_humble/install/setup.bash` or equivalent)
- Python 3.11
- `colcon` build tool (`pip install colcon-common-extensions`)
- `git` with submodule support

For screen communication, a patched `py-spidev` is required on the target hardware (Raspberry Pi only; not needed for running tests locally on macOS/Linux without hardware).

## Steps

### 1. Clone the repository with submodules

```bash
git clone git@github.com:ShapiroDesignLab/DiceMaster.git --recursive
cd DiceMaster/DiceMaster_Central
```

If you already cloned without `--recursive`:

```bash
git submodule update --init --recursive
```

### 2. Source ROS2

```bash
source ~/ros2_humble/install/setup.bash
```

Add this to `~/.bashrc` to avoid repeating it each session.

### 3. Install Python dependencies

```bash
pip install -r src/dicemaster_central/dicemaster_central/requirements.txt
```

### 4. Build the workspace

Always build with `--symlink-install` so Python source edits take effect without rebuilding:

```bash
cd /path/to/DiceMaster_Central
colcon build --symlink-install
```

Build artifacts go to `build/`, `install/`, and `log/` (all gitignored).

### 5. Source the workspace overlay

```bash
source install/setup.bash
```

This must be done after every build and in any new shell where you run nodes.

### 6. Run the tests

```bash
python3 -m pytest src/dicemaster_central/tests/
```

Or, using ROS2 tooling:

```bash
colcon test --packages-select dicemaster_central
colcon test-result --verbose
```

### 7. After a Python-only edit

Because `--symlink-install` is used, Python changes take effect immediately. There is no rebuild step. Just restart the affected node or relaunch:

```bash
ros2 launch dicemaster_central dicemaster.launch.py
```

### 8. After a message definition or setup.py change

A full rebuild is required:

```bash
colcon build --symlink-install
source install/setup.bash
```

### 9. Adding a new game

A game consists of a directory with a `config.json` and an `assets/` folder. The simplest path for development is placing it in the built-in examples directory:

```
src/dicemaster_central/examples/games/{your_game_name}/
  config.json
  assets/
    ...
```

`config.json` must contain:

```json
{
    "game_name": "your_game_name",
    "strategy": "your_strategy_name",
    "strategy_config": {}
}
```

The strategy referenced by `"strategy"` must exist as a directory under `examples/strategies/` (or `~/.dicemaster/strategies/`) containing `{strategy_name}.py` with a `BaseStrategy` subclass.

For permanent user games outside the source tree, place them in:

```
~/.dicemaster/games/{your_game_name}/
~/.dicemaster/strategies/{your_strategy_name}/
```

These locations are scanned by `GameConfig.default_game_locations` and `default_strategy_locations` in `config.py`.

To make your new game the default, edit `GameConfig.default_game` in `src/dicemaster_central/dicemaster_central/config.py`.

## Verify

- `colcon build --symlink-install` exits with `Summary: X packages finished`
- `source install/setup.bash` produces no errors
- `ros2 pkg list | grep dicemaster` shows `dicemaster_central` and `dicemaster_central_msgs`
- `python3 -m pytest src/dicemaster_central/tests/` passes

## Troubleshooting

**`ModuleNotFoundError: No module named 'dicemaster_central'`**
You have not sourced the workspace overlay. Run `source install/setup.bash`.

**Changes to a `.py` file are not reflected when the node runs**
Check whether the workspace was built without `--symlink-install` at some point. Verify with `ls -la install/lib/python*/site-packages/dicemaster_central/` — entries should be symlinks. If they are regular files, rebuild with `--symlink-install`.

**`colcon build` fails on message generation**
Ensure ROS2 Humble is sourced before building (`source ~/ros2_humble/install/setup.bash`). Message generation requires the ament CMake toolchain from ROS2.

**Strategy not discovered by GameManager**
Confirm the strategy directory name matches the `_strategy_name` attribute in the class and the filename. The loader expects `{strategy_name}/{strategy_name}.py`.
