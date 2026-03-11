# Raspberry Pi Setup

## Flash & Configure OS

1. Flash Raspbian OS 64-bit lite (or full for GUI desktop)
   - Configure `username=dice` and `password` in pi-imager
2. (Dev only) Enable SSH in pi-imager, configure SSH keys
   - (Optional) Install zerotier for private VPN access
3. Install packages:
```bash
sudo apt update && sudo apt upgrade -y && sudo apt install -y git
```
4. Configure SPI and I2C interfaces — see `docs/user_guides/rpi_hw_config.md`

## Install ROS2 Humble

Since Debian is tier-3 supported, compile from source:
- [ROS2 Humble build instructions](https://docs.ros.org/en/humble/Installation/Ubuntu-Install-Debs.html#setup-sources)
- Build to `~/ros2_humble/` so it can be sourced with:
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

## Install Custom py-spidev

Extended SPI buffer support for screen communication:
```bash
git clone https://github.com/doceme/py-spidev.git
cd py-spidev
pip install -e . --break-system-packages
```

## Configure Auto-Start

See `docs/configure/auto_start.readme.md`
