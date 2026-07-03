# Display Media API

How game code puts text, images, and GIFs on the six screens, and how those
requests travel from a ROS2 topic to the ESP32 boards over SPI.

This document describes the current (`BusEventLoop`-based) implementation.
Source of truth:
- `src/dicemaster_central/dicemaster_central/hw/screen/screen_bus_manager.py`
- `src/dicemaster_central/dicemaster_central/hw/screen/bus_event_loop.py`
- `src/dicemaster_central/dicemaster_central/hw/screen/screen.py`
- `src/dicemaster_central/dicemaster_central/media_typing/` (encoding + wire protocol)

For game authors: you normally do **not** touch this layer. Use the `dice.screen`
SDK (`docs/creator/strategy.md`). This document is for people working on the
screen pipeline itself.

---

## The one-paragraph model

A strategy publishes a `ScreenMediaCmd` on `/screen_{id}_cmd`. The
`ScreenBusManager` node that owns that screen's SPI bus receives it on the ROS
executor thread, wraps it in an `Event`, and hands it to a `BusEventLoop`
running on a dedicated per-bus thread. That loop thread does all encoding and
all SPI transmission — it turns the media file into protocol messages and writes
them to the wire, rate-limited per bus. Rotation changes and GIF frame timing
flow through the same single-threaded loop, so the `Screen` object needs no
locks of its own.

---

## Command message: `ScreenMediaCmd`

`dicemaster_central_msgs/msg/ScreenMediaCmd`:

```
int32  screen_id     # target screen, 1–6
int32  media_type    # 0 = TEXT, 1 = IMAGE, 2 = GIF  (constants.ContentType)
string file_path     # ABSOLUTE path to the asset on the Pi
```

`media_type` values come from `constants.ContentType`. `file_path` must be an
absolute path that exists on the Pi's filesystem — the bus manager reads and
encodes the file itself.

Asset formats accepted (`constants.CONTENT_EXTENSION_MAP`):

| media_type | ContentType | On-disk format |
|---|---|---|
| 0 | `TEXT` | `.json` (a `TextGroup` spec) |
| 1 | `IMAGE` | `.jpg` / `.jpeg` |
| 2 | `GIF` | a `.gif.d` directory of frames |

Publish a test command by hand:

```bash
ros2 topic pub /screen_1_cmd dicemaster_central_msgs/msg/ScreenMediaCmd \
  "{screen_id: 1, media_type: 0, file_path: '/absolute/path/to/greeting.json'}" --once
```

---

## Rotation message: `ScreenPose`

The chassis node publishes `/chassis/screen_{id}_pose` (`ScreenPose`) whenever the
dice is reoriented. The bus manager subscribes to it and forwards `msg.rotation`
(a raw `0–3` int, see `constants.Rotation`) into the loop as a
`ROTATION_CHANGED` event. The loop re-encodes the screen's last static content
with the new rotation and resends it. GIFs keep playing and simply pick up the
new rotation on their next frame.

| rotation | meaning |
|---|---|
| 0 | `ROTATION_0` |
| 1 | `ROTATION_90` |
| 2 | `ROTATION_180` |
| 3 | `ROTATION_270` |

---

## Node: `ScreenBusManager` (one per SPI bus)

`screen_bus_manager_{bus_id}`, spawned dynamically by `screens.launch.py`.
See ADR-001 (`docs/decisions/001-ros2-node-per-screen-bus.md`) for why there is
one node per bus.

On construction it:
1. Reads its bus config and the `ScreenConfig`s for the screens on this bus.
2. Opens one `SPIDevice` for the bus.
3. Creates a `Screen` object per screen.
4. Creates the `BusEventLoop` and starts its thread (`start()`).
5. Subscribes to `/screen_{id}_cmd` and `/chassis/screen_{id}_pose` for each
   owned screen.

Its ROS callbacks do the minimum possible work — validate the `screen_id` and
`enqueue` an `Event`. All heavy work happens on the loop thread. This keeps the
ROS executor responsive and keeps SPI access single-threaded per bus.

---

## The loop: `BusEventLoop`

One thread per bus (`bus_loop_{bus_id}`). It blocks on a condition variable and
wakes on either (a) a new event or (b) the next GIF frame deadline
(`condition.wait(timeout=next_gif_deadline)`), so idle buses consume no CPU.

Event types (`EventType`):

| Event | Trigger | Effect |
|---|---|---|
| `NEW_CONTENT` | `/screen_{id}_cmd` | encode the media, send it |
| `ROTATION_CHANGED` | `/chassis/screen_{id}_pose` | re-encode last static content at new rotation, send |
| `SHUTDOWN` | `stop()` | exit the loop thread |

Each wakeup, the loop: handles `SHUTDOWN` first, then drains content/rotation
events, then sends a frame for any screen whose GIF deadline has passed.

### Rate limiting

Every send goes through `_rate_limited_send()`, which enforces
`bus_min_interval_s` (from `SPIBusConfig`) between transfers on that bus. This
paces GIF playback and prevents back-to-back updates from saturating the bus.
Rate limiting is per bus and needs no cross-bus coordination — another reason
for the one-node-per-bus design.

### GIF playback

`_process_gif()` pre-encodes every frame into a list of protocol messages and
sets `gif_active = True`. The loop advances one frame per `GIF_FRAME_TIME`
(`1/12 s`, ~12 fps) via `advance_gif_frame()`, applying the current rotation to
each frame as it goes. There is no `IMAGE_TRANSFER_END` bookkeeping — frame
timing is driven entirely by the loop's deadline math.

---

## Encoding object: `Screen`

`Screen` is a **pure data/encoding object** — no threads, no timers, no locks.
Every method except `__init__`/`destroy` is called only from the loop thread.

| Method | Purpose |
|---|---|
| `process_media(cmd)` | encode TEXT/IMAGE/GIF, store as "last content" |
| `current_msgs()` | encoded messages for the current static content (None for GIF) |
| `resend_with_rotation()` | re-encode last static content at `current_rotation` |
| `advance_gif_frame()` | next GIF frame's messages, rotation applied |

Encoding itself lives in `media_typing/media_types.py` (`TextGroup`, `Image`,
`GIF`) which produce SPI protocol messages via `media_typing/protocol.py`.

---

## Wire protocol (summary)

Messages are chunked and DMA-aligned before hitting SPI. Full protocol details
(5-byte header, screen-ID bit-masking, chunking) live in:
- `src/dicemaster_central/dicemaster_central/media_typing/protocol.py`
- `docs/protocol.md` in the **root** DiceMaster repository (shared with the ESP32 firmware)
- `docs/api/architecture.md` → "Communication Protocol"

The receiving side is documented in `DiceMaster_ESPScreen/docs/architecture.md`.

---

## Debugging the pipeline

| Symptom | Check |
|---|---|
| Screen never updates | `ros2 topic hz /screen_{id}_cmd` — is anything published? |
| Command published, nothing shows | bus manager logs; is `file_path` absolute and present on the Pi? |
| "Unknown screen_id" error | the `screen_id` isn't assigned to any bus in `config.py` |
| GIF stutters | `bus_min_interval_s` too large relative to `GIF_FRAME_TIME`, or bus saturated |
| Rotation not applied | confirm `/chassis/screen_{id}_pose` is publishing (`ros2 topic echo`) |

See `docs/setup/dev_setup.md` for the full ROS2 introspection toolbox.
