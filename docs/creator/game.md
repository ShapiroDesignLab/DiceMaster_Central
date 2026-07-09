# Developing a New Game

A DiceMaster game is a Python class that subclasses `BaseStrategy` from the `dice` SDK.
The `dice` SDK abstracts all ROS2 plumbing — your game logic calls `dice.screen`, `dice.motion`,
and `dice.orientation` directly.

## Quick Start

Copy the example strategy as a starting point:

```bash
cp -r examples/strategies/shake_quizlet/ examples/strategies/my_game/
```

See `examples/strategies/shake_quizlet/shake_quizlet.py` for a fully annotated example.

## The dice SDK

```python
from dice import screen, motion, orientation, assets, log, timer

class MyGame(BaseStrategy):
    _strategy_name = "my_game"

    def setup(self):
        motion.on_shake(self.on_shake)

    def on_shake(self):
        screen.set_text(0, "You shook it!")
```

## Asset Structure

- `assets/images/` — JPEG/PNG images (480×480 or 240×240)
- `assets/text/` — JSON files with text content
- `assets/gifs/` — Animated GIFs

## Game Config

Each game lives in its own directory and needs a `config.json`:

```json
{
    "game_name": "my_game",
    "strategy": "my_game",
    "strategy_config": {}
}
```

Place user games in `~/.dicemaster/games/my_game/` and strategies in `~/.dicemaster/strategies/my_game/`.

## Full Documentation

Full game authoring guide is in progress. For now, see:
- `examples/strategies/shake_quizlet/` — fully working example
- `src/dice/dice/` — the dice SDK source
- `docs/creator/strategy.md` — strategy class reference
