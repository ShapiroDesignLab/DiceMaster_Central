# DiceMaster_Central

Raspberry Pi ROS2 runtime for the [DiceMaster](https://github.com/DanielHou315/DiceMaster) programmable dice — coordinates game logic, reads IMU motion/orientation, and streams media commands to 6 ESP32-powered screens over SPI.

For overall system architecture, see the [root repository](https://github.com/DanielHou315/DiceMaster).

## System Role

```
 Game (dice Python SDK)
       │
       ▼
 Chassis Node ◀── IMU (MPU-6050, I2C)
       │
       ▼
 Screen Bus (SPI master) ──▶ 6× ESP32 screens (DiceMaster_ESPScreen)
```

## Quick Start

See [docs/setup/rpi_setup.md](docs/setup/rpi_setup.md) for full setup and deployment instructions.

## Hardware

- Raspberry Pi 4 (or Compute Module 4)
- MPU-6050 6-axis IMU (I2C, address 0x68)
- 6× SPI connections to ESP32 Qualia boards (one SPI bus per pair, CS lines per board)
- Wire protocol: see [docs/protocol.md](https://github.com/DanielHou315/DiceMaster/blob/main/docs/protocol.md) in the root repository

## Documentation

| Section | Contents |
|---|---|
| [docs/api/architecture.md](docs/api/architecture.md) | System architecture, node hierarchy, message flow, configuration |
| [docs/api/display_media.md](docs/api/display_media.md) | Screen display API reference |
| [docs/api/motion_detection.md](docs/api/motion_detection.md) | IMU motion detection API |
| [docs/setup/rpi_setup.md](docs/setup/rpi_setup.md) | Raspberry Pi setup, ROS2 install, build, launch |
| [docs/setup/rpi_hw_config.md](docs/setup/rpi_hw_config.md) | SPI and I2C hardware configuration |
| [docs/setup/auto_start.md](docs/setup/auto_start.md) | Auto-start systemd service setup |
| [docs/setup/dev_setup.md](docs/setup/dev_setup.md) | Development setup, remote (SSH) workflow, testing, debugging |
| [docs/creator/game.md](docs/creator/game.md) | How to create a new game |
| [docs/creator/strategy.md](docs/creator/strategy.md) | How to create a new strategy |
| [docs/decisions/](docs/decisions/) | Architecture Decision Records (why things are built the way they are) |
| [docs/project-status.md](docs/project-status.md) | Tested/untested boundary and hardware bring-up checklist |

---

## Project Status

The last state verified on real hardware is commit `439089c` (Aug 12, 2025).
Everything since — including the event-driven screen bus, the Madgwick IMU
pipeline, and the `dice` SDK — is unit-tested but **not yet re-verified on
hardware**. See [docs/project-status.md](docs/project-status.md) for the
tested/untested boundary and the hardware bring-up checklist.
