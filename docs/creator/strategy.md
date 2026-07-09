# Developing a New Strategy

A strategy is a Python class that defines the behavior of a DiceMaster game. It subclasses
`BaseStrategy` and is loaded dynamically by the game manager at runtime.

## Strategy Anatomy

```python
from dice.strategy import BaseStrategy
from dice import screen, motion, orientation, log

class MyStrategy(BaseStrategy):
    _strategy_name = "my_strategy"   # must match directory and filename

    def setup(self):
        """Called once when the strategy is loaded. Register callbacks here."""
        motion.on_shake(self.on_shake)
        orientation.on_face_up(1, self.on_face_1_up)

    def teardown(self):
        """Called when the strategy is unloaded. Clean up resources here."""
        pass

    def on_shake(self):
        log.info("Shaken!")
        screen.set_text(0, "Shake detected")

    def on_face_1_up(self):
        screen.set_image(0, "assets/images/face1.jpg")
```

## Discovery Rules

The game manager discovers strategies by name:
1. Strategy directory name must match `_strategy_name`
2. File inside the directory must be `{strategy_name}.py`
3. The class must subclass `BaseStrategy` and set `_strategy_name`

Search paths (in order):
1. `examples/strategies/` (built-in examples)
2. `~/.dicemaster/strategies/` (user strategies)

## Available dice SDK Modules

| Module | Purpose |
|---|---|
| `dice.screen` | Display text, images, and GIFs on the 6 screens |
| `dice.motion` | Register shake/motion event callbacks |
| `dice.orientation` | Register face-up orientation event callbacks |
| `dice.assets` | Load assets from the game's asset directory |
| `dice.log` | Logging (routes to ROS2 logger) |
| `dice.timer` | Schedule delayed or repeating callbacks |

## Full Documentation

Full strategy authoring guide is in progress. For now, see:
- `examples/strategies/shake_quizlet/` — fully working example
- `src/dice/dice/strategy.py` — BaseStrategy source
- `docs/creator/game.md` — game config and asset structure
