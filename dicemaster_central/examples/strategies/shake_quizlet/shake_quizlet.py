"""
Example strategy that loads a bunch of `quizlet` cards from assets, each with a unique folder name 
  - each of which has a "answer.json" file for the bottom of the display
  - and a few (>=4) images as hints in the images/ sub-folder

  At the top, a fixed `question.json` describes the text of the question: Qu'est-ce que c'est en français?

This strategy subscribes to the motion_detection/ topic and shuffles to a different question if there is a shake
After each new_question, it 
  - starts a timer of 500ms for shake to stabilize
  - prints the question on the top screen
  - prints the answer to the bottom screen
  - prints the images/gif to the four screens that are not top or bottom, in random order. 

An example file structure (examples/games/chinese_quizlet):
├── computer
│   ├── images
│   │   ├── computer_4.jpg
│   │   ├── computer_3.jpg
│   │   ├── computer_1.jpg
│   │   └── computer_2.jpg
│   └── answer.json
│   └── quesetion.json
├── dog
│   ├── images
│   │   ├── dog_3.jpg
│   │   ├── dog_4.jpg
│   │   ├── dog_2.jpg
│   │   └── dog_1.jpg
│   └── answer.json
│   └── quesetion.json
└── cat
    ├── images
    │   ├── cat_1.jpg
    │   ├── cat_4.jpg
    │   ├── cat_2.jpg
    │   └── cat_3.jpg
    └── answer.json
    └── question.json
"""

import os
import random

from dicemaster_central.games.strategy import BaseStrategy
from dicemaster_central.config import dice_config
from dicemaster_central.constants import ContentType
from dicemaster_central_msgs.msg import ScreenMediaCmd, MotionDetection, ChassisOrientation, ScreenPose


