#!/bin/bash

# REQUIRES: time is set properly and internet is accessible
__DEBUG_BUILD=false

# Download repository
if [[ "$(basename "$PWD")" != *"DiceMaster_Central" ]]; then
  cd ~/Documents
  git clone git@github.com:ShapiroDesignLab/DiceMaster_Central
  cd DiceMaster_Central/
fi

# Install Dependencies
sudo apt update && sudo apt upgrade -y
sudo apt install < ./apt_requirements.txt

# Setup Interfaces (SPI, I2C)
sudo raspi-config nonint do_spi 0
sudo raspi-config nonint do_i2c 0

# Setup No UI and Auto-Login
sudo raspi-config nonint do_boot_behaviour B2
sudo raspi-config nonint do_boot_autologin 0

# Setup SD Card Auto-Mount
sudo cp ./sd_auto_mount.sh /usr/local/bin/automount-sd.sh
sudo chmod +x /usr/local/bin/automount-sd.sh
sudo bash -c 'echo "ACTION==\"add\", KERNEL==\"sd[a-z][0-9]\", SUBSYSTEM==\"block\", ENV{ID_FS_TYPE}==\"exfat\", RUN+=\"/usr/local/bin/automount-sd.sh %k\"" > /etc/udev/rules.d/99-automount-sd.rules'
sudo udevadm control --reload-rules
sudo udevadm trigger

# Setup Auto-Start
DICE_MAIN_PATH="$(pwd)/path/to/your/script.sh"
# Ensure the script is executable
sudo chmod +x "$DICE_MAIN_PATH"

# Add the script to /etc/rc.local before the 'exit 0' line, if it's not already added
sudo sed -i "/^exit 0/i $SCRIPT_PATH &" /etc/rc.local

# Setup Reemote Debug
sudo raspi-config nonint do_ssh 0

if [[ $__DEBUG_BUILD == false ]]; then
  $ZEROTIER_NET_ID = "56374ac9a4f8cbad"
  # Install zerotier remote management
  curl -s https://install.zerotier.com | sudo yes | sudo bash
  sudo zerotier-cli join $ZEROTIER_NET_ID
fi