#!/usr/bin/env python3
"""
Dataset Management Utility Script

This script provides command-line tools for managing datasets:
- List available datasets
- Load/reload datasets
- Cleanup cache
- Get dataset information
- Test dataset integrity
"""

import argparse
import sys
import os
import json
import time
from pathlib import Path

import rclpy
from rclpy.node import Node
from std_srvs.srv import Empty, Trigger
from DiceMaster_Central.msg import DatasetInfo

# Add the package to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from DiceMaster_Central.config.constants import DATASET_METADATA_PATH


class DatasetManagerCLI(Node):
    """Command-line interface for dataset management"""
    
    def __init__(self):
        super().__init__('dataset_manager_cli')
        
        # Service clients
        self.load_client = self.create_client(Empty, '/dice_system/datasets/load')
        self.reload_client = self.create_client(Empty, '/dice_system/datasets/reload')
        self.cleanup_client = self.create_client(Empty, '/dice_system/datasets/cleanup')
        self.info_client = self.create_client(Trigger, '/dice_system/datasets/info')
        
        # Subscriber for dataset info
        self.dataset_info = None
        self.dataset_subscriber = self.create_subscription(
            DatasetInfo,
            '/dice_system/datasets',
            self._dataset_info_callback,
            10
        )
    
    def _dataset_info_callback(self, msg):
        """Callback for dataset info messages"""
        self.dataset_info = msg
    
    def wait_for_services(self, timeout=10.0):
        """Wait for all services to be available"""
        services = [
            self.load_client,
            self.reload_client,
            self.cleanup_client,
            self.info_client
        ]
        
        for service in services:
            if not service.wait_for_service(timeout_sec=timeout):
                self.get_logger().error(f'Service {service.srv_name} not available')
                return False
        
        return True
    
    def load_datasets(self):
        """Load datasets"""
        print("Loading datasets...")
        request = Empty.Request()
        
        try:
            future = self.load_client.call_async(request)
            rclpy.spin_until_future_complete(self, future, timeout_sec=60.0)
            
            if future.result() is not None:
                print("✓ Dataset load completed successfully")
                return True
            else:
                print("✗ Dataset load failed")
                return False
                
        except Exception as e:
            print(f"✗ Error loading datasets: {e}")
            return False
    
    def reload_datasets(self):
        """Reload datasets (clears cache first)"""
        print("Reloading datasets (clearing cache)...")
        request = Empty.Request()
        
        try:
            future = self.reload_client.call_async(request)
            rclpy.spin_until_future_complete(self, future, timeout_sec=120.0)
            
            if future.result() is not None:
                print("✓ Dataset reload completed successfully")
                return True
            else:
                print("✗ Dataset reload failed")
                return False
                
        except Exception as e:
            print(f"✗ Error reloading datasets: {e}")
            return False
    
    def cleanup_cache(self):
        """Cleanup cache"""
        print("Cleaning up cache...")
        request = Empty.Request()
        
        try:
            future = self.cleanup_client.call_async(request)
            rclpy.spin_until_future_complete(self, future, timeout_sec=30.0)
            
            if future.result() is not None:
                print("✓ Cache cleanup completed successfully")
                return True
            else:
                print("✗ Cache cleanup failed")
                return False
                
        except Exception as e:
            print(f"✗ Error cleaning up cache: {e}")
            return False
    
    def get_service_info(self):
        """Get service information"""
        print("Getting service information...")
        request = Trigger.Request()
        
        try:
            future = self.info_client.call_async(request)
            rclpy.spin_until_future_complete(self, future, timeout_sec=10.0)
            
            result = future.result()
            if result is not None:
                print(result.message)
                return result.success
            else:
                print("✗ Failed to get service info")
                return False
                
        except Exception as e:
            print(f"✗ Error getting service info: {e}")
            return False
    
    def list_datasets(self):
        """List available datasets"""
        print("Listing datasets...")
        
        # Wait for dataset info message
        timeout = 10.0
        start_time = time.time()
        
        while self.dataset_info is None and (time.time() - start_time) < timeout:
            rclpy.spin_once(self, timeout_sec=0.1)
        
        if self.dataset_info is None:
            print("✗ No dataset information available")
            return False
        
        print(f"\n📁 Available Datasets ({len(self.dataset_info.dataset_names)}):")
        print("-" * 60)
        
        for i, name in enumerate(self.dataset_info.dataset_names):
            path = self.dataset_info.dataset_paths[i] if i < len(self.dataset_info.dataset_paths) else "N/A"
            md5 = self.dataset_info.md5_hashes[i] if i < len(self.dataset_info.md5_hashes) else "N/A"
            size = self.dataset_info.file_sizes[i] if i < len(self.dataset_info.file_sizes) else 0
            
            size_mb = size / (1024 * 1024) if size > 0 else 0
            
            print(f"  {i+1}. {name}")
            print(f"     Path: {path}")
            print(f"     Size: {size_mb:.2f} MB")
            print(f"     MD5:  {md5[:16]}...")
            print()
        
        return True
    
    def show_metadata(self):
        """Show detailed metadata from file"""
        if not os.path.exists(DATASET_METADATA_PATH):
            print("✗ No metadata file found")
            return False
        
        try:
            with open(DATASET_METADATA_PATH, 'r') as f:
                metadata = json.load(f)
            
            print("\n📊 Dataset Metadata:")
            print("-" * 60)
            
            datasets = metadata.get('datasets', {})
            cache_info = metadata.get('cache_info', {})
            
            print(f"Total datasets: {len(datasets)}")
            print(f"Cache size: {cache_info.get('total_size_mb', 0):.2f} MB")
            print(f"Cache files: {cache_info.get('file_count', 0)}")
            print(f"Last load: {time.ctime(metadata.get('last_load_time', 0))}")
            print()
            
            for name, data in datasets.items():
                print(f"Dataset: {name}")
                print(f"  Source: {data.get('source_path', 'N/A')}")
                print(f"  Extracted: {data.get('extract_path', 'N/A')}")
                print(f"  Size: {data.get('file_size', 0) / (1024*1024):.2f} MB")
                print(f"  MD5: {data.get('md5_hash', 'N/A')}")
                print(f"  Extracted: {time.ctime(data.get('extraction_time', 0))}")
                print()
            
            return True
            
        except Exception as e:
            print(f"✗ Error reading metadata: {e}")
            return False


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(description='Dataset Management CLI')
    parser.add_argument('command', choices=[
        'load', 'reload', 'cleanup', 'info', 'list', 'metadata'
    ], help='Command to execute')
    parser.add_argument('--timeout', type=float, default=10.0, 
                      help='Service timeout in seconds')
    
    args = parser.parse_args()
    
    # Initialize ROS
    rclpy.init()
    
    try:
        cli = DatasetManagerCLI()
        
        # Wait for services to be available
        print("Waiting for dataset loader service...")
        if not cli.wait_for_services(timeout=args.timeout):
            print("✗ Dataset loader service not available")
            return 1
        
        # Execute command
        success = False
        
        if args.command == 'load':
            success = cli.load_datasets()
        elif args.command == 'reload':
            success = cli.reload_datasets()
        elif args.command == 'cleanup':
            success = cli.cleanup_cache()
        elif args.command == 'info':
            success = cli.get_service_info()
        elif args.command == 'list':
            success = cli.list_datasets()
        elif args.command == 'metadata':
            success = cli.show_metadata()
        
        return 0 if success else 1
        
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        return 1
    except Exception as e:
        print(f"✗ Error: {e}")
        return 1
    finally:
        rclpy.shutdown()


if __name__ == '__main__':
    sys.exit(main())
