#!/usr/bin/env python3
"""
Test suite for Screen Media Service
Tests the complete pipeline from ROS message to screen display
"""

import os
import json
import time
import threading
from pathlib import Path

import rclpy
from rclpy.node import Node
from DiceMaster_Central.msg import ScreenMediaCmd
from dicemaster_central.constants import ContentType


class ScreenMediaTestPublisher(Node):
    """Test node that publishes media commands to test the screen service"""
    
    def __init__(self):
        super().__init__('screen_media_test_publisher')
        
        # Publisher for media commands
        self.publisher = self.create_publisher(
            ScreenMediaCmd,
            '/screen_media_cmd',
            10
        )
        
        # Test assets directory
        self.test_assets_dir = Path(__file__).parent / 'test_assets'
        self.test_assets_dir.mkdir(exist_ok=True)
        
        # Create test assets
        self._create_test_assets()
        
        # Test sequence
        self.test_sequence = [
            {'screen_id': 0, 'media_type': ContentType.TEXT, 'file_path': str(self.test_assets_dir / 'test_text.json')},
            {'screen_id': 1, 'media_type': ContentType.IMAGE, 'file_path': str(self.test_assets_dir / 'test_image.png')},
            {'screen_id': 2, 'media_type': ContentType.GIF, 'file_path': str(self.test_assets_dir / 'test_gif.gif')},
            {'screen_id': 0, 'media_type': ContentType.TEXT, 'file_path': str(self.test_assets_dir / 'test_text2.json')},
            {'screen_id': 3, 'media_type': ContentType.IMAGE, 'file_path': str(self.test_assets_dir / 'test_image.png')},
            {'screen_id': 4, 'media_type': ContentType.TEXT, 'file_path': str(self.test_assets_dir / 'test_text.json')},
        ]
        
        self.current_test_index = 0
        self.max_tests = len(self.test_sequence) * 2  # Run sequence twice
        
        # Timer for publishing test commands every 2 seconds
        self.timer = self.create_timer(2.0, self._publish_test_command)
        
        self.get_logger().info(f"Screen Media Test Publisher started with {len(self.test_sequence)} test cases")
        self.get_logger().info(f"Test assets created in: {self.test_assets_dir}")

    def _create_test_assets(self):
        """Create test media assets for testing"""
        
        # Create test text configurations
        text_config_1 = {
            "text_elements": [
                {
                    "text": "Hello World!",
                    "x": 10,
                    "y": 20,
                    "font_size": 16,
                    "color": [255, 255, 255],
                    "background_color": [0, 0, 0]
                },
                {
                    "text": "Screen Test",
                    "x": 10,
                    "y": 50,
                    "font_size": 12,
                    "color": [255, 0, 0],
                    "background_color": [0, 0, 0]
                }
            ],
            "background_color": [0, 0, 0],
            "screen_width": 128,
            "screen_height": 128
        }
        
        text_config_2 = {
            "text_elements": [
                {
                    "text": "Test Complete!",
                    "x": 5,
                    "y": 30,
                    "font_size": 14,
                    "color": [0, 255, 0],
                    "background_color": [0, 0, 0]
                }
            ],
            "background_color": [0, 0, 0],
            "screen_width": 128,
            "screen_height": 128
        }
        
        # Write text configs to JSON files
        with open(self.test_assets_dir / 'test_text.json', 'w') as f:
            json.dump(text_config_1, f, indent=2)
            
        with open(self.test_assets_dir / 'test_text2.json', 'w') as f:
            json.dump(text_config_2, f, indent=2)
        
        # Create a simple test image (solid color squares)
        try:
            from PIL import Image
            
            # Create a 128x128 test image with colored squares
            img = Image.new('RGB', (128, 128), color=(0, 0, 0))
            pixels = img.load()
            
            # Red square
            for x in range(10, 50):
                for y in range(10, 50):
                    pixels[x, y] = (255, 0, 0)
            
            # Green square
            for x in range(70, 110):
                for y in range(10, 50):
                    pixels[x, y] = (0, 255, 0)
                    
            # Blue square
            for x in range(10, 50):
                for y in range(70, 110):
                    pixels[x, y] = (0, 0, 255)
                    
            # White square
            for x in range(70, 110):
                for y in range(70, 110):
                    pixels[x, y] = (255, 255, 255)
            
            img.save(self.test_assets_dir / 'test_image.png')
            
            # Create a simple animated GIF (color cycling)
            frames = []
            colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0)]
            
            for color in colors:
                frame = Image.new('RGB', (128, 128), color=color)
                # Add a moving white dot
                pixels = frame.load()
                dot_x = 20 + colors.index(color) * 20
                for x in range(dot_x-5, dot_x+5):
                    for y in range(60, 70):
                        if 0 <= x < 128:
                            pixels[x, y] = (255, 255, 255)
                frames.append(frame)
            
            # Save as animated GIF
            frames[0].save(
                self.test_assets_dir / 'test_gif.gif',
                save_all=True,
                append_images=frames[1:],
                duration=500,  # 500ms per frame
                loop=0
            )
            
        except ImportError:
            self.get_logger().warn("PIL not available, creating placeholder image files")
            # Create placeholder files
            (self.test_assets_dir / 'test_image.png').touch()
            (self.test_assets_dir / 'test_gif.gif').touch()

    def _publish_test_command(self):
        """Publish the next test command"""
        if self.current_test_index >= self.max_tests:
            self.get_logger().info("All test cases completed!")
            self.timer.cancel()
            return
        
        # Get current test case
        test_case = self.test_sequence[self.current_test_index % len(self.test_sequence)]
        
        # Create and publish message
        msg = ScreenMediaCmd()
        msg.screen_id = test_case['screen_id']
        msg.media_type = test_case['media_type']
        msg.file_path = test_case['file_path']
        
        self.publisher.publish(msg)
        
        cycle = (self.current_test_index // len(self.test_sequence)) + 1
        case_num = (self.current_test_index % len(self.test_sequence)) + 1
        
        self.get_logger().info(
            f"Published test {self.current_test_index + 1}/{self.max_tests} "
            f"(Cycle {cycle}, Case {case_num}): "
            f"Screen {msg.screen_id}, Type {msg.media_type}, File {Path(msg.file_path).name}"
        )
        
        self.current_test_index += 1


class ScreenMediaTestRunner:
    """Test runner that coordinates the test execution"""
    
    def __init__(self):
        self.test_publisher = None
        self.test_thread = None
        
    def run_test(self, duration_seconds=30):
        """Run the screen media test for specified duration"""
        print(f"Starting Screen Media Service Test (duration: {duration_seconds}s)")
        print("This test will:")
        print("- Create test media assets (text configs, image, GIF)")
        print("- Publish media commands every 2 seconds")
        print("- Test all screen IDs with different media types")
        print("- Run the test sequence twice")
        print()
        
        # Initialize ROS2
        rclpy.init()
        
        try:
            # Create test publisher
            self.test_publisher = ScreenMediaTestPublisher()
            
            # Run test in thread with timeout
            def test_worker():
                rclpy.spin(self.test_publisher)
            
            self.test_thread = threading.Thread(target=test_worker, daemon=True)
            self.test_thread.start()
            
            # Wait for test completion or timeout
            start_time = time.time()
            while time.time() - start_time < duration_seconds:
                if not self.test_thread.is_alive():
                    break
                time.sleep(0.1)
            
            print("\nTest completed!")
            
        except KeyboardInterrupt:
            print("\nTest interrupted by user")
        except Exception as e:
            print(f"Test error: {e}")
        finally:
            if self.test_publisher:
                self.test_publisher.destroy_node()
            rclpy.shutdown()


def test_screen_media_service():
    """Main test function"""
    runner = ScreenMediaTestRunner()
    runner.run_test(duration_seconds=30)


if __name__ == '__main__':
    test_screen_media_service()
