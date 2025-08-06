"""
An example base strategy that selects a random screen ID and prints a notification to it every second

- It creates a timer
- randomly chooses a number out of all screen IDs (may need to import from dicemaster_central.config)
- and then uses notification_builder to build a notification to send to that screen with that screen ID
- publish the notification to screen_media_service
"""
import random
from dicemaster_central.games.strategy import BaseStrategy
from dicemaster_central.config import dice_config
from dicemaster_central.utils.notification_builder import build_info_notification
from dicemaster_central_msgs.msg import ScreenMediaCmd

class TestStrategy(BaseStrategy):
    """Example strategy that sends random notifications to screens every second."""
    
    _strategy_name = "pipeline_test"
    
    def __init__(self, game_name: str, config_file: str, assets_path: str, verbose: bool = False):
        super().__init__(game_name, config_file, assets_path, verbose)
        
        # Get available screen IDs from config
        self.available_screen_ids = list(dice_config.screen_configs.keys())
        self.get_logger().info(f"Available screen IDs: {self.available_screen_ids}")
        
        # Publisher for screen media commands
        self.screen_media_publisher = None
        self.notification_timer = None
        
        # Message counter for generating different content
        self.message_count = 0
    
    def start_strategy(self):
        """Start the strategy: create publisher and timer."""
        # Create publisher for screen media commands
        self.screen_media_publisher = self.create_publisher(
            ScreenMediaCmd,
            '/screen_media_cmd',
            10  # QoS depth
        )
        
        # Create timer that fires every second
        self.notification_timer = self.create_timer(1.0, self.send_random_notification)
        
        self.get_logger().info("TestStrategy started - sending notifications every second")
    
    def stop_strategy(self):
        """Stop the strategy: destroy timer and publisher."""
        if self.notification_timer:
            self.notification_timer.destroy()
            self.notification_timer = None
            
        if self.screen_media_publisher:
            self.screen_media_publisher.destroy()
            self.screen_media_publisher = None
            
        self.get_logger().info("TestStrategy stopped")
    
    def send_random_notification(self):
        """Timer callback to send a notification to a random screen."""
        if not self.available_screen_ids:
            self.get_logger().warn("No available screen IDs configured")
            return
            
        if not self.screen_media_publisher:
            self.get_logger().warn("Publisher not available")
            return
        
        # Select a random screen ID
        target_screen_id = random.choice(self.available_screen_ids)
        self.message_count += 1
        notification_content = f"Test message #{self.message_count} from TestStrategy"
        
        try:
            # Build notification using the updated notification builder
            notification_msg = build_info_notification(notification_content, target_screen_id)
            self.screen_media_publisher.publish(notification_msg)
            self.get_logger().info(
                f"Sent notification #{self.message_count} to screen {target_screen_id}: '{notification_content}'"
            )
            
        except Exception as e:
            self.get_logger().error(f"Failed to send notification: {e}")
