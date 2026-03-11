"""
Example strategy that loads a bunch of `quizlet` cards from assets, each with a unique folder name 
  - each of which has a "answer.json" file for the bottom of the display
  - and a few (>=4) images as hints in the images/ sub-folder

  At the top, a fixed `question.json` describes the text of the question: Qu'est-ce que c'est en français?

This strategy subscribes to the motion_detection/ topic and shuffles to a different question if there are 3 consecutive shake detections
After each new_question, it 
  - starts a 3-second stop period where additional motion is ignored
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
    - Changes to new question when 3 consecutive shake detections occur
    - Implements 3-second stop period after triggering to ignore additional motion
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
        self.shake_history = []  # Track last 3 shake states
        self.last_trigger_time = 0.0
        self.stop_period_duration = 3.0  # 3 seconds stop period
        
        # ROS components (will be created in start_strategy)
        self.screen_publishers = {}
        self.motion_subscription = None
        self.chassis_subscription = None
        
        # Load quizlet cards from assets
        self._load_quizlet_cards()
        self.displayed_initial = False
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
                if img_file.lower().endswith(('.jpg', '.jpeg', '.png', '.gif.d')):
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
    
    def _get_screen_publisher(self, screen_id: int):
        """Get or create publisher for a specific screen ID"""
        if screen_id not in self.screen_publishers:
            topic_name = f'/screen_{screen_id}_cmd'
            self.screen_publishers[screen_id] = self.create_publisher(
                ScreenMediaCmd,
                topic_name,
                10
            )
            self.get_logger().info(f"Created publisher for {topic_name}")
        return self.screen_publishers[screen_id]
    
    def _update_screen_assignments(self, chassis_msg: ChassisOrientation):
        """Update which screens are top/bottom based on chassis orientation."""
        self.top_screen_id = chassis_msg.top_screen_id
        self.bottom_screen_id = chassis_msg.bottom_screen_id
        
        # Side screens are all screens except top and bottom
        self.side_screen_ids = [
            screen_id for screen_id in self.available_screen_ids 
            if screen_id != self.top_screen_id and screen_id != self.bottom_screen_id
        ]
        
        # self.get_logger().info(f"Screen assignment updated - Top: {self.top_screen_id}, Bottom: {self.bottom_screen_id}, Sides: {self.side_screen_ids}")
    
    def _display_current_question(self):
        """Display the current question and answer on appropriate screens."""
        if not self.quizlet_cards:
            self.get_logger().warn("No quizlet cards loaded")
            return
        
        if self.top_screen_id is None or self.bottom_screen_id is None:
            self.get_logger().warn("Screen assignments not ready")
            return
        
        current_card = self.quizlet_cards[self.current_card_index]
        
        # Display question on top screen
        if self.question_file_path:
            question_msg = ScreenMediaCmd()
            question_msg.screen_id = self.top_screen_id
            question_msg.media_type = ContentType.TEXT
            question_msg.file_path = self.question_file_path
            
            # Get publisher for top screen and publish
            top_publisher = self._get_screen_publisher(self.top_screen_id)
            top_publisher.publish(question_msg)
        
        # Display answer on bottom screen
        answer_msg = ScreenMediaCmd()
        answer_msg.screen_id = self.bottom_screen_id
        answer_msg.media_type = ContentType.TEXT
        answer_msg.file_path = current_card['answer_path']
        
        # Get publisher for bottom screen and publish
        bottom_publisher = self._get_screen_publisher(self.bottom_screen_id)
        bottom_publisher.publish(answer_msg)
        
        # Display hint images on side screens
        self._display_hint_images(current_card)
        self.get_logger().info(f"Displayed question for card '{current_card['name']}'")
    
    def _display_hint_images(self, card_data):
        """Display hint images on side screens in random order."""
        if not self.side_screen_ids or len(self.side_screen_ids) < 4:
            self.get_logger().warn("Not enough side screens for hint images")
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
            image_msg.media_type = ContentType.GIF if image_path.lower().endswith(('.gif.d')) else ContentType.IMAGE
            image_msg.file_path = image_path
            
            # Get publisher for this screen and publish
            screen_publisher = self._get_screen_publisher(screen_id)
            screen_publisher.publish(image_msg)
        
        self.get_logger().info(f"Displayed {len(selected_images)} hint images on side screens")
    
    def _next_question(self):
        """Move to the next question in the deck."""
        if not self.quizlet_cards:
            return
        
        self.current_card_index = (self.current_card_index + 1) % len(self.quizlet_cards)
        self.get_logger().info(f"Moved to question {self.current_card_index + 1} of {len(self.quizlet_cards)}")
        
        # Display the new question immediately
        self._display_current_question()
    
    def _motion_callback(self, msg: MotionDetection):
        """Handle motion detection messages - look for consecutive shake events."""
        current_time = self.get_clock().now().nanoseconds / 1e9
        
        # Check if we're in the stop period
        if current_time - self.last_trigger_time < self.stop_period_duration:
            return  # Ignore all motion during stop period
        
        # Add current shake state to history
        self.shake_history.append(msg.shaking)
        
        # Keep only the last 3 states
        if len(self.shake_history) > 3:
            self.shake_history.pop(0)
        
        # Check if we have 3 consecutive True shaking states
        if len(self.shake_history) == 3 and all(self.shake_history):
            self.last_trigger_time = current_time
            self.shake_history = []  # Reset history after trigger
            self.get_logger().info("3 consecutive shakes detected - changing question")
            self._next_question()
    
    def _chassis_callback(self, msg: ChassisOrientation):
        """Handle chassis orientation updates."""
        self._update_screen_assignments(msg)
        
        # Display initial question only if we haven't displayed anything yet
        if not self.displayed_initial and self.top_screen_id is not None and self.bottom_screen_id is not None:
            self.get_logger().info(f"Displaying initial question on screens {self.top_screen_id} and {self.bottom_screen_id}")
            self._display_current_question()
            self.displayed_initial = True

    def start_strategy(self):
        """Start the shake quizlet strategy."""
        # Subscribe to motion detection
        self.motion_subscription = self.create_subscription(
            MotionDetection,
            '/imu/motion',
            self._motion_callback,
            10
        )
        
        # Subscribe to chassis orientation
        self.chassis_subscription = self.create_subscription(
            ChassisOrientation,
            '/chassis/orientation',
            self._chassis_callback,
            10
        )
        
        self.get_logger().info("ShakeQuizletStrategy started - waiting for orientation data")

    def stop_strategy(self):
        """Stop the shake quizlet strategy."""
        # Reset shake detection state
        self.shake_history = []
        
        # Destroy subscribers
        if self.motion_subscription:
            self.motion_subscription.destroy()
            self.motion_subscription = None
        
        if self.chassis_subscription:
            self.chassis_subscription.destroy()
            self.chassis_subscription = None
        
        # Destroy publishers
        for publisher in self.screen_publishers.values():
            if publisher:
                publisher.destroy()
        self.screen_publishers = {}
        
        self.get_logger().info("ShakeQuizletStrategy stopped")

