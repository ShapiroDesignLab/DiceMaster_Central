# Docs Restructure Design

**Date:** 2026-03-11
**Status:** Approved

## Goal

Reorganize `docs/` into three audience-oriented sections — `api/`, `setup/`, and `creator/` — and clean up `README.md` to be a short entry point with routing links.

---

## Target Structure

```
docs/
  api/
    architecture.md        ← refactored from developer_guide.md (overview + cross-refs only)
    display_media.md       ← unchanged
    motion_detection.md    ← unchanged
  setup/
    rpi_setup.md           ← merged from docs/setup.md + README.md setup steps
    rpi_hw_config.md       ← moved from user_guides/rpi_hw_config.md
    auto_start.md          ← moved from configure/auto_start.readme.md
    dev_setup.md           ← moved from user_guides/remote_dev.md (currently empty stub)
  creator/
    game.md                ← moved from user_guides/game.md
    strategy.md            ← moved from user_guides/strategy.md
  superpowers/specs/       ← internal specs (this file)
```

---

## Files to Create

| File | Source |
|------|--------|
| `docs/api/architecture.md` | Refactored from `developer_guide.md` — overview + cross-refs only |
| `docs/setup/rpi_setup.md` | Merged from `docs/setup.md` + README.md setup steps |
| `docs/setup/rpi_hw_config.md` | Moved from `user_guides/rpi_hw_config.md` |
| `docs/setup/auto_start.md` | Moved from `configure/auto_start.readme.md` |
| `docs/setup/dev_setup.md` | Moved from `user_guides/remote_dev.md` (stub); add Testing & Debugging section from `developer_guide.md` |
| `docs/creator/game.md` | Moved from `user_guides/game.md` |
| `docs/creator/strategy.md` | Moved from `user_guides/strategy.md` |

---

## Files to Delete

| File | Reason |
|------|--------|
| `docs/architecture.md` | Empty; replaced by `docs/api/architecture.md` |
| `docs/developer_guide.md` | Content refactored into `docs/api/architecture.md` |
| `docs/setup.md` | Content merged into `docs/setup/rpi_setup.md` |
| `docs/configure/auto_start.readme.md` | Moved to `docs/setup/auto_start.md` |
| `docs/configure/` folder | Empty after move |
| `docs/user_guides/remote_dev.md` | Moved to `docs/setup/dev_setup.md` |
| `docs/user_guides/rpi_hw_config.md` | Moved to `docs/setup/rpi_hw_config.md` |
| `docs/user_guides/game.md` | Moved to `docs/creator/game.md` |
| `docs/user_guides/strategy.md` | Moved to `docs/creator/strategy.md` |
| `docs/user_guides/` folder | Empty after moves |

---

## README.md Changes

### Remove
- Steps 1–8 (full RPi setup walkthrough) → moved to `docs/setup/rpi_setup.md`
- "Configure USB mass storage device" step → deleted (hardware no longer supports this feature)
- "Configure a new Raspberry Pi for Development" section → moved to `docs/setup/dev_setup.md`

### Keep
- Project name and one-line description

### Add
A `## Documentation` section:
```markdown
## Documentation
- **Architecture & API**: `docs/api/architecture.md`
- **Setup & Deployment**: `docs/setup/`
- **Creating Games & Strategies**: `docs/creator/`
```

A minimal quick-start pointer:
```markdown
## Quick Start
See [docs/setup/rpi_setup.md](docs/setup/rpi_setup.md) for full setup instructions.
```

---

## `docs/api/architecture.md` Content Outline

Refactored from `developer_guide.md`. The file becomes a **thin overview** that cross-references other docs rather than containing all detail inline.

### Sections to Keep (abbreviated)
1. **System Architecture Overview** — high-level component diagram, brief node descriptions
2. **Communication Protocol** — protocol summary, key topic names, no full code blocks
3. **ROS2 Node Architecture** — table of nodes and their responsibilities
4. **Message Flow** — abbreviated sequence diagram or description

### Sections to Relocate Out
| Section in developer_guide.md | Destination |
|-------------------------------|-------------|
| Testing & Debugging | `docs/setup/dev_setup.md` |
| Deployment | `docs/setup/rpi_setup.md` |
| Hardware Interfaces detail | `docs/setup/rpi_hw_config.md` |
| Launch System | `docs/setup/rpi_setup.md` |
| Configuration System | `docs/api/architecture.md` (brief summary, link to source) |
| Protocol Implementation (code) | `docs/api/architecture.md` (summary only, or link to source) |

### Cross-References to Add
- → `docs/setup/rpi_setup.md` for deployment and launch
- → `docs/setup/dev_setup.md` for testing and debugging
- → `docs/api/display_media.md` for Screen class API
- → `docs/api/motion_detection.md` for IMU API
- → `docs/creator/game.md` and `docs/creator/strategy.md` for extending the system

---

## Constraints

- **Do not invent content** for stub files (`game.md`, `strategy.md`, `dev_setup.md`, `remote_dev.md`) — move them as stubs, mark with a TODO if needed
- **Preserve all existing content** that is not explicitly deleted (USB storage section)
- **No content duplication** — setup steps currently in both README and setup.md should appear only in `docs/setup/rpi_setup.md`

---

## Success Criteria

1. `docs/` contains exactly four subdirectories: `api/`, `setup/`, `creator/`, `superpowers/`
2. `README.md` is under 50 lines with routing links to `docs/`
3. `docs/api/architecture.md` is a cross-referencing overview, not a monolithic guide
4. No broken internal links in any doc file
5. `developer_guide.md`, `setup.md`, and the old folder structure no longer exist
