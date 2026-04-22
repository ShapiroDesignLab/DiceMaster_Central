# ADR-003: Use colcon --symlink-install for the Workspace Build

## Status

Accepted

## Context

DiceMaster_Central is a colcon workspace whose packages are almost entirely Python (`dicemaster_central`, `dicemaster_central_msgs` message definitions, and `imu_tools` as a vendored dependency). The development workflow involves frequent edits to Python source files — strategy scripts, hardware drivers, configuration — followed by testing on the Raspberry Pi.

Without `--symlink-install`, colcon copies Python files from the source tree into `install/`. After every Python edit, the developer must re-run `colcon build` before the change takes effect. On the Raspberry Pi (aarch64, limited I/O), a full package build takes tens of seconds even for a trivial one-line change. This friction slows the edit-test loop significantly.

## Decision

The workspace is always built with `--symlink-install`:

```bash
colcon build --symlink-install
```

This causes colcon to create symbolic links from `install/` back to the source tree for Python files, instead of copying them. After building once, edits to any `.py` file under `src/` are visible to the installed package immediately — no rebuild required.

The `--symlink-install` flag is documented in `docs/setup/rpi_setup.md` and used in all rebuild instructions throughout the project.

## Consequences

**Positive:**
- Python source changes (strategy logic, hardware drivers, launch files, config) take effect the next time the relevant node starts, with no rebuild step. For long-running nodes, restarting the node or the full launch is sufficient.
- The edit-test cycle on the Raspberry Pi is reduced to: edit locally, push, pull on device, restart node.
- `launch/*.launch.py` files are also symlinked, so launch file changes are instant.

**Negative:**
- Changes to `setup.py`, `package.xml`, or any `.msg`/`.srv` message definition in `dicemaster_central_msgs` still require a full `colcon build --symlink-install` followed by a restart of all nodes that use those messages. The symlink approach only bypasses the copy step for Python; it does not skip CMake or ament processing for message generation.
- Developers who accidentally run `colcon build` without `--symlink-install` (e.g. copy-pasting a generic build command) will silently switch back to a copy-based install. Subsequent Python edits will appear to have no effect until the next build.
- Symlinks mean the `install/` tree is not self-contained: moving or deleting the source tree breaks the installed package. This is acceptable for a development-only Pi that always has the source present.

## Alternatives Considered

**Regular install (no flag):** Every Python change requires a rebuild. Rebuild time on the Pi is acceptable for infrequent changes but becomes disruptive during active development. Rejected for the development workflow.

**Editable pip install (`pip install -e`):** Would work for pure Python packages but is incompatible with ament/colcon packaging, which is required for ROS2 node discovery, message generation, and launch file integration.
