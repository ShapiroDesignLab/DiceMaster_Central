#!/bin/bash
# setup_workspace.sh — Set up the ROS2 workspace for DiceMaster Central.
#
# Creates ros_ws/src/ with symlinks to all packages, installs rosdep
# dependencies, and runs colcon build. Idempotent — safe to re-run.
#
# Usage:
#   ./scripts/setup_workspace.sh          # full setup + build
#   ./scripts/setup_workspace.sh --no-build   # setup only, skip build
#   source ./scripts/setup_workspace.sh   # setup + source into current shell

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
WS_DIR="$REPO_ROOT/ros_ws"
SRC_DIR="$WS_DIR/src"

# ---------------------------------------------------------------------------
# Detect ROS2 installation
# ---------------------------------------------------------------------------
ROS_SETUP=""
for candidate in \
    /opt/ros/humble/setup.bash \
    "$HOME/ros2_humble/install/setup.bash" \
    /opt/ros/humble/install/setup.bash; do
    if [ -f "$candidate" ]; then
        ROS_SETUP="$candidate"
        break
    fi
done

if [ -z "$ROS_SETUP" ]; then
    echo "ERROR: Could not find ROS2 Humble setup.bash"
    echo "Searched: /opt/ros/humble/setup.bash, ~/ros2_humble/install/setup.bash"
    exit 1
fi

echo "Using ROS2 from: $ROS_SETUP"
source "$ROS_SETUP"

# ---------------------------------------------------------------------------
# Create workspace src/ symlinks
# ---------------------------------------------------------------------------
mkdir -p "$SRC_DIR"

# Link our own packages
for pkg in dicemaster_central dicemaster_central_msgs dicemaster_cpp; do
    target="$REPO_ROOT/$pkg"
    link="$SRC_DIR/$pkg"
    if [ ! -e "$link" ]; then
        ln -sf "$target" "$link"
        echo "Linked: $link -> $target"
    fi
done

# Link external dependencies (imu_tools submodule)
DEPS_DIR="$REPO_ROOT/deps"
if [ -d "$DEPS_DIR/imu_tools" ]; then
    link="$SRC_DIR/imu_tools"
    if [ ! -e "$link" ]; then
        ln -sf "$DEPS_DIR/imu_tools" "$link"
        echo "Linked: $link -> $DEPS_DIR/imu_tools"
    fi
else
    echo "WARNING: deps/imu_tools not found. Run: git submodule update --init --recursive"
fi

# ---------------------------------------------------------------------------
# Set colcon defaults
# ---------------------------------------------------------------------------
export COLCON_DEFAULTS_FILE="$WS_DIR/colcon.defaults.json"

# ---------------------------------------------------------------------------
# Install rosdep dependencies
# ---------------------------------------------------------------------------
if command -v rosdep &>/dev/null; then
    echo "Installing rosdep dependencies..."
    rosdep install --from-paths "$SRC_DIR" --ignore-src -y 2>/dev/null || true
fi

# ---------------------------------------------------------------------------
# Build (unless --no-build)
# ---------------------------------------------------------------------------
if [[ "$1" != "--no-build" ]]; then
    echo "Building workspace..."
    cd "$WS_DIR"
    colcon build
    echo ""
    echo "Build complete."
fi

# ---------------------------------------------------------------------------
# Source the workspace (if this script was sourced, not executed)
# ---------------------------------------------------------------------------
if [ -f "$WS_DIR/install/setup.bash" ]; then
    source "$WS_DIR/install/setup.bash"
    echo "Workspace sourced: $WS_DIR/install/setup.bash"
fi

echo ""
echo "Done. To use this workspace in a new shell:"
echo "  source $ROS_SETUP"
echo "  source $WS_DIR/install/setup.bash"
