"""
U-M Shapiro Design Lab
Daniel Hou @2024

Game Manager for DiceMaster Central
Manages game discovery, strategy loading, and lifecycle management.
"""
import os
from typing import Dict, Optional, Type

import rclpy
from rclpy.node import Node
from rclpy.executors import MultiThreadedExecutor
from rclpy.callback_groups import ReentrantCallbackGroup

from lifecycle_msgs.srv import ChangeState
from lifecycle_msgs.msg import Transition

from dicemaster_central.config import dice_config
from dicemaster_central.games.strategy import BaseStrategy
from dicemaster_central.games.game import DiceGame

# Import service definitions when available
from dicemaster_central_msgs.srv import DiceGameControl


class GameManager(Node):
    """
    Main game manager that discovers and manages games using lifecycle management.
    Provides simplified APIs: start_game, stop_game, list_games.
    """
    
    def __init__(self, executor: MultiThreadedExecutor):
        super().__init__('game_manager')
        
        # Store executor reference for adding/removing nodes
        self.executor = executor
        
        # Initialize configuration
        self.game_config = dice_config.game_config
        
        # Storage for discovered items
        self.strategies: Dict[str, Type[BaseStrategy]] = {}
        self.games: Dict[str, DiceGame] = {}
        
        # Current active game and strategy node
        self.current_game_name: Optional[str] = None
        self.current_strategy_node: Optional[BaseStrategy] = None
        
        # ROS2 services
        self.callback_group = ReentrantCallbackGroup()
        self.game_control_service = self.create_service(
            DiceGameControl,
            'game_control',
            self.handle_game_control,
            callback_group=self.callback_group
        )

        # Discovery and initialization
        self.get_logger().info("Starting game manager initialization...")
        self._discover_strategies()
        self._discover_games() 
        
        # Auto-launch default game if specified (deferred to avoid deadlock)
        if self.game_config.default_game:
            if self.game_config.default_game in self.games:
                self.get_logger().info(f"Auto-launching default game: {self.game_config.default_game}")
                self._default_game_timer = self.create_timer(0.1, self._deferred_start_default_game)
            else:
                self.get_logger().info(f"{self.game_config.default_game} not in detected games")
        else:
            self.get_logger().info("No default game detected")
        self.get_logger().info("Game manager initialized successfully")
    
    def _deferred_start_default_game(self):
        """Deferred start of default game to avoid executor deadlock."""
        if hasattr(self, '_default_game_timer'):
            self.destroy_timer(self._default_game_timer)
            delattr(self, '_default_game_timer')
        self.start_game(self.game_config.default_game)
    
    def _transition(self, node_name: str, transition_id: int, wait_sec: float = 5.0) -> bool:
        """Helper to request lifecycle transitions on strategy nodes."""
        cli = self.create_client(ChangeState, f'{node_name}/change_state')
        if not cli.wait_for_service(timeout_sec=wait_sec):
            self.get_logger().error(f"change_state service not available for {node_name}")
            return False
        
        req = ChangeState.Request()
        req.transition.id = transition_id
        fut = cli.call_async(req)
        rclpy.spin_until_future_complete(self, fut, timeout_sec=wait_sec)
        res = fut.result()
        return bool(res and res.success)
    
    def _traverse_folder(self, folder_path: str, item_processor):
        """Generic folder traversal that calls item_processor for each subdirectory."""
        if not os.path.exists(folder_path):
            self.get_logger().warn(f"Folder does not exist: {folder_path}")
            return
            
        self.get_logger().info(f"Scanning folder: {folder_path}")
        
        for item in os.listdir(folder_path):
            if item.startswith('__'):
                continue
                
            item_path = os.path.join(folder_path, item)
            if os.path.isdir(item_path):
                item_processor(item_path, item)
    
    def _load_strategy(self, strategy_dir: str, strategy_name: str):
        """Load a single strategy using the verifier."""
        strategy_class = BaseStrategy.verify_and_load(strategy_dir, strategy_name, self.get_logger())
        if strategy_class:
            self.strategies[strategy_name] = strategy_class
            self.get_logger().info(f"Loaded strategy: {strategy_name} from {strategy_dir}")
    
    def _load_game(self, game_dir: str, game_name: str):
        """Load a single game using the verifier."""
        game = DiceGame.verify_and_load(game_dir, game_name, self.strategies, self.get_logger())
        if game:
            self.games[game_name] = game
            self.get_logger().info(f"Loaded game: {game_name} (strategy: {game.strategy_name})")
    
    def _discover_strategies(self):
        """Discover all available strategies from configured locations."""
        self.get_logger().info("Discovering strategies...")
        
        for strategy_location in self.game_config.default_strategy_locations:
            self._traverse_folder(strategy_location, self._load_strategy)
        
        self.get_logger().info(f"Discovered {len(self.strategies)} strategies: {list(self.strategies.keys())}")
    
    def _discover_games(self):
        """Discover all available games from configured locations."""
        self.get_logger().info("Discovering games...")
        
        for game_location in self.game_config.default_game_locations:
            self._traverse_folder(game_location, self._load_game)
        
        self.get_logger().info(f"Discovered {len(self.games)} games: {list(self.games.keys())}")
    
    def handle_game_control(self, request: DiceGameControl.Request, response: DiceGameControl.Response):
        """Handle game control service requests."""
        self.get_logger().info(f"Game control request: {request.command}")
        
        try:
            if request.command == "list":
                games = self.list_games()
                response.available_games = games
                response.current_game = self.current_game_name or ""
                response.success = True
                response.message = f"Found {len(games)} available games"
                
            elif request.command == "start":
                if not request.game_name:
                    response.success = False
                    response.message = "Game name required for start command"
                else:
                    success = self.start_game(request.game_name)
                    response.success = success
                    response.message = f"{'Started' if success else 'Failed to start'} game '{request.game_name}'"
                    
            elif request.command == "stop":
                success = self.stop_game()
                response.success = success
                response.message = f"{'Stopped' if success else 'Failed to stop'} current game"
                
            elif request.command == "restart":
                if self.current_game_name:
                    self.stop_game()
                    success = self.start_game(self.current_game_name)
                    response.success = success
                    response.message = f"{'Restarted' if success else 'Failed to restart'} game '{self.current_game_name}'"
                else:
                    response.success = False
                    response.message = "No current game to restart"
            else:
                response.success = False
                response.message = f"Unknown command: {request.command}"
                
        except Exception as e:
            self.get_logger().error(f"Error handling game control request: {e}")
            response.success = False
            response.message = f"Error: {str(e)}"
        
        response.current_game = self.current_game_name or ""
        return response
    
    def list_games(self) -> list:
        """List all available games."""
        return list(self.games.keys())
    
    def start_game(self, game_name: str) -> bool:
        """Start a game by creating and activating its strategy node."""
        if game_name not in self.games:
            self.get_logger().error(f"Game '{game_name}' not found")
            return False
        
        # Stop current game if running
        if self.current_strategy_node:
            if not self.stop_game():
                return False
        
        game = self.games[game_name]
        
        try:
            # Create strategy instance
            strategy_class = self.strategies[game.strategy_name]
            strategy_node = strategy_class(
                game_name=game.game_name,
                config_file=game.config_path,
                assets_path=game.assets_path
            )
            
            # 1) Put it under the executor before service calls
            self.executor.add_node(strategy_node)
            
            # 2) Configure → Activate lifecycle transitions
            node_name = strategy_node.get_name()
            if not self._transition(node_name, Transition.TRANSITION_CONFIGURE):
                self.get_logger().error(f"Configure failed for {node_name}")
                self.executor.remove_node(strategy_node)
                strategy_node.destroy_node()
                return False
            
            if not self._transition(node_name, Transition.TRANSITION_ACTIVATE):
                self.get_logger().error(f"Activate failed for {node_name}")
                # Best-effort cleanup
                self._transition(node_name, Transition.TRANSITION_CLEANUP)
                self.executor.remove_node(strategy_node)
                strategy_node.destroy_node()
                return False
            
            # Store references
            self.current_strategy_node = strategy_node
            self.current_game_name = game_name
            
            self.get_logger().info(f"Started game: {game_name} (strategy: {game.strategy_name})")
            return True
            
        except Exception as e:
            self.get_logger().error(f"Failed to start game '{game_name}': {e}")
            return False
    
    def stop_game(self) -> bool:
        """Stop the currently running game."""
        if not self.current_strategy_node:
            self.get_logger().info("No game currently running")
            return True
        
        node = self.current_strategy_node
        name = node.get_name()
        current_game = self.current_game_name
        
        ok = True
        try:
            # Try to gracefully transition down
            self._transition(name, Transition.TRANSITION_DEACTIVATE)
            self._transition(name, Transition.TRANSITION_CLEANUP)
            self._transition(name, Transition.TRANSITION_SHUTDOWN)
        except Exception as e:
            self.get_logger().warn(f"Graceful lifecycle shutdown failed for {name}: {e}")
            ok = False
        finally:
            # Always remove from executor and destroy
            try:
                self.executor.remove_node(node)
            except Exception:
                pass
            node.destroy_node()
            self.current_strategy_node = None
            self.current_game_name = None
        
        self.get_logger().info(f"Stopped game: {current_game}")
        return ok
    
    def destroy_node(self):
        """Clean shutdown of the game manager."""
        self.get_logger().info("Shutting down game manager...")
        self.stop_game()
        super().destroy_node()


def main(args=None):
    """Main entry point for the game manager."""
    rclpy.init(args=args)
    
    # Use MultiThreadedExecutor for service calls
    executor = MultiThreadedExecutor()
    game_manager = GameManager(executor)
    executor.add_node(game_manager)
    
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Error starting game manager: {e}")
    finally:
        if game_manager is not None:
            game_manager.destroy_node()
        if executor is not None:
            executor.shutdown()

if __name__ == '__main__':
    main()

