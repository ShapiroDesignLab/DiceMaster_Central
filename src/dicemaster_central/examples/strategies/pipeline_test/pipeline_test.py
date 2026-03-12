"""
Example strategy that cycles through screen IDs and sends a text notification to each one.

Uses dice.timer for periodic callbacks and dice.screen for display.
"""

import os
import json
import tempfile

from dice import screen, log, timer
from dice.strategy import BaseStrategy


class TestStrategy(BaseStrategy):
    _strategy_name = "pipeline_test"

    def __init__(self, game_name: str, config: dict, assets_path: str, **kwargs):
        super().__init__(game_name, config, assets_path, **kwargs)
        self.available_screen_ids = list(range(1, 7))
        self.current_screen_index = 0
        self.message_count = 0
        self._timer_id = None
        self._temp_dir = tempfile.mkdtemp(prefix="dice_test_")

    def start_strategy(self):
        self._timer_id = timer.set(0.1, self._send_notification)
        log("TestStrategy started - sending notifications every 0.1s")

    def stop_strategy(self):
        if self._timer_id is not None:
            timer.cancel(self._timer_id)
            self._timer_id = None
        log("TestStrategy stopped")

    def _send_notification(self):
        if not self.available_screen_ids:
            return

        target_id = self.available_screen_ids[self.current_screen_index]
        self.current_screen_index = (self.current_screen_index + 1) % len(self.available_screen_ids)
        self.message_count += 1

        content = f"Test #{self.message_count} screen {target_id}"

        # Build a simple text JSON file for the screen
        text_data = {
            "bg_color": "0x0000",
            "texts": [{
                "x_cursor": 40,
                "y_cursor": 200,
                "font_name": "tf",
                "font_color": "0xFFFF",
                "text": content,
            }]
        }
        path = os.path.join(self._temp_dir, f"notif_{target_id}.json")
        with open(path, 'w') as f:
            json.dump(text_data, f)

        screen.set_text(target_id, path)
