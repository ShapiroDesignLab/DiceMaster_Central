# Display Media API

> **Note**: This document describes the Screen API as of the last tested release (`439089c`).
> The `BusEventLoop`-based refactor (commits after Aug 12, 2025) changed the Screen API
> significantly — the `using_rotation` parameter, `queue_media_request()` method, and
> TF2-based rotation tracking described below no longer exist in their original form.
> Until the refactor is tested and documented, refer to the source directly:
> `src/dicemaster_central/dicemaster_central/hw/screen/screen.py`

---

## Archived Content (pre-refactor, untested against current code)

The `Screen` class manages media display for a single ESP32 screen board. It accepts media
requests and transmits them over SPI via the `BusEventLoop`.

For the current wire protocol, see `docs/protocol.md` in the DiceMaster root repository and
`src/dicemaster_central/dicemaster_central/hw/screen/bus_event_loop.py`.
