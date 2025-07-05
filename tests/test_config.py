#!/usr/bin/env python3
"""
Test script for DiceMaster configuration system
Tests the dice config publisher/subscriber system by:
1. Loading YAML config directly from disk
2. Starting a config publisher
3. Creating a config subscriber
4. Comparing the received JSON with the original YAML
"""

import sys
import os
import json
import yaml
import time
import threading
import unittest
from typing import Dict, Any

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import rclpy
from rclpy.node import Node
from rclpy.executors import MultiThreadedExecutor
from DiceMaster_Central.dice_config import DiceConfigPublisher, DiceConfigSubscriber


class ConfigTestNode(Node):
    """Test node that uses DiceConfigSubscriber"""
    
    def __init__(self):
        super().__init__('config_test_node')
        self.config_received = False
        self.received_config = {}
        self.config_event = threading.Event()
        
        # Create subscriber with callback
        self.subscriber = DiceConfigSubscriber(self, self._on_config_received)
        
    def _on_config_received(self, config: Dict[str, Any]):
        """Callback when config is received"""
        self.received_config = config
        self.config_received = True
        self.config_event.set()
        self.get_logger().info("Configuration received by test node")


class TestDiceConfig(unittest.TestCase):
    """Test cases for dice configuration system"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test environment"""
        rclpy.init()
        cls.executor = MultiThreadedExecutor()
        
        # Find config file
        current_dir = os.path.dirname(os.path.abspath(__file__))
        parent_dir = os.path.dirname(current_dir)
        cls.config_file = os.path.join(parent_dir, 'resource', 'config.yaml')
        
        if not os.path.exists(cls.config_file):
            raise FileNotFoundError(f"Config file not found: {cls.config_file}")
        
        # Load original YAML
        with open(cls.config_file, 'r') as f:
            cls.original_yaml = yaml.safe_load(f)
        
        # Start publisher
        cls.publisher = DiceConfigPublisher(cls.config_file)
        cls.executor.add_node(cls.publisher)
        
        # Start test node with subscriber
        cls.test_node = ConfigTestNode()
        cls.executor.add_node(cls.test_node)
        
        # Start executor in separate thread
        cls.executor_thread = threading.Thread(target=cls.executor.spin)
        cls.executor_thread.daemon = True
        cls.executor_thread.start()
        
        # Wait for initial config to be received
        print("Waiting for initial config...")
        if not cls.test_node.config_event.wait(timeout=10):
            raise TimeoutError("Config not received within timeout")
        
        print("✓ Initial configuration received")
    
    @classmethod
    def tearDownClass(cls):
        """Clean up test environment"""
        cls.executor.shutdown()
        if cls.executor_thread.is_alive():
            cls.executor_thread.join(timeout=5)
        rclpy.shutdown()
    
    def test_yaml_to_json_conversion(self):
        """Test that YAML config is correctly converted to JSON"""
        print("\n=== Testing YAML to JSON Conversion ===")
        
        # Get the received config
        received_config = self.test_node.received_config
        
        # Verify we have the main sections
        self.assertIn('screen_configs', received_config)
        self.assertIn('global_settings', received_config)
        self.assertIn('spi_config', received_config)
        self.assertIn('display_config', received_config)
        
        print("✓ All required sections present in received config")
    
    def test_screen_configs_match(self):
        """Test that screen configurations match between YAML and JSON"""
        print("\n=== Testing Screen Configs Match ===")
        
        original_screens = self.original_yaml.get('screen_config', {})
        received_screens = self.test_node.received_config.get('screen_configs', [])
        
        # Convert original to list format for comparison
        original_screens_list = []
        for screen_key, screen_data in original_screens.items():
            original_screens_list.append(screen_data)
        
        # Sort both lists by ID for comparison
        original_screens_list.sort(key=lambda x: x['id'])
        received_screens.sort(key=lambda x: x['id'])
        
        self.assertEqual(len(original_screens_list), len(received_screens))
        print(f"✓ Screen count matches: {len(received_screens)} screens")
        
        # Compare each screen
        for original, received in zip(original_screens_list, received_screens):
            self.assertEqual(original['id'], received['id'])
            self.assertEqual(original['bus_id'], received['bus_id'])
            self.assertEqual(original['bus_dev_id'], received['bus_dev_id'])
            self.assertEqual(original['default_orientation'], received['default_orientation'])
            self.assertEqual(original['position'], received['position'])
            self.assertEqual(original['description'], received['description'])
        
        print("✓ All screen configurations match")
    
    def test_global_settings_match(self):
        """Test that global settings match between YAML and JSON"""
        print("\n=== Testing Global Settings Match ===")
        
        original_settings = self.original_yaml.get('screen_settings', {})
        received_settings = self.test_node.received_config.get('global_settings', {})
        
        # Check each setting
        expected_settings = {
            'auto_rotate': original_settings.get('auto_rotate', True),
            'rotation_margin': original_settings.get('rotation_margin', 0.2),
            'max_chunk_size': original_settings.get('max_chunk_size', 1024),
            'communication_timeout': original_settings.get('communication_timeout', 5.0)
        }
        
        for key, expected_value in expected_settings.items():
            self.assertEqual(received_settings.get(key), expected_value)
            print(f"✓ {key}: {received_settings.get(key)} (matches expected)")
    
    def test_spi_config_match(self):
        """Test that SPI configuration matches between YAML and JSON"""
        print("\n=== Testing SPI Config Match ===")
        
        original_spi = self.original_yaml.get('spi_config', {})
        received_spi = self.test_node.received_config.get('spi_config', {})
        
        # Check each SPI setting
        expected_spi = {
            'max_speed_hz': original_spi.get('max_speed_hz', 1000000),
            'mode': original_spi.get('mode', 0),
            'bits_per_word': original_spi.get('bits_per_word', 8)
        }
        
        for key, expected_value in expected_spi.items():
            self.assertEqual(received_spi.get(key), expected_value)
            print(f"✓ {key}: {received_spi.get(key)} (matches expected)")
    
    def test_display_config_match(self):
        """Test that display configuration matches between YAML and JSON"""
        print("\n=== Testing Display Config Match ===")
        
        original_display = self.original_yaml.get('display_config', {})
        received_display = self.test_node.received_config.get('display_config', {})
        
        # Deep comparison of display config
        self.assertEqual(original_display, received_display)
        print(f"✓ Display config matches: {len(received_display)} entries")
    
    def test_config_reload(self):
        """Test that configuration can be reloaded"""
        print("\n=== Testing Config Reload ===")
        
        # Reset the event
        self.test_node.config_event.clear()
        
        # Trigger reload
        self.publisher.reload_config()
        
        # Wait for updated config
        if self.test_node.config_event.wait(timeout=5):
            print("✓ Config reload successful")
        else:
            self.fail("Config reload timed out")
    
    def test_subscriber_methods(self):
        """Test DiceConfigSubscriber methods"""
        print("\n=== Testing Subscriber Methods ===")
        
        subscriber = self.test_node.subscriber
        
        # Test config availability
        self.assertTrue(subscriber.is_config_available())
        print("✓ Config available")
        
        # Test get_config
        config = subscriber.get_config()
        self.assertIsInstance(config, dict)
        self.assertIn('screen_configs', config)
        print("✓ get_config() works")
        
        # Test get_screen_configs
        screen_configs = subscriber.get_screen_configs()
        self.assertIsInstance(screen_configs, list)
        self.assertGreater(len(screen_configs), 0)
        print(f"✓ get_screen_configs() returns {len(screen_configs)} screens")
        
        # Test get_screen_config_by_id
        first_screen = screen_configs[0]
        found_screen = subscriber.get_screen_config_by_id(first_screen.id)
        self.assertIsNotNone(found_screen)
        self.assertEqual(found_screen.id, first_screen.id)
        print(f"✓ get_screen_config_by_id() found screen {first_screen.id}")
        
        # Test get_global_settings
        global_settings = subscriber.get_global_settings()
        self.assertIsNotNone(global_settings)
        print("✓ get_global_settings() works")
        
        # Test get_spi_config
        spi_config = subscriber.get_spi_config()
        self.assertIsNotNone(spi_config)
        print("✓ get_spi_config() works")
        
        # Test get_screen_ids
        screen_ids = subscriber.get_screen_ids()
        self.assertIsInstance(screen_ids, list)
        self.assertEqual(len(screen_ids), len(screen_configs))
        print(f"✓ get_screen_ids() returns {len(screen_ids)} IDs")


