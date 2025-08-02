# DiceMaster Configuration Launch System

This directory contains launch files for the DiceMaster configuration system.

## Files

- `launch_config_pub.py`: ROS2 launch file for the config publisher
- `launch_config_simple.py`: Simple Python launcher script

## Usage

### Simple Launcher (Recommended)

```bash
# Source ROS environment first
cd /home/dice/DiceMaster/DiceMaster_ROS_workspace && source prepare.sh

# Validate configuration only
python3 launch/launch_config_simple.py --validate-only

# Launch publisher with default config
python3 launch/launch_config_simple.py

# Launch publisher with custom config file
python3 launch/launch_config_simple.py --config-file /path/to/custom.yaml

# Launch with validation only using custom config
python3 launch/launch_config_simple.py --validate-only --config-file /path/to/custom.yaml
```

### ROS2 Launch File

```bash
# Launch with default config
ros2 launch DiceMaster_Central launch_config_pub.py

# Launch with custom config file
ros2 launch DiceMaster_Central launch_config_pub.py config_file:=/path/to/custom.yaml

# Validation only
ros2 launch DiceMaster_Central launch_config_pub.py validate_only:=true
```

## Configuration File

The launcher looks for configuration files in this order:

1. File specified by `--config-file` argument
2. File specified by `DICE_CONFIG_FILE` environment variable
3. Default: `resource/config.yaml`

## Examples

### Basic Usage
```bash
# Test configuration
./launch_config_simple.py --validate-only

# Run publisher
./launch_config_simple.py
```

### With Custom Config
```bash
# Test custom config
./launch_config_simple.py --validate-only --config-file /path/to/test.yaml

# Run publisher with custom config
./launch_config_simple.py --config-file /path/to/production.yaml
```

## Environment Variables

- `DICE_CONFIG_FILE`: Path to configuration file (overrides default)
- `DICE_VERBOSE`: Enable verbose logging (set to any value)

## Testing

The configuration system includes comprehensive tests:

```bash
# Run config tests
cd /home/dice/DiceMaster/DiceMaster_ROS_workspace && source prepare.sh
cd /home/dice/DiceMaster/DiceMaster_Central
python3 tests/test_config.py manual
```
