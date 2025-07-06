import os
import json
import random
from pathlib import Path
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, validator

import rclpy
from rclpy.node import Node
from std_msgs.msg import String, Bool
from sensor_msgs.msg import Image
import cv2
from cv_bridge import CvBridge


class ContentFiles(BaseModel):
    """Pydantic model to validate and load content files from directory structure"""
    images: List[str] = Field(default_factory=list, description="List of image file paths")
    gifs: List[str] = Field(default_factory=list, description="List of gif file paths")
    texts: List[str] = Field(default_factory=list, description="List of text file paths")
    
    @validator('images', 'gifs', each_item=True)
    def validate_media_files_exist(cls, v):
        if not os.path.exists(v):
            raise ValueError(f"File does not exist: {v}")
        return v
    
    @validator('texts', each_item=True)
    def validate_text_files_exist(cls, v):
        if not os.path.exists(v):
            raise ValueError(f"Text file does not exist: {v}")
        return v
    
    @classmethod
    def load_from_directory(cls, content_dir: str) -> 'ContentFiles':
        """Load content files from a directory structure"""
        content_path = Path(content_dir)
        
        # Supported file extensions
        image_exts = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff'}
        gif_exts = {'.gif'}
        text_exts = {'.txt'}
        
        images = []
        gifs = []
        texts = []
        
        if content_path.exists():
            for file_path in content_path.rglob('*'):
                if file_path.is_file():
                    ext = file_path.suffix.lower()
                    if ext in image_exts:
                        images.append(str(file_path))
                    elif ext in gif_exts:
                        gifs.append(str(file_path))
                    elif ext in text_exts:
                        texts.append(str(file_path))
        
        return cls(images=images, gifs=gifs, texts=texts)


class RandomTimeStrategy(Node):
    """ROS2 strategy node that responds to shaking with random content on random screens"""
    
    def __init__(self, content_directory: str = "content"):
        super().__init__('random_time_strategy')
        
        # Load and validate content files
        self.content_files = ContentFiles.load_from_directory(content_directory)
        self.get_logger().info(f"Loaded {len(self.content_files.images)} images, "
                              f"{len(self.content_files.gifs)} gifs, "
                              f"{len(self.content_files.texts)} texts")
        
        # Initialize CV bridge for image handling
        self.cv_bridge = CvBridge()
        
        # Screen IDs and publishers
        self.screen_ids: List[int] = []
        self.screen_publishers: Dict[int, Dict[str, Any]] = {}
        
        # Subscribers
        self.shaking_sub = self.create_subscription(
            Bool,
            '/dice_imu/shaking',
            self.shaking_callback,
            10
        )
        
        self.robot_description_sub = self.create_subscription(
            String,
            '/robot_description',
            self.robot_description_callback,
            10
        )
        
        # State tracking
        self.is_shaking = False
        self.last_shaking_time = self.get_clock().now()
        
        self.get_logger().info("RandomTimeStrategy node initialized")
    
    def robot_description_callback(self, msg: String):
        """Parse robot description to get screen IDs and setup publishers"""
        try:
            description_data = json.loads(msg.data)
            new_screen_ids = description_data.get('screen_ids', [])
            
            if new_screen_ids != self.screen_ids:
                self.screen_ids = new_screen_ids
                self.setup_screen_publishers()
                self.get_logger().info(f"Updated screen IDs: {self.screen_ids}")
                
        except json.JSONDecodeError:
            self.get_logger().error("Failed to parse robot description JSON")
    
    def setup_screen_publishers(self):
        """Setup publishers for each screen"""
        self.screen_publishers.clear()
        
        for screen_id in self.screen_ids:
            self.screen_publishers[screen_id] = {
                'text': self.create_publisher(String, f'/screen_{screen_id}/text', 10),
                'image': self.create_publisher(Image, f'/screen_{screen_id}/image', 10),
                'gif': self.create_publisher(String, f'/screen_{screen_id}/gif', 10)
            }
    
    def shaking_callback(self, msg: Bool):
        """Handle shaking signal - trigger random content display"""
        current_time = self.get_clock().now()
        
        # Detect shaking start (transition from False to True)
        if msg.data and not self.is_shaking:
            self.is_shaking = True
            self.last_shaking_time = current_time
            self.display_random_content()
            
        elif not msg.data:
            self.is_shaking = False
    
    def display_random_content(self):
        """Display random content on a random screen"""
        if not self.screen_ids:
            self.get_logger().warn("No screen IDs available")
            return
        
        # Select random screen
        screen_id = random.choice(self.screen_ids)
        
        # Collect all available content
        all_content = []
        
        if self.content_files.images:
            all_content.extend([('image', path) for path in self.content_files.images])
        if self.content_files.gifs:
            all_content.extend([('gif', path) for path in self.content_files.gifs])
        if self.content_files.texts:
            all_content.extend([('text', path) for path in self.content_files.texts])
        
        if not all_content:
            self.get_logger().warn("No content available to display")
            return
        
        # Select random content
        content_type, content_path = random.choice(all_content)
        
        try:
            if content_type == 'text':
                self.publish_text_content(screen_id, content_path)
            elif content_type == 'image':
                self.publish_image_content(screen_id, content_path)
            elif content_type == 'gif':
                self.publish_gif_content(screen_id, content_path)
                
            self.get_logger().info(f"Displayed {content_type} on screen {screen_id}: {content_path}")
            
        except Exception as e:
            self.get_logger().error(f"Failed to display content: {e}")
    
    def publish_text_content(self, screen_id: int, text_path: str):
        """Publish text content to screen"""
        with open(text_path, 'r', encoding='utf-8') as f:
            text_content = f.read().strip()
        
        msg = String()
        msg.data = text_content
        self.screen_publishers[screen_id]['text'].publish(msg)
    
    def publish_image_content(self, screen_id: int, image_path: str):
        """Publish image content to screen"""
        cv_image = cv2.imread(image_path)
        if cv_image is None:
            raise ValueError(f"Could not load image: {image_path}")
        
        ros_image = self.cv_bridge.cv2_to_imgmsg(cv_image, encoding="bgr8")
        self.screen_publishers[screen_id]['image'].publish(ros_image)
    
    def publish_gif_content(self, screen_id: int, gif_path: str):
        """Publish gif path to screen (assuming screen handles gif playback)"""
        msg = String()
        msg.data = gif_path
        self.screen_publishers[screen_id]['gif'].publish(msg)


def main(args=None):
    rclpy.init(args=args)
    
    # Get content directory from parameter or use default
    import sys
    content_dir = sys.argv[1] if len(sys.argv) > 1 else "content"
    
    try:
        strategy_node = RandomTimeStrategy(content_dir)
        rclpy.spin(strategy_node)
    except Exception as e:
        print(f"Error running strategy: {e}")
    finally:
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
