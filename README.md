# DiceMaster_Central

This is the Raspberry Pi codebase of the DiceMaster project

## Configure a new Raspberry Pi for DiceMaster Deployment
1. Flash Raspbian OS 64-bit lite (if you prefer to work directly from the pi, flash the full version)
	- Make sure to configure `username=dice` and `password=<your_password>` in pi-imager

2. Install, update packages, and configure OS
```bash
sudo apt update && sudo apt upgrade -y && sudo apt install -y git
```

3. Configure SPI and I2C interfaces by following `DiceMaster_Central/docs/HW_interfaces.md`. 

4. Install ROS 2 humble (base variant is sufficient). 
- Since Debian is tier-3 supported by ROS2, you need to compile from source. You may need to remove a few packages if your raspberry pi has limited storage space (<32GB). 
- [Install ROS2 humble via apt](https://docs.ros.org/en/humble/Installation/Ubuntu-Install-Debs.html#setup-sources)
- We have a pre-built binary package for Raspberry Pi Compute Module 4 (yours may be different!)
- Build ros in `/home/dice/ros2_humble` workspace, such that the build ros2 can be sourced by
```bash
source /home/dice/ros2_humble/install/setup.bash
```

5. Add ROS path to `.bashrc`
```bash
echo 'source /home/dice/ros2_humble/install/setup.bash' >> ~/.bashrc
```

6.  Get the DiceMaster_Central package from github and compile.
DiceMaster_Central is a self-contained colcon workspace — packages live in `src/`, build artifacts go to `build/`/`install/`/`log/` (gitignored).
```bash
git clone git@github.com:ShapiroDesignLab/DiceMaster.git --recursive
cd DiceMaster/DiceMaster_Central
./scripts/setup_workspace.sh
```

7. Download, compile, and install a [custom py-spidev](https://forums.raspberrypi.com/viewtopic.php?t=124472) for extnded SPI buffer support. 
```
git clone https://github.com/doceme/py-spidev.git
cd py-spidev
# make the necessary changes
pip install -e . --break-system-packages
```

8. Configure auto-start of package entrypoint. Follow the tutorial in `docs/auto_start_readme.md`

9. Configure USB mass storage device
https://chatgpt.com/share/689fed33-d4b8-8010-a765-7733afccb31e

## Configure a new Raspberry Pi for Development

1. Do (1, 2) in above. 
2. Configure os with
```bash
sudo raspi-config
```
and in `interface options` enable SSH. 
3. Setup SSH in pi-imager
	- Configure SSH keys from your device
	- (Optional) Install zerotier for easier access through private VPN. 
4. Do everything else above. 