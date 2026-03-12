"""
Example strategy that loads quizlet cards from assets, each with a unique folder name
  - each of which has a "answer.json" file for the bottom of the display
  - and a few (>=4) images as hints in the images/ sub-folder

  At the top, a fixed `question.json` describes the text of the question.

This strategy detects shaking and shuffles to a different question after 3 consecutive shakes.
After each new question, it:
  - starts a 3-second stop period where additional motion is ignored
  - prints the question on the top screen
  - prints the answer to the bottom screen
  - prints the images/gif to the four side screens in random order
"""

import os
import random
import time

from dice import screen, motion, orientation, assets, log, timer
from dice.strategy import BaseStrategy


class ShakeQuizletStrategy(BaseStrategy):
    _strategy_name = "shake_quizlet"

    def __init__(self, game_name: str, config: dict, assets_path: str, **kwargs):
        super().__init__(game_name, config, assets_path, **kwargs)

        # Screen state
        self.top_screen_id = None
        self.bottom_screen_id = None
        self.side_screen_ids = []
        self.available_screen_ids = list(range(1, 7))  # screens 1-6

        # Quizlet data
        self.quizlet_cards = []
        self.current_card_index = 0
        self.question_file_path = None

        # Shake detection state
        self.shake_history = []
        self.last_trigger_time = 0.0
        self.stop_period_duration = 3.0

        self.displayed_initial = False
        self._load_quizlet_cards()
        log(f"ShakeQuizletStrategy initialized with {len(self.quizlet_cards)} cards")

    def _load_quizlet_cards(self):
        """Load all quizlet cards from the assets directory."""
        self.quizlet_cards = []
        root = self._assets_path

        question_path = os.path.join(root, 'question.json')
        if os.path.exists(question_path):
            self.question_file_path = question_path
        else:
            log(f"Warning: question file not found at {question_path}")

        if not os.path.exists(root):
            log(f"Error: assets path does not exist: {root}")
            return

        for item in os.listdir(root):
            item_path = os.path.join(root, item)
            if not os.path.isdir(item_path):
                continue

            answer_path = os.path.join(item_path, 'answer.json')
            images_path = os.path.join(item_path, 'images')

            if not os.path.exists(answer_path) or not os.path.exists(images_path):
                continue

            image_files = [
                os.path.join(images_path, f)
                for f in os.listdir(images_path)
                if f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif.d'))
            ]

            if len(image_files) < 4:
                log(f"Warning: card '{item}' has only {len(image_files)} images, need at least 4")
                continue

            self.quizlet_cards.append({
                'name': item,
                'answer_path': answer_path,
                'image_paths': image_files,
            })

        random.shuffle(self.quizlet_cards)
        log(f"Loaded {len(self.quizlet_cards)} quizlet cards")

    def _update_screen_assignments(self, top, bottom):
        """Update which screens are top/bottom/side."""
        self.top_screen_id = top
        self.bottom_screen_id = bottom
        self.side_screen_ids = [
            sid for sid in self.available_screen_ids
            if sid != top and sid != bottom
        ]

        if not self.displayed_initial:
            self._display_current_question()
            self.displayed_initial = True

    def _display_current_question(self):
        """Display the current question and answer on appropriate screens."""
        if not self.quizlet_cards or self.top_screen_id is None:
            return

        card = self.quizlet_cards[self.current_card_index]

        # Question on top
        if self.question_file_path:
            screen.set_text(self.top_screen_id, self.question_file_path)

        # Answer on bottom
        screen.set_text(self.bottom_screen_id, card['answer_path'])

        # Hint images on sides
        selected_images = random.sample(card['image_paths'], min(4, len(card['image_paths'])))
        sides = self.side_screen_ids.copy()
        random.shuffle(sides)
        for i, image_path in enumerate(selected_images):
            if i >= len(sides):
                break
            if image_path.lower().endswith('.gif.d'):
                screen.set_gif(sides[i], image_path)
            else:
                screen.set_image(sides[i], image_path)

        log(f"Displayed card '{card['name']}'")

    def _next_question(self):
        if not self.quizlet_cards:
            return
        self.current_card_index = (self.current_card_index + 1) % len(self.quizlet_cards)
        self._display_current_question()

    def _on_shake(self, intensity):
        """Handle shake events — trigger next question after 3 consecutive shakes."""
        now = time.time()
        if now - self.last_trigger_time < self.stop_period_duration:
            return

        self.shake_history.append(True)
        if len(self.shake_history) > 3:
            self.shake_history.pop(0)

        if len(self.shake_history) == 3 and all(self.shake_history):
            self.last_trigger_time = now
            self.shake_history = []
            log("3 consecutive shakes detected - changing question")
            self._next_question()

    def start_strategy(self):
        motion.on_shake(self._on_shake)
        orientation.on_change(self._update_screen_assignments)
        log("ShakeQuizletStrategy started - waiting for orientation data")

    def stop_strategy(self):
        self.shake_history = []
        log("ShakeQuizletStrategy stopped")
