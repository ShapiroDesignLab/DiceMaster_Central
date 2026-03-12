"""Integration test — simulate a full game round with ROS2 mock."""
from dice import screen, motion, orientation, log
from dice.strategy import BaseStrategy
from dice._runtime import teardown
from dicemaster_central_msgs.msg import MotionDetection, ChassisOrientation


class QuizGame(BaseStrategy):
    _strategy_name = "quiz"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.question_idx = 0

    def start_strategy(self):
        self.show_question()
        motion.on_shake(self.next_question)
        orientation.on_change(self.on_flip)

    def stop_strategy(self):
        log("game over")

    def show_question(self):
        screen.set_text(1, f"q{self.question_idx}.json")

    def next_question(self, intensity):
        self.question_idx += 1
        self.show_question()

    def on_flip(self, top, bottom):
        screen.set_image(top, "highlight.jpg")


def test_full_game_lifecycle(mock_runtime):
    # 1. Create and start
    game = QuizGame(game_name="quiz", config={}, assets_path="/assets")
    game.start_strategy()

    # Verify initial screen publish
    pub1 = mock_runtime.publishers_["/screen_1_cmd"]
    assert len(pub1.messages) == 1
    assert pub1.messages[0].file_path == "q0.json"

    # 2. Simulate shake
    motion_sub = [s for s in mock_runtime.subscriptions_ if s.topic == "/imu/motion"][0]
    shake_msg = MotionDetection()
    shake_msg.shaking = True
    shake_msg.shake_intensity = 0.7
    motion_sub.callback(shake_msg)

    assert len(pub1.messages) == 2
    assert pub1.messages[1].file_path == "q1.json"

    # 3. Simulate orientation change
    orient_sub = [s for s in mock_runtime.subscriptions_ if s.topic == "/chassis/orientation"][0]
    orient_msg = ChassisOrientation()
    orient_msg.top_screen_id = 3
    orient_msg.bottom_screen_id = 4
    orient_sub.callback(orient_msg)

    pub3 = mock_runtime.publishers_["/screen_3_cmd"]
    assert pub3.messages[0].file_path == "highlight.jpg"

    # 4. Stop game
    game.stop_strategy()
    assert ("info", "game over") in mock_runtime._logger.messages

    # 5. Teardown
    teardown()

    # 6. Verify state reset
    assert motion.is_shaking() is False
    assert orientation.top() == 1
