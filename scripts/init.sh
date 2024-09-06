#!/bin/bash

# REQUIRES: time is set properly and internet is accessible
__DEBUG_BUILD=false


# Update System Dependencies
sudo apt update && sudo apt upgrade -y
sudo apt install < ./apt_requirements.txt


# Install Py Venv
VENV_DIR="$HOME/DiceMaster_Central_venv"
python3 -m venv "$VENV_DIR"
VENV_PIP="$VENV_DIR/bin/pip3" 
"$VENV_PIP" install --upgrade pip
"$VENV_PIP" install -r ./dice_pip_requirements.txt


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


# Path to the Python script
DICE_MAIN_PATH="$HOME/Documents/DiceMaster_Central/dice.py"
PYTHON_EXEC="$VENV_DIR/bin/python"
# Name of the Miniconda environment
ENV_NAME="my_conda_env"
# Ensure the script is executable
sudo chmod +x "$DICE_MAIN_PATH"
# Add the activation and script execution to /etc/rc.local before the 'exit 0' line
# sudo sed -i "/^exit 0/i source /home/$USER/miniconda3/bin/activate $ENV_NAME && python $DICE_MAIN_PATH &" /etc/rc.local
sudo sed -i "/^exit 0/i source $PYTHON_EXEC $DICE_MAIN_PATH &" /etc/rc.local

# Setup Remote Debug
sudo raspi-config nonint do_ssh 0

if [[ $__DEBUG_BUILD == true ]]; then
  $ZEROTIER_NET_ID="56374ac9a4f8cbad"
  # Install zerotier remote management
  curl -s https://install.zerotier.com | sudo yes | sudo bash
  sudo zerotier-cli join $ZEROTIER_NET_ID
fi
