# ADR-001: One ROS2 Node Per SPI Screen Bus

## Status

Accepted

## Context

DiceMaster has 6 ESP32-driven screens distributed across 3 SPI buses:
- Bus 0: Screens 1 and 6
- Bus 1: Screens 3 and 5
- Bus 3: Screens 2 and 4

Each screen can display text, images, or GIFs. Game strategies publish `ScreenMediaCmd` messages to `/screen_{id}_cmd` topics and expect responsive, near-simultaneous updates across multiple screens — for example, when a new quizlet card is shown, all 6 screens must update within a short window.

SPI is a synchronous, blocking bus: one message transfer holds the bus until complete. A single node managing all 6 screens serially would serialize all transfers, causing visible lag when multiple screens need to update at once. GIF playback adds further pressure because frames must be sent at a consistent cadence.

An alternative was a single `ScreenManager` node using Python threading to interleave sends across buses. This approach was prototyped but introduced lock contention and made the transmission pipeline harder to reason about, because all bus state lived in one node.

## Decision

Use one `ScreenBusManager` ROS2 node per SPI bus, launched dynamically from `screens.launch.py` based on `dice_config.active_spi_controllers`. Each node:

- Owns one `SPIDevice` instance for its bus.
- Manages the `Screen` objects for the screens on that bus (2 screens per bus in the current hardware configuration).
- Subscribes independently to `/screen_{id}_cmd` (via `ScreenMediaCmd`) and `/chassis/screen_{id}_pose` (via `ScreenPose`) for each screen it owns.
- Delegates all encoding and SPI transmission to a `BusEventLoop` that runs in a dedicated background thread.

The node is named `screen_bus_manager_{bus_id}` and is spawned with the bus ID passed as a command-line argument.

## Consequences

**Positive:**
- The three buses operate in parallel, so updates to screens on different buses proceed simultaneously without blocking each other.
- Each node's state (SPI device handle, screen objects, event queue) is isolated; a crash or error on one bus does not affect the others.
- Adding a fourth SPI bus requires only a new entry in `dice_config.bus_configs` and `dice_config.screen_configs`; `screens.launch.py` picks it up automatically.
- The `BusEventLoop` background thread can apply per-bus rate limiting (`bus_min_interval_s`) without coordinating with other buses.

**Negative:**
- Three nodes must be monitored instead of one. If a bus node dies, its screens go dark silently unless health monitoring is added.
- Cross-bus ordering guarantees are absent: if a strategy wants screens on bus 0 and bus 1 to update at exactly the same instant, there is no synchronization primitive to enforce that.

## Alternatives Considered

**Single node with Python threading:** One `ScreenManager` node holding three threads, one per bus. Rejected because all bus state shared one process address space, lock contention between threads was non-trivial to tune, and a failure in one bus thread could corrupt shared state and take down all screens.

**Single node with asyncio:** Similar isolation concerns as threading, plus mixing asyncio with the ROS2 executor model requires care to avoid deadlocks on callback queues.
