#!/bin/bash

# Wait for network or graphical environment to be ready (optional delay)
sleep 3

# Source your ROS 2 setup and workspace
source /home/dice/DiceMaster/DiceMaster_ROS_workspace/prepare.sh

# Launch your ROS 2 launch file
ros2 launch dicemaster_central dicemaster.launch.py