def run_manual_test():
    """Run a manual test without unittest framework"""
    print("=== Manual Config Test ===")
    
    # Initialize ROS
    rclpy.init()
    
    try:
        # Find config file
        current_dir = os.path.dirname(os.path.abspath(__file__))
        parent_dir = os.path.dirname(current_dir)
        config_file = os.path.join(parent_dir, 'resource', 'config.yaml')
        
        if not os.path.exists(config_file):
            print(f"❌ Config file not found: {config_file}")
            return False
        
        print(f"📁 Using config file: {config_file}")
        
        # Load original YAML
        with open(config_file, 'r') as f:
            original_yaml = yaml.safe_load(f)
        
        print("✓ Original YAML loaded")
        
        # Create executor
        executor = MultiThreadedExecutor()
        
        # Start publisher
        publisher = DiceConfigPublisher(config_file)
        executor.add_node(publisher)
        
        # Start test node
        test_node = ConfigTestNode()
        executor.add_node(test_node)
        
        # Start executor
        executor_thread = threading.Thread(target=executor.spin)
        executor_thread.daemon = True
        executor_thread.start()
        
        print("🚀 Publisher and subscriber started")
        
        # Wait for config
        print("⏳ Waiting for configuration...")
        if not test_node.config_event.wait(timeout=10):
            print("❌ Timeout waiting for config")
            return False
        
        print("✓ Configuration received")
        
        # Compare configurations
        received_config = test_node.received_config
        
        print("\n📊 Comparison Results:")
        print(f"  Original YAML sections: {list(original_yaml.keys())}")
        print(f"  Received JSON sections: {list(received_config.keys())}")
        
        # Check screen configs
        original_screens = original_yaml.get('screen_config', {})
        received_screens = received_config.get('screen_configs', [])
        
        print(f"  Screen configs: {len(original_screens)} original → {len(received_screens)} received")
        
        # Check if they match
        all_match = True
        
        # Convert original to list for comparison
        original_screens_list = list(original_screens.values())
        original_screens_list.sort(key=lambda x: x['id'])
        received_screens.sort(key=lambda x: x['id'])
        
        if len(original_screens_list) != len(received_screens):
            print("  ❌ Screen count mismatch")
            all_match = False
        else:
            for i, (orig, recv) in enumerate(zip(original_screens_list, received_screens)):
                if orig != recv:
                    print(f"  ❌ Screen {i} mismatch:")
                    print(f"    Original: {orig}")
                    print(f"    Received: {recv}")
                    all_match = False
        
        if all_match:
            print("  ✅ All configurations match!")
        else:
            print("  ❌ Configuration mismatch detected")
        
        # Clean up
        executor.shutdown()
        if executor_thread.is_alive():
            executor_thread.join(timeout=5)
        
        return all_match
        
    except Exception as e:
        print(f"❌ Error during manual test: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        rclpy.shutdown()


def main():
    """Main test function"""
    print("DiceMaster Configuration Test")
    print("=" * 50)
    
    # Check if we should run unittest or manual test
    if len(sys.argv) > 1 and sys.argv[1] == 'manual':
        return 0 if run_manual_test() else 1
    else:
        # Run unittest
        unittest.main(verbosity=2)


if __name__ == '__main__':
    main()