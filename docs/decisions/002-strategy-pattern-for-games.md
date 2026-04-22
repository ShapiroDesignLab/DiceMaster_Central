# ADR-002: Strategy/Plugin Pattern for Game Logic (BaseStrategy)

## Status

Accepted

## Context

DiceMaster is designed to support multiple educational games — quizlet flash cards, language drills, vocabulary challenges, and others — each with different rules for how screens update in response to shaking or orientation changes. The system needs to let educators and content creators write new games without requiring them to understand ROS2 node lifecycle, topic subscription plumbing, or SPI screen protocols.

Two approaches were considered for how game logic connects to the ROS2 graph:

1. **Raw node subclassing:** Each game author subclasses `rclpy.node.Node` directly, creates their own subscriptions and publishers, and is added to the executor. This is flexible but exposes the full ROS2 API surface to game authors, who may have no ROS2 experience.

2. **Strategy pattern with a base class:** Provide a `BaseStrategy` class that already is a `rclpy.node.Node` and handles node naming, configuration loading, and asset loading. Game authors implement two abstract methods — `start_strategy()` and `stop_strategy()` — and declare a `_strategy_name` class attribute. The framework discovers and loads strategy classes automatically.

## Decision

All game logic inherits from `BaseStrategy` (`src/dicemaster_central/dicemaster_central/games/strategy.py`). The base class:

- Is itself a `rclpy.node.Node` subclass, so the strategy is a first-class ROS2 node named `strategy_{game_name}`.
- Accepts `game_name`, `config_file`, and `assets_path` in its constructor and handles loading both the JSON config and the assets directory index before calling `start_strategy()`.
- Raises `FileNotFoundError` or `RuntimeError` if required files are missing, so the `GameManager` can catch failures cleanly.
- Calls `start_strategy()` at the end of `__init__`, so the strategy is live immediately after construction.
- Requires `stop_strategy()` to be implemented for clean teardown; `GameManager` calls this before removing the node from the executor and destroying it.

Each strategy class sets `_strategy_name` as a class attribute (e.g. `_strategy_name = "shake_quizlet"`). The `load_strategy()` function discovers strategy files by scanning configured directories, loading `{strategy_name}.py`, and finding any class that is a subclass of `BaseStrategy`. This means a game author drops a single `.py` file into `~/.dicemaster/strategies/{name}/` and the framework picks it up on the next launch.

Games are separate from strategies. A game is a directory with `config.json` (specifying `game_name`, `strategy`, and `strategy_config`) and an `assets/` folder. Multiple games can share the same strategy class with different asset sets.

## Consequences

**Positive:**
- Game authors only need to implement `start_strategy()` and `stop_strategy()`, plus whatever ROS2 subscriptions they choose (e.g. `/imu/motion`, `/chassis/orientation`). They are not required to manage node lifecycle, executor registration, or configuration parsing.
- Strategies are auto-discovered from `~/.dicemaster/strategies/` and the built-in examples directory; no registration step is needed.
- The `GameManager` can start, stop, and switch games at runtime by adding and removing strategy nodes from the `MultiThreadedExecutor` without restarting the full system.
- A broken strategy (raises during init) is isolated: `GameManager.start_game()` catches the exception and returns `False` without crashing other nodes.

**Negative:**
- Game authors must understand the `BaseStrategy` API and the lifecycle contract (`start_strategy` / `stop_strategy`). Incorrect teardown in `stop_strategy` can leak ROS2 subscriptions or timers.
- Because `BaseStrategy.__init__` calls `start_strategy()` before returning, any ROS2 subscriptions created in `start_strategy()` are active before the node is added to the executor; callbacks may queue but not execute until the executor picks up the node.
- The `_strategy_name` class attribute is used for logging and discovery but is not enforced by the ABC; omitting it produces a confusing `AttributeError` at runtime rather than a clear error at class definition time.

## Alternatives Considered

**Raw `rclpy.node.Node` subclassing:** Full ROS2 flexibility, but no guardrails. Game authors would need to know ROS2 topic names, message types, and executor management. Rejected because the target audience includes non-ROS2 developers.

**YAML-driven game definition with no code:** Define games entirely in YAML (screens, triggers, assets). Rejected because the game logic (e.g. "advance card after 3 consecutive shakes within a cooldown window") cannot be expressed declaratively without a custom scripting layer that would be as complex as Python.
