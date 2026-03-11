#!/bin/bash

# Wait for network or graphical environment to be ready (optional delay)
sleep 3

# Source ROS2 and workspace
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
source "$REPO_ROOT/scripts/setup_workspace.sh" --no-build

# Launch DiceMaster
ros2 launch dicemaster_central dicemaster.launch.py