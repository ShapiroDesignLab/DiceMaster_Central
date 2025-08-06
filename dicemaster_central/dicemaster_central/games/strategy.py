from abc import ABC, abstractmethod
import os
import json
import importlib
import importlib.util
from typing import Optional, Type

# NOTE: inherit from LifecycleNode instead of Node
from rclpy.lifecycle import LifecycleNode, State, TransitionCallbackReturn
from dicemaster_central.utils import load_directory


class BaseStrategy(LifecycleNode, ABC):
    """
    Base class for all strategies in the DiceMaster Central system.
    Now implemented as a LifecycleNode so it can be managed (configure/activate/deactivate).
    """
    _strategy_name: str
    def __init__(
        self,
        game_name: str,
        config_file: str,
        assets_path: str,
        verbose: bool = False,
    ):
        super().__init__(game_name)
        self._game_name = game_name
        self.get_logger().info(f"{self._game_name} (strategy={self._strategy_name}) initialized (lifecycle)")

        self._config_file = config_file
        self._assets_path = assets_path
        self._verbose = verbose

        # Load configuration
        if not os.path.isfile(self._config_file):
            self.get_logger().error(f"Configuration file {self._config_file} does not exist")
            raise FileNotFoundError(f"Configuration file {self._config_file} not found")
        try:
            self._config = json.load(open(self._config_file, "r", encoding="utf-8"))
        except Exception as e:
            self.get_logger().error(f"Failed to load configuration from {self._config_file}: {e}")
            # Let lifecycle error handling take over
            raise

        # Load assets
        if not os.path.exists(self._assets_path):
            self.get_logger().error(f"Assets path {self._assets_path} does not exist")
            raise FileNotFoundError(f"Assets path {self._assets_path} not found")
        self._assets = self._load_assets()

    def _load_assets(self):
        """Load the assets index for this game."""
        dir_idx = load_directory(self._assets_path)
        if self._verbose:
            print(f"Strategy {self._strategy_name}")
        return dir_idx

    # --- Abstract work methods your concrete strategies implement ---
    @abstractmethod
    def start_strategy(self):
        """Start any publishers/timers/work needed while ACTIVE."""
        pass

    @abstractmethod
    def stop_strategy(self):
        """Stop/tear down publishers/timers/work when leaving ACTIVE."""
        pass

    # --- Lifecycle callbacks ---
    def on_activate(self, state: State) -> TransitionCallbackReturn:
        """
        Called when a transition to ACTIVE is requested.
        Return SUCCESS to complete the transition, FAILURE to abort.
        """
        try:
            self.start_strategy()
            self.get_logger().info(f"{self._strategy_name}: activated.")
            return TransitionCallbackReturn.SUCCESS
        except Exception as e:
            self.get_logger().error(f"{self._strategy_name}: activation failed: {e}")
            return TransitionCallbackReturn.FAILURE

    def on_deactivate(self, state: State) -> TransitionCallbackReturn:
        """
        Called when a transition from ACTIVE to INACTIVE is requested.
        """
        try:
            self.stop_strategy()
            self.get_logger().info(f"{self._strategy_name}: deactivated.")
            return TransitionCallbackReturn.SUCCESS
        except Exception as e:
            self.get_logger().error(f"{self._strategy_name}: deactivation failed: {e}")
            return TransitionCallbackReturn.FAILURE

    # Optional: keep your explicit cleanup path if you use it elsewhere
    def _destroy(self):
        try:
            self.stop_strategy()
        except Exception:
            # avoid raising in destroy path
            pass
        super().destroy_node()

    def __del__(self):
        # Avoid heavy work in __del__; lifecycle shutdown is preferred.
        try:
            self._destroy()
        except Exception:
            pass
    
    @staticmethod
    def verify_and_load(strategy_dir: str, strategy_name: str, logger=None) -> Optional[Type['BaseStrategy']]:
        """Verify and load a strategy from {strategy_name}/__init__.py."""
        init_file = os.path.join(strategy_dir, '__init__.py')
        
        if not os.path.isfile(init_file):
            if logger:
                logger.warn(f"No __init__.py found in strategy directory: {strategy_dir}")
            return None
        
        try:
            spec = importlib.util.spec_from_file_location(strategy_name, init_file)
            if spec is None or spec.loader is None:
                if logger:
                    logger.warn(f"Could not create module spec for {init_file}")
                return None
                
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # Find BaseStrategy subclasses (but not BaseStrategy itself)
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (isinstance(attr, type) and 
                    issubclass(attr, BaseStrategy) and 
                    attr != BaseStrategy):
                    return attr
            
            if logger:
                logger.warn(f"No BaseStrategy subclass found in {init_file}")
            return None
            
        except Exception as e:
            if logger:
                logger.error(f"Failed to load strategy from {init_file}: {e}")
            return None