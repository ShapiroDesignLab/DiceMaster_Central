import pytest
from dice.strategy import BaseStrategy


class FakeStrategy(BaseStrategy):
    _strategy_name = "fake"
    started = False
    stopped = False

    def start_strategy(self):
        self.started = True

    def stop_strategy(self):
        self.stopped = True


def test_strategy_name():
    assert FakeStrategy._strategy_name == "fake"


def test_start_strategy(mock_runtime):
    s = FakeStrategy(game_name="test", config={}, assets_path="/tmp")
    s.start_strategy()
    assert s.started


def test_stop_strategy(mock_runtime):
    s = FakeStrategy(game_name="test", config={}, assets_path="/tmp")
    s.stop_strategy()
    assert s.stopped


def test_config_access(mock_runtime):
    s = FakeStrategy(game_name="test", config={"difficulty": "hard"}, assets_path="/tmp")
    assert s.config["difficulty"] == "hard"


def test_game_name(mock_runtime):
    s = FakeStrategy(game_name="my_game", config={}, assets_path="/tmp")
    assert s.game_name == "my_game"


def test_abstract_methods():
    with pytest.raises(TypeError):
        BaseStrategy(game_name="test", config={}, assets_path="/tmp")
