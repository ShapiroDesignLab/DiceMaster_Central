"""
Configuration loader for DiceMaster screens
Loads screen configuration from JSON file and provides client library for ROS nodes


spi_config: SPIConfig class
screen_config_global: ScreenConfigGlobal class
screen_configs: list of ScreenConfig instances
"""

import json
import yaml
import os
import threading
from typing import Dict, Any, List, Tuple, Optional
from dataclasses import dataclass, asdict

import rclpy
from rclpy.node import Node
from std_msgs.msg import String


@dataclass
class ScreenConfig:
    """Configuration for a single screen"""
    id: int
    bus_id: int
    bus_dev_id: int
    default_orientation: int
    position: str
    description: str

@dataclass
class ScreenConfigGlobal:
    """Global screen settings"""
    auto_rotate: bool
    rotation_margin: float
    max_chunk_size: int
    communication_timeout: float

@dataclass
class SPIConfig:
    """SPI configuration settings"""
    max_speed_hz: int
    mode: int
    bits_per_word: int


class DiceConfigPublisher(Node):
    """Loads and manages DiceMaster configuration - Single publisher for multiple subscribers"""
    
    def __init__(self, config_file: str = None):
        super().__init__('dice_config_publisher')
        
        if config_file is None:
            # Default to config.yaml in resource directory
            current_dir = os.path.dirname(os.path.abspath(__file__))
            parent_dir = os.path.dirname(current_dir)
            config_file = os.path.join(parent_dir, 'resource', 'config.yaml')
        
        assert config_file.endswith('.yaml'), "Configuration file must be a YAML file"
        self.config_file = config_file
        self.config = self._load_config()
        
        # Publisher for configuration
        self.config_publisher = self.create_publisher(String, '/dice_config', 10)
        
        # Publish configuration periodically and on startup
        self.timer = self.create_timer(5.0, self.publish_config)  # Every 5 seconds
        
        # Thread safety
        self.config_lock = threading.Lock()
        
        # Publish initial config
        self.publish_config()
        
        self.get_logger().info(f"DiceConfigPublisher initialized with config: {self.config_file}")
        
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        try:
            with open(self.config_file, 'r') as file:
                return yaml.safe_load(file)
        except FileNotFoundError:
            raise FileNotFoundError(f"Configuration file not found: {self.config_file}")
        except yaml.YAMLError as e:
            raise ValueError(f"Error parsing YAML configuration: {e}")
    
    def publish_config(self):
        """Publish configuration to all subscribers"""
        with self.config_lock:
            try:
                # Convert dataclass configurations to dict for JSON serialization
                config_data = {
                    'screen_configs': [asdict(config) for config in self.get_screen_configs()],
                    'global_settings': asdict(self.get_global_settings()),
                    'spi_config': asdict(self.get_spi_config()),
                    'display_config': self.get_display_config()
                }
                
                msg = String()
                msg.data = json.dumps(config_data)
                self.config_publisher.publish(msg)
                
            except Exception as e:
                self.get_logger().error(f"Failed to publish config: {e}")
    
    def reload_config(self):
        """Reload configuration from file and publish updates"""
        try:
            with self.config_lock:
                self.config = self._load_config()
            self.publish_config()
            self.get_logger().info("Configuration reloaded and published")
        except Exception as e:
            self.get_logger().error(f"Failed to reload config: {e}")
    
    def get_screen_configs(self) -> List[ScreenConfig]:
        """Get the list of screen configurations"""
        screen_configs = []
        screen_config_dict = self.config.get('screen_config', {})
        
        for screen_key, screen_data in screen_config_dict.items():
            screen_configs.append(ScreenConfig(
                id=screen_data['id'],
                bus_id=screen_data['bus_id'],
                bus_dev_id=screen_data['bus_dev_id'],
                default_orientation=screen_data['default_orientation'],
                position=screen_data['position'],
                description=screen_data['description']
            ))
        
        return screen_configs
    
    def get_global_settings(self) -> ScreenConfigGlobal:
        """Get the global screen settings"""
        global_settings = self.config.get('screen_settings', {})
        return ScreenConfigGlobal(
            auto_rotate=global_settings.get('auto_rotate', True),
            rotation_margin=global_settings.get('rotation_margin', 0.2),
            max_chunk_size=global_settings.get('max_chunk_size', 1024),
            communication_timeout=global_settings.get('communication_timeout', 5.0)
        )
    
    def get_spi_config(self) -> SPIConfig:
        """Get the SPI configuration settings"""
        spi_settings = self.config.get('spi_config', {})
        return SPIConfig(
            max_speed_hz=spi_settings.get('max_speed_hz', 1000000),
            mode=spi_settings.get('mode', 0),
            bits_per_word=spi_settings.get('bits_per_word', 8)
        )
    
    def get_display_config(self) -> Dict[str, Any]:
        """Get display configuration"""
        return self.config.get('display_config', {})
    
    def get_num_screens(self) -> int:
        """Get the number of configured screens"""
        return len(self.get_screen_configs())
    
    def validate_config(self) -> bool:
        """Validate the configuration file"""
        try:
            # Check if we have screen configurations
            screen_configs = self.get_screen_configs()
            if not screen_configs:
                raise ValueError("No screen configurations found")
            
            # Check for duplicate screen IDs
            screen_ids = [config.id for config in screen_configs]
            if len(screen_ids) != len(set(screen_ids)):
                raise ValueError("Duplicate screen IDs found")
            
            # Check for duplicate bus/device combinations
            bus_combos = [(config.bus_id, config.bus_dev_id) for config in screen_configs]
            if len(bus_combos) != len(set(bus_combos)):
                raise ValueError("Duplicate bus/device combinations found")
            
            # Validate orientation values
            for config in screen_configs:
                if config.default_orientation not in [0, 1, 2, 3]:
                    raise ValueError(f"Invalid orientation {config.default_orientation} for screen {config.id}")
            
            # Try to load other configurations
            self.get_global_settings()
            self.get_spi_config()
            self.get_display_config()
            
            self.get_logger().info("Configuration validation passed")
            return True
            
        except Exception as e:
            self.get_logger().error(f"Configuration validation failed: {e}")
            return False

