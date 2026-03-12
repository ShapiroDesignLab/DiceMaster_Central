"""Base strategy — students subclass this to create games."""
from __future__ import annotations
from abc import ABC, abstractmethod
from dice import assets as _assets


class BaseStrategy(ABC):
    _strategy_name: str = ""

    def __init__(self, game_name: str, config: dict, assets_path: str, **kwargs):
        self._game_name = game_name
        self._config = config
        self._assets_path = assets_path
        _assets.configure(assets_path)

    @property
    def game_name(self) -> str:
        return self._game_name

    @property
    def config(self) -> dict:
        return self._config

    @abstractmethod
    def start_strategy(self) -> None:
        ...

    @abstractmethod
    def stop_strategy(self) -> None:
        ...
