"""
An example base strategy that selects screen IDs in order and prints a notification to them every second

- It creates a timer
- cycles through screen IDs in order (may need to import from dicemaster_central.config)
- and then uses notification_builder to build a notification to send to that screen with that screen ID
- publish the notification to screen_{id}_cmd
"""
from dicemaster_central.games.strategy import BaseStrategy
from dicemaster_central.config import dice_config
from dicemaster_central.utils.notification_builder import build_info_notification
from dicemaster_central_msgs.msg import ScreenMediaCmd, ScreenPose

class TestStrategy(BaseStrategy):
    """Example strategy that sends notifications to screens in order every second."""
    
    _strategy_name = "pipeline_test"
    
    def __init__(self, game_name: str, config_file: str, assets_path: str, verbose: bool = False):
        super().__init__(game_name, config_file, assets_path, verbose)
        
        # Get available screen IDs from config
        self.available_screen_ids = list(dice_config.screen_configs.keys())
        self.get_logger().info(f"Available screen IDs: {self.available_screen_ids}")
        
        # Publishers for screen media commands (created as needed)
        self.screen_publishers = {}
        self.notification_timer = None
        
        # Message counter for generating different content
        self.message_count = 0
        
        # Index for cycling through screen IDs in order
        self.current_screen_index = 0
        
        # Track chassis information for each screen
        self.screen_poses = {}  # screen_id -> ScreenPose
        self.pose_subscriptions = {}
        
        # Subscribe to chassis pose topics for all available screens
        self._setup_pose_subscriptions()
    
    def _get_screen_publisher(self, screen_id: int):
        """Get or create publisher for a specific screen ID"""
        if screen_id not in self.screen_publishers:
            topic_name = f'/screen_{screen_id}_cmd'
            self.screen_publishers[screen_id] = self.create_publisher(
                ScreenMediaCmd,
                topic_name,
                10
            )
            # self.get_logger().info(f"Created publisher for {topic_name}")
        return self.screen_publishers[screen_id]
    
    def _setup_pose_subscriptions(self):
        """Setup subscriptions to chassis pose topics for all available screens"""
        for screen_id in self.available_screen_ids:
            topic_name = f'/chassis/screen_{screen_id}_pose'
            subscription = self.create_subscription(
                ScreenPose,
                topic_name,
                self._create_pose_callback(screen_id),
                10
            )
            self.pose_subscriptions[screen_id] = subscription
            # Initialize with default values
            self.screen_poses[screen_id] = None
            self.get_logger().info(f"Subscribed to {topic_name}")
    
    def _create_pose_callback(self, screen_id: int):
        """Create a pose callback for a specific screen ID"""
        def callback(msg: ScreenPose):
            if msg.screen_id == screen_id:
                self.screen_poses[screen_id] = msg
        return callback
    
    def start_strategy(self):
        """Start the strategy: create timer."""
        # Create timer that fires every second
        self.notification_timer = self.create_timer(0.1, self.send_random_notification)
        self.get_logger().info("TestStrategy started - sending notifications to screens in order every second")
    
    def stop_strategy(self):
        """Stop the strategy: destroy timer and publishers."""
        if self.notification_timer:
            self.destroy_timer(self.notification_timer)
            self.notification_timer = None
            
        # Destroy all screen publishers
        for screen_id, publisher in self.screen_publishers.items():
            if publisher:
                self.destroy_publisher(publisher)
        self.screen_publishers.clear()
        
        # Clean up pose subscriptions
        for screen_id, subscription in self.pose_subscriptions.items():
            if subscription:
                self.destroy_subscription(subscription)
        self.pose_subscriptions.clear()
        self.screen_poses.clear()
            
        self.get_logger().info("TestStrategy stopped")
    
    def send_random_notification(self):
        """Timer callback to send a notification to screens in order."""
        if not self.available_screen_ids:
            self.get_logger().warn("No available screen IDs configured")
            return
        
        # Select the next screen ID in order
        target_screen_id = self.available_screen_ids[self.current_screen_index]
        self.current_screen_index = (self.current_screen_index + 1) % len(self.available_screen_ids)
        
        self.message_count += 1
        
        # Get chassis information for this screen
        pose_info = self.screen_poses.get(target_screen_id)
        if pose_info:
            # Convert rotation enum to degrees for display
            rotation_degrees = pose_info.rotation * 90
            facing_status = "ON TOP" if pose_info.is_facing_up else "NOT ON TOP"
            chassis_info = f" | Rot: {rotation_degrees}° | {facing_status}"
        else:
            chassis_info = " | Chassis: Unknown"
        
        notification_content = f"Test #{self.message_count} to screen {target_screen_id}{chassis_info}"
        
        try:
            # Build notification using the updated notification builder
            notification_msg = build_info_notification(notification_content, target_screen_id)
            
            # Get the appropriate publisher for this screen and publish
            publisher = self._get_screen_publisher(target_screen_id)
            publisher.publish(notification_msg)
            
            # self.get_logger().info(
            #     f"Sent notification #{self.message_count} to screen {target_screen_id}: '{notification_content}'"
            # )
            
        except Exception as e:
            self.get_logger().error(f"Failed to send notification: {e}")