class DiceConfigSubscriber:
    """Subscriber client for DiceMaster configuration - receives config from publisher"""
    
    def __init__(self, node: Node, config_callback: Optional[callable] = None):
        self.node = node
        self.config_callback = config_callback
        self.config = {}
        self.config_lock = threading.Lock()
        
        # Subscribe to configuration updates
        self.config_subscription = self.node.create_subscription(
            String,
            '/dice_config',
            self._parse_config,
            10
        )
        
        self.node.get_logger().info("DiceConfigSubscriber initialized")

    def _parse_config(self, msg: String):
        """Parse the configuration message and call callback if provided"""
        try:
            with self.config_lock:
                self.config = json.loads(msg.data)
            
            self.node.get_logger().debug("Configuration updated")
            
            # Call user-provided callback if available
            if self.config_callback:
                self.config_callback(self.config)
                
        except json.JSONDecodeError as e:
            self.node.get_logger().error(f"Error parsing JSON config: {e}")
            self.config = {}

    def get_config(self) -> Dict[str, Any]:
        """Get the current configuration (thread-safe)"""
        with self.config_lock:
            return self.config.copy()

    def is_config_available(self) -> bool:
        """Check if configuration has been received"""
        with self.config_lock:
            return bool(self.config)

    def get_screen_configs(self) -> List[ScreenConfig]:
        """Get the list of screen configurations"""
        with self.config_lock:
            screen_configs = []
            for screen_data in self.config.get('screen_configs', []):
                screen_configs.append(ScreenConfig(**screen_data))
            return screen_configs

    def get_screen_config_by_id(self, screen_id: int) -> Optional[ScreenConfig]:
        """Get screen configuration by ID"""
        for config in self.get_screen_configs():
            if config.id == screen_id:
                return config
        return None

    def get_global_settings(self) -> Optional[ScreenConfigGlobal]:
        """Get the global screen settings"""
        with self.config_lock:
            global_settings = self.config.get('global_settings', {})
            if global_settings:
                return ScreenConfigGlobal(**global_settings)
        return None

    def get_spi_config(self) -> Optional[SPIConfig]:
        """Get the SPI configuration settings"""
        with self.config_lock:
            spi_settings = self.config.get('spi_config', {})
            if spi_settings:
                return SPIConfig(**spi_settings)
        return None

    def get_display_config(self) -> Dict[str, Any]:
        """Get display configuration"""
        with self.config_lock:
            return self.config.get('display_config', {})

    def get_screen_ids(self) -> List[int]:
        """Get list of all screen IDs"""
        return [config.id for config in self.get_screen_configs()]


