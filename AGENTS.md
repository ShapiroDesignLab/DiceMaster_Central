# Guidance for Coding Agents

**Do not keep separate documentation in this file.** All project documentation
lives in the README and `docs/`, which are the single source of truth for both
humans and agents. If something is missing or wrong, fix it there — not here.

## Where to look

| You need… | Read |
|---|---|
| Entry point + documentation index | [`README.md`](README.md) |
| System architecture, nodes, topics, message flow | [`docs/api/architecture.md`](docs/api/architecture.md) |
| Screen display pipeline (ScreenBusManager / BusEventLoop / Screen) | [`docs/api/display_media.md`](docs/api/display_media.md) |
| IMU / motion / orientation | [`docs/api/motion_detection.md`](docs/api/motion_detection.md) |
| Raspberry Pi setup, build, launch | [`docs/setup/rpi_setup.md`](docs/setup/rpi_setup.md) |
| Dev workflow, remote (SSH) loop, testing, debugging | [`docs/setup/dev_setup.md`](docs/setup/dev_setup.md) |
| Deploy / restart / verify on the Pi | [`docs/runbooks/deploy.md`](docs/runbooks/deploy.md) |
| Writing a game / strategy | [`docs/creator/`](docs/creator/) |
| Why things are built this way | [`docs/decisions/`](docs/decisions/) |
| What is / isn't hardware-tested | [`docs/project-status.md`](docs/project-status.md) |
| The SPI wire protocol (shared with the ESP32) | root repo `docs/protocol.md` |

## Working notes

- This is a self-contained ROS2 (Humble) colcon workspace; packages live in
  `src/`. Built with `--symlink-install`, so Python-only edits need no rebuild —
  only `.msg`/`.srv`/`setup.py`/C++ changes do. See `docs/runbooks/deploy.md`.
- Real hardware (IMU, SPI, screens) only exists on the Pi (`dice1`); the normal
  loop is edit locally → push → pull on the Pi → test there. See the "Remote
  Development" section of `docs/setup/dev_setup.md`.
- The wire protocol is **shared with `DiceMaster_ESPScreen`** — keep
  `media_typing/protocol.py`, the ESP32 `protocol.h`/`constants.h`, and the root
  repo's `docs/protocol.md` in sync.
- When you change behavior, update the relevant file under `docs/` in the same
  change. Note the tested/untested boundary in `docs/project-status.md`.
