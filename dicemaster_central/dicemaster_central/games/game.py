from abc import ABC
import os
import json
from typing import Optional

class DiceGame(ABC):
    def __init__(self,
        name: str,
        strategy_name: str,
        assets_path: str,
        config_path: str = "",
        **kwargs
    ):
        self.game_name: str = name
        self.strategy_name: str = strategy_name
        self.assets_path: str = assets_path
        self.config_path: str = config_path

        self.strategy_node_kwargs = kwargs

def load_game(game_dir: str, game_name: str, strategies: dict, logger=None) -> Optional['DiceGame']:
    """Verify and load a game from {game_name}/ directory."""
    config_file = os.path.join(game_dir, 'config.json')
    assets_dir = os.path.join(game_dir, 'assets')
    
    # Verify config.json exists
    if not os.path.isfile(config_file):
        if logger:
            logger.warn(f"No config.json found in game directory: {game_dir}")
        return None
    
    # Verify assets/ directory exists
    if not os.path.isdir(assets_dir):
        if logger:
            logger.warn(f"No assets/ directory found in game directory: {game_dir}")
        return None
    
    try:
        # Load and validate config
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # Verify required fields
        required_fields = ['game_name', 'strategy', 'strategy_config']
        for field in required_fields:
            if field not in config:
                if logger:
                    logger.warn(f"Missing required field '{field}' in {config_file}")
                return None
        
        strategy_name = config['strategy']
        
        # Verify strategy exists in discovered strategies
        if strategy_name not in strategies:
            if logger:
                logger.warn(f"Strategy '{strategy_name}' not found for game '{game_name}'")
            return None
        
        # Create DiceGame object
        game = DiceGame(
            name=config['game_name'],
            strategy_name=strategy_name,
            assets_path=assets_dir,
            config_path=config_file,
            **config['strategy_config']
        )
        
        return game
        
    except Exception as e:
        if logger:
            logger.error(f"Failed to verify game from {game_dir}: {e}")
        return None