def main_publisher(args=None):
    """Main function for configuration publisher node"""
    rclpy.init(args=args)
    
    try:
        # Check for config file in environment or args
        config_file = os.getenv('DICE_CONFIG_FILE', None)
        publisher = DiceConfigPublisher(config_file)
        
        if publisher.validate_config():
            publisher.get_logger().info("✓ Configuration is valid")
            rclpy.spin(publisher)
        else:
            publisher.get_logger().error("✗ Configuration validation failed")
            return 1
            
    except Exception as e:
        print(f"Error running config publisher: {e}")
        return 1
    finally:
        if rclpy.ok():
            rclpy.shutdown()
    
    return 0


def main_test(args=None):
    """Test function for configuration validation"""
    rclpy.init(args=args)
    
    try:
        # Check for config file in environment or args
        config_file = os.getenv('DICE_CONFIG_FILE', None)
        publisher = DiceConfigPublisher(config_file)
        
        print("Validating configuration...")
        if publisher.validate_config():
            print("✓ Configuration is valid")
        else:
            print("✗ Configuration validation failed")
            return 1
        
        print(f"\nFound {publisher.get_num_screens()} screens:")
        for config in publisher.get_screen_configs():
            print(f"  Screen {config.id}: Bus {config.bus_id}.{config.bus_dev_id}, "
                  f"Orientation {config.default_orientation}, Position {config.position}")
        
        print(f"\nGlobal settings:")
        settings = publisher.get_global_settings()
        print(f"  Auto-rotate: {settings.auto_rotate}")
        print(f"  Rotation margin: {settings.rotation_margin}")
        print(f"  Max chunk size: {settings.max_chunk_size}")
        print(f"  Communication timeout: {settings.communication_timeout}")
        
        print(f"\nSPI settings:")
        spi_config = publisher.get_spi_config()
        print(f"  Max speed: {spi_config.max_speed_hz} Hz")
        print(f"  Mode: {spi_config.mode}")
        print(f"  Bits per word: {spi_config.bits_per_word}")
        
    except Exception as e:
        print(f"Error during test: {e}")
        return 1
    finally:
        if rclpy.ok():
            rclpy.shutdown()
    
    return 0


if __name__ == "__main__":
    import sys
    import argparse
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='DiceMaster Configuration Manager')
    parser.add_argument('mode', nargs='?', default='test', choices=['publisher', 'test'],
                       help='Mode to run in (default: test)')
    parser.add_argument('--config-file', type=str, default=None,
                       help='Path to configuration YAML file')
    
    parsed_args = parser.parse_args()
    
    # Set config file in environment if provided
    if parsed_args.config_file:
        os.environ['DICE_CONFIG_FILE'] = parsed_args.config_file
    
    # Run appropriate mode
    if parsed_args.mode == "publisher":
        exit(main_publisher())
    else:
        # Default: run test
        exit(main_test())