class ShakeQuizletStrategy(BaseStrategy):
    """
    Shake Quizlet Strategy - A language learning game activated by shaking the dice.
    
    Features:
    - Loads quizlet cards from assets (each with answer.json and images/)
    - Displays question on top screen, answer on bottom screen
    - Shows hint images on side screens
    - Changes to new question when shake is detected
    - Implements stabilization timer after shake detection
    """
    
    _strategy_name = "shake_quizlet"
    
    def __init__(self, game_name: str, config_file: str, assets_path: str, verbose: bool = False):
        super().__init__(game_name, config_file, assets_path, verbose)
        
        # Screen management
        self.available_screen_ids = list(dice_config.screen_configs.keys())
        self.top_screen_id = None
        self.bottom_screen_id = None
        self.side_screen_ids = []
        
        # Quizlet data
        self.quizlet_cards = []
        self.current_card_index = 0
        self.question_file_path = None
        
        # State management
        self.shake_stabilization_timer = None
        self.is_stabilizing = False
        self.last_shake_time = 0.0
        
        # ROS components (will be created in start_strategy)
        self.screen_media_publisher = None
        self.motion_subscription = None
        self.chassis_subscription = None
        self.screen_pose_subscription = None
        
        # Load quizlet cards from assets
        self._load_quizlet_cards()
        
        self.get_logger().info(f"ShakeQuizletStrategy initialized with {len(self.quizlet_cards)} cards")
    
    def _load_quizlet_cards(self):
        """Load all quizlet cards from the assets directory."""
        self.quizlet_cards = []
        
        # Load question file
        question_path = os.path.join(self._assets_path, 'question.json')
        if os.path.exists(question_path):
            self.question_file_path = question_path
        else:
            self.get_logger().warn(f"Question file not found at {question_path}")
        
        # Scan for card directories
        if not os.path.exists(self._assets_path):
            self.get_logger().error(f"Assets path does not exist: {self._assets_path}")
            return
        
        for item in os.listdir(self._assets_path):
            item_path = os.path.join(self._assets_path, item)
            
            # Skip files (like question.json)
            if not os.path.isdir(item_path):
                continue
            
            # Look for answer.json and images/ directory
            answer_path = os.path.join(item_path, 'answer.json')
            images_path = os.path.join(item_path, 'images')
            
            if not os.path.exists(answer_path):
                self.get_logger().warn(f"No answer.json found for card '{item}'")
                continue
            
            if not os.path.exists(images_path):
                self.get_logger().warn(f"No images/ directory found for card '{item}'")
                continue
            
            # Load image files
            image_files = []
            for img_file in os.listdir(images_path):
                if img_file.lower().endswith(('.jpg', '.jpeg', '.png')):
                    image_files.append(os.path.join(images_path, img_file))
            
            if len(image_files) < 4:
                self.get_logger().warn(f"Card '{item}' has only {len(image_files)} images, need at least 4")
                continue
            
            card_data = {
                'name': item,
                'answer_path': answer_path,
                'image_paths': image_files
            }
            self.quizlet_cards.append(card_data)
            
        self.get_logger().info(f"Loaded {len(self.quizlet_cards)} quizlet cards")
        
        # Shuffle cards for random order
        random.shuffle(self.quizlet_cards)
    
    def _update_screen_assignments(self, chassis_msg: ChassisOrientation):
        """Update which screens are top/bottom based on chassis orientation."""
        self.top_screen_id = chassis_msg.top_screen_id
        self.bottom_screen_id = chassis_msg.bottom_screen_id
        
        # Side screens are all screens except top and bottom
        self.side_screen_ids = [
            screen_id for screen_id in self.available_screen_ids 
            if screen_id != self.top_screen_id and screen_id != self.bottom_screen_id
        ]
        
        self.get_logger().info(f"Screen assignment updated - Top: {self.top_screen_id}, Bottom: {self.bottom_screen_id}, Sides: {self.side_screen_ids}")
    
    def _display_current_question(self):
        """Display the current question and answer on appropriate screens."""
        if not self.quizlet_cards:
            self.get_logger().warn("No quizlet cards loaded")
            return
        
        if self.top_screen_id is None or self.bottom_screen_id is None:
            self.get_logger().warn("Screen assignments not ready")
            return
        
        if self.screen_media_publisher is None:
            self.get_logger().warn("Screen media publisher not initialized")
            return
        
        current_card = self.quizlet_cards[self.current_card_index]
        
        # Display question on top screen
        if self.question_file_path:
            question_msg = ScreenMediaCmd()
            question_msg.screen_id = self.top_screen_id
            question_msg.media_type = ContentType.TEXT
            question_msg.file_path = self.question_file_path
            self.screen_media_publisher.publish(question_msg)
        
        # Display answer on bottom screen
        answer_msg = ScreenMediaCmd()
        answer_msg.screen_id = self.bottom_screen_id
        answer_msg.media_type = ContentType.TEXT
        answer_msg.file_path = current_card['answer_path']
        self.screen_media_publisher.publish(answer_msg)
        
        # Display hint images on side screens
        self._display_hint_images(current_card)
        
        self.get_logger().info(f"Displayed question for card '{current_card['name']}'")
    
    def _display_hint_images(self, card_data):
        """Display hint images on side screens in random order."""
        if not self.side_screen_ids or len(self.side_screen_ids) < 4:
            self.get_logger().warn("Not enough side screens for hint images")
            return
        
        if self.screen_media_publisher is None:
            self.get_logger().warn("Screen media publisher not initialized")
            return
        
        # Select up to 4 images randomly
        selected_images = random.sample(card_data['image_paths'], min(4, len(card_data['image_paths'])))
        
        # Assign to side screens (shuffle for randomness)
        available_sides = self.side_screen_ids.copy()
        random.shuffle(available_sides)
        
        for i, image_path in enumerate(selected_images):
            if i >= len(available_sides):
                break
                
            screen_id = available_sides[i]
            image_msg = ScreenMediaCmd()
            image_msg.screen_id = screen_id
            image_msg.media_type = ContentType.IMAGE
            image_msg.file_path = image_path
            self.screen_media_publisher.publish(image_msg)
        
        self.get_logger().info(f"Displayed {len(selected_images)} hint images on side screens")
    
    def _next_question(self):
        """Move to the next question in the deck."""
        if not self.quizlet_cards:
            return
        
        self.current_card_index = (self.current_card_index + 1) % len(self.quizlet_cards)
        self.get_logger().info(f"Moved to question {self.current_card_index + 1} of {len(self.quizlet_cards)}")
        
        # Display the new question after stabilization timer
        self._start_stabilization_timer()
    
    def _start_stabilization_timer(self):
        """Start 500ms stabilization timer after shake detection."""
        if self.shake_stabilization_timer:
            self.shake_stabilization_timer.cancel()
        
        self.is_stabilizing = True
        self.shake_stabilization_timer = self.create_timer(0.5, self._on_stabilization_complete)
        self.get_logger().info("Started 500ms stabilization timer")
    
    def _on_stabilization_complete(self):
        """Called when stabilization timer completes."""
        if self.shake_stabilization_timer:
            self.shake_stabilization_timer.cancel()
            self.shake_stabilization_timer = None
        
        self.is_stabilizing = False
        self._display_current_question()
        self.get_logger().info("Stabilization complete - displaying new question")
    
    def _motion_callback(self, msg: MotionDetection):
        """Handle motion detection messages - look for shake events."""
        if msg.shaking and not self.is_stabilizing:
            current_time = self.get_clock().now().nanoseconds / 1e9
            
            # Debounce shake detection (minimum 1 second between shakes)
            if current_time - self.last_shake_time > 1.0:
                self.last_shake_time = current_time
                self.get_logger().info("Shake detected - changing question")
                self._next_question()
    
    def _chassis_callback(self, msg: ChassisOrientation):
        """Handle chassis orientation updates."""
        self._update_screen_assignments(msg)
        
        # If we're not stabilizing, update the display
        if not self.is_stabilizing:
            self._display_current_question()
    
    def _screen_pose_callback(self, msg: ScreenPose):
        """Handle individual screen pose updates (optional - for future use)."""
        # This could be used for screen-specific rotation handling
        pass
    
    def start_strategy(self):
        """Start the shake quizlet strategy."""
        # Create publisher for screen media commands
        self.screen_media_publisher = self.create_publisher(
            ScreenMediaCmd,
            '/screen_media_cmd',
            10
        )
        
        # Subscribe to motion detection
        self.motion_subscription = self.create_subscription(
            MotionDetection,
            '/dice_hw/imu/motion',
            self._motion_callback,
            10
        )
        
        # Subscribe to chassis orientation
        self.chassis_subscription = self.create_subscription(
            ChassisOrientation,
            '/dice_hw/chassis/orientation',
            self._chassis_callback,
            10
        )
        
        # Subscribe to screen poses (optional)
        self.screen_pose_subscription = self.create_subscription(
            ScreenPose,
            '/dice_hw/chassis/screen_pose',
            self._screen_pose_callback,
            10
        )
        
        self.get_logger().info("ShakeQuizletStrategy started - waiting for orientation data")
        
        # If we already have screen assignments, display the first question
        if self.top_screen_id is not None and self.bottom_screen_id is not None:
            self._display_current_question()
    
    def stop_strategy(self):
        """Stop the shake quizlet strategy."""
        # Cancel stabilization timer
        if self.shake_stabilization_timer:
            self.shake_stabilization_timer.cancel()
            self.shake_stabilization_timer = None
        
        # Destroy subscribers
        if self.motion_subscription:
            self.motion_subscription.destroy()
            self.motion_subscription = None
        
        if self.chassis_subscription:
            self.chassis_subscription.destroy()
            self.chassis_subscription = None
        
        if self.screen_pose_subscription:
            self.screen_pose_subscription.destroy()
            self.screen_pose_subscription = None
        
        # Destroy publisher
        if self.screen_media_publisher:
            self.screen_media_publisher.destroy()
            self.screen_media_publisher = None
        
        self.get_logger().info("ShakeQuizletStrategy stopped")

