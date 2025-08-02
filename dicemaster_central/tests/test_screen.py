#!/usr/bin/env python3
"""
Simplified test for Screen Media Service
Tests the complete pipeline from ROS message to screen display using existing test assets

Two test configurations available:
1. 'single' - Tests only screen ID 1 (recommended when you have only one screen connected)
2. 'multi' - Tests screen IDs 1, 2, and 4 (use when you have multiple screens)

Usage:
    python3 test_screen.py single    # Test single screen (default)
    python3 test_screen.py multi     # Test multiple screens
    python3 test_screen.py           # Defaults to single screen test
"""

from pathlib import Path

import rclpy
from rclpy.node import Node
from dicemaster_central_msgs.msg import ScreenMediaCmd
from dicemaster_central.constants import ContentType
from dicemaster_central.hw.screen.screen_media_service import ScreenMediaService


class ScreenMediaTestPublisher(Node):
    """Test node that publishes media commands to test the screen service"""
    
    def __init__(self, test_config='single'):
        super().__init__('screen_media_test_publisher')
        
        # Publisher for media commands
        self.publisher = self.create_publisher(
            ScreenMediaCmd,
            '/screen_media_cmd',
            10
        )
        
        # Test assets directory (use existing assets)
        self.test_assets_dir = Path(__file__).parent / 'test_assets'
        
        # Test configurations
        if test_config == 'single':
            # Single screen test (screen ID 1 only)
            self.test_sequence = [
                {'screen_id': 1, 'media_type': ContentType.TEXT, 'file_path': str(self.test_assets_dir / 'hey_guys.json')},
                {'screen_id': 1, 'media_type': ContentType.IMAGE, 'file_path': str(self.test_assets_dir / 'cat_480.jpg')},
                {'screen_id': 1, 'media_type': ContentType.GIF, 'file_path': str(self.test_assets_dir / 'miss-you.gif.d')},
                # {'screen_id': 1, 'media_type': ContentType.TEXT, 'file_path': str(self.test_assets_dir / 'hey_guys.json')},
            ]
            self.get_logger().info("Running SINGLE SCREEN test configuration (Screen ID 1 only)")
        elif test_config == 'multi':
            # Multiple screens test (screen IDs 1, 2, 4)
            self.test_sequence = [
                {'screen_id': 1, 'media_type': ContentType.TEXT, 'file_path': str(self.test_assets_dir / 'hey_guys.json')},
                {'screen_id': 2, 'media_type': ContentType.IMAGE, 'file_path': str(self.test_assets_dir / 'cat_480.jpg')},
                {'screen_id': 4, 'media_type': ContentType.GIF, 'file_path': str(self.test_assets_dir / 'miss-you.gif.d')},
                {'screen_id': 1, 'media_type': ContentType.IMAGE, 'file_path': str(self.test_assets_dir / 'cat_480.jpg')},
                {'screen_id': 2, 'media_type': ContentType.TEXT, 'file_path': str(self.test_assets_dir / 'hey_guys.json')},
                {'screen_id': 4, 'media_type': ContentType.IMAGE, 'file_path': str(self.test_assets_dir / 'cat_480.jpg')},
            ]
            self.get_logger().info("Running MULTI SCREEN test configuration (Screen IDs 1, 2, 4)")
        else:
            raise ValueError(f"Invalid test_config: {test_config}. Use 'single' or 'multi'")
        
        self.current_test_index = 0
        self.max_tests = len(self.test_sequence)
        
        # Timer for publishing test commands every 3 seconds
        self.timer = self.create_timer(3.0, self._publish_test_command)
        
        self.get_logger().info(f"Screen Media Test Publisher started with {len(self.test_sequence)} test cases")
        self.get_logger().info(f"Using test assets from: {self.test_assets_dir}")

    def _publish_test_command(self):
        """Publish the next test command"""
        if self.current_test_index >= self.max_tests:
            self.get_logger().info("All test cases completed!")
            self.timer.cancel()
            return
        
        # Get current test case
        test_case = self.test_sequence[self.current_test_index]
        
        # Create and publish message
        msg = ScreenMediaCmd()
        msg.screen_id = test_case['screen_id']
        msg.media_type = test_case['media_type']
        msg.file_path = test_case['file_path']
        
        self.publisher.publish(msg)
        
        self.get_logger().info(
            f"Published test {self.current_test_index + 1}/{self.max_tests}: "
            f"Screen {msg.screen_id}, Type {msg.media_type}, File {Path(msg.file_path).name}"
        )
        
        self.current_test_index += 1


def test_screen_media_service(test_config='single'):
    """Main test function that runs both service and test publisher
    
    Args:
        test_config (str): 'single' for single screen test (ID 1) or 'multi' for multiple screens (IDs 1,2,4)
    """
    print(f"Starting Screen Media Service Test - {test_config.upper()} configuration")
    print("This test will:")
    print("- Start the screen media service")
    print("- Publish media commands every 3 seconds")
    if test_config == 'single':
        print("- Test ONLY screen ID 1 with different media types")
        print("- Perfect for testing with only one screen connected")
    else:
        print("- Test screen IDs 1, 2, and 4 with different media types")
        print("- Use this when you have multiple screens connected")
    print()
    
    # Initialize ROS2
    rclpy.init()
    
    try:
        # Create both the service and test publisher
        screen_service = ScreenMediaService()
        test_publisher = ScreenMediaTestPublisher(test_config=test_config)
        
        # Use MultiThreadedExecutor to avoid timer blocking
        from rclpy.executors import MultiThreadedExecutor
        executor = MultiThreadedExecutor(num_threads=4)
        executor.add_node(screen_service)
        executor.add_node(test_publisher)
        
        print("Running test with MultiThreadedExecutor... Press Ctrl+C to stop")
        executor.spin()
        
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    except Exception as e:
        print(f"Test error: {e}")
    finally:
        rclpy.shutdown()


def test_single_screen():
    """Convenience function to test single screen (ID 1 only)"""
    test_screen_media_service('single')


def test_multi_screen():
    """Convenience function to test multiple screens (IDs 1, 2, 4)"""
    test_screen_media_service('multi')


if __name__ == '__main__':
    import sys
    
    # Check command line arguments
    if len(sys.argv) > 1:
        config = sys.argv[1].lower()
        if config in ['single', 'multi']:
            test_screen_media_service(config)
        else:
            print("Usage: python3 test_screen.py [single|multi]")
            print()
            print("Configurations:")
            print("  single - Test only screen ID 1 (default)")
            print("  multi  - Test screen IDs 1, 2, and 4")
            print()
            print("Examples:")
            print("  python3 test_screen.py single")
            print("  python3 test_screen.py multi")
    else:
        # Default to single screen test
        print("No configuration specified, using 'single' (screen ID 1 only)")
        print("Use 'python3 test_screen.py multi' to test multiple screens")
        print()
        test_screen_media_service('single')
