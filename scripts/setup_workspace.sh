#!/bin/bash
# setup_workspace.sh — Build the DiceMaster Central colcon workspace.
#
# The repo root IS the workspace; packages live in src/.
#
# Usage:
#   ./scripts/setup_workspace.sh              # rosdep + build
#   ./scripts/setup_workspace.sh --no-build   # rosdep only, skip build
#   source ./scripts/setup_workspace.sh       # build + source into current shell

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

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
# Ensure submodules are initialized
# ---------------------------------------------------------------------------
if [ ! -f "$REPO_ROOT/src/imu_tools/package.xml" ]; then
    echo "Initializing git submodules..."
    git -C "$REPO_ROOT" submodule update --init --recursive
fi

# ---------------------------------------------------------------------------
# Install rosdep dependencies
# ---------------------------------------------------------------------------
if command -v rosdep &>/dev/null; then
    echo "Installing rosdep dependencies..."
    rosdep install --from-paths "$REPO_ROOT/src" --ignore-src -y 2>/dev/null || true
fi

# ---------------------------------------------------------------------------
# Build (unless --no-build)
# ---------------------------------------------------------------------------
if [[ "$1" != "--no-build" ]]; then
    echo "Building workspace..."
    cd "$REPO_ROOT"
    colcon build
    echo ""
    echo "Build complete."
fi

# ---------------------------------------------------------------------------
# Source the workspace (if this script was sourced, not executed)
# ---------------------------------------------------------------------------
if [ -f "$REPO_ROOT/install/setup.bash" ]; then
    source "$REPO_ROOT/install/setup.bash"
    echo "Workspace sourced: $REPO_ROOT/install/setup.bash"
fi

echo ""
echo "Done. To use this workspace in a new shell:"
echo "  source $ROS_SETUP"
echo "  source $REPO_ROOT/install/setup.bash"
