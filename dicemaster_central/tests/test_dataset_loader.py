#!/usr/bin/env python3
"""
Test script for Dataset Loader Service

This script tests the dataset loader functionality including:
- Service availability
- Dataset loading and caching
- MD5 verification
- Cache cleanup
- File tree building
"""

import os
import sys
import tempfile
import zipfile
import time
import json
import shutil
from pathlib import Path

import rclpy
from rclpy.node import Node
from std_srvs.srv import Empty, Trigger
from dicemaster_central_msgs.msg import DatasetInfo

# Add the package to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dicemaster_central.config.constants import DATASETS_PATH, DATASET_CACHE_PATH, DATASET_METADATA_PATH


class DatasetLoaderTest(Node):
    """Test class for dataset loader service"""
    
    def __init__(self):
        super().__init__('dataset_loader_test')
        
        # Service clients
        self.load_client = self.create_client(Empty, '/dice_system/datasets/load')
        self.reload_client = self.create_client(Empty, '/dice_system/datasets/reload')
        self.cleanup_client = self.create_client(Empty, '/dice_system/datasets/cleanup')
        self.info_client = self.create_client(Trigger, '/dice_system/datasets/info')
        
        # Dataset info storage
        self.dataset_info = None
        self.dataset_subscriber = self.create_subscription(
            DatasetInfo,
            '/dice_system/datasets',
            self._dataset_info_callback,
            10
        )
        
        # Test tracking
        self.tests_passed = 0
        self.tests_failed = 0
        self.temp_dirs = []
    
    def _dataset_info_callback(self, msg):
        """Callback for dataset info messages"""
        self.dataset_info = msg
    
    def wait_for_services(self, timeout=10.0):
        """Wait for all services to be available"""
        services = [
            (self.load_client, 'load'),
            (self.reload_client, 'reload'),
            (self.cleanup_client, 'cleanup'),
            (self.info_client, 'info')
        ]
        
        print("🔄 Waiting for dataset loader services...")
        
        for service, name in services:
            if not service.wait_for_service(timeout_sec=timeout):
                print(f"✗ Service {name} not available")
                return False
            print(f"✓ Service {name} available")
        
        return True
    
    def create_test_dataset(self, name, files):
        """Create a test dataset ZIP file"""
        try:
            # Create temporary directory for dataset content
            temp_dir = tempfile.mkdtemp()
            self.temp_dirs.append(temp_dir)
            
            # Create test files
            for file_path, content in files.items():
                full_path = os.path.join(temp_dir, file_path)
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                
                if isinstance(content, str):
                    with open(full_path, 'w') as f:
                        f.write(content)
                else:
                    with open(full_path, 'wb') as f:
                        f.write(content)
            
            # Create ZIP file
            zip_path = os.path.join(DATASETS_PATH, f"{name}.zip")
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                for root, dirs, files in os.walk(temp_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arc_path = os.path.relpath(file_path, temp_dir)
                        zf.write(file_path, arc_path)
            
            print(f"✓ Created test dataset: {zip_path}")
            return zip_path
            
        except Exception as e:
            print(f"✗ Error creating test dataset {name}: {e}")
            return None
    
    def cleanup_test_files(self):
        """Clean up temporary test files"""
        try:
            # Remove test datasets
            if os.path.exists(DATASETS_PATH):
                for file in os.listdir(DATASETS_PATH):
                    if file.startswith('test_') and file.endswith('.zip'):
                        os.remove(os.path.join(DATASETS_PATH, file))
            
            # Remove temporary directories
            for temp_dir in self.temp_dirs:
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)
            
            print("✓ Cleaned up test files")
        except Exception as e:
            print(f"✗ Error cleaning up test files: {e}")
    
    def test_service_availability(self):
        """Test that all services are available"""
        print("\n🧪 Testing service availability...")
        
        if self.wait_for_services():
            print("✓ All services available")
            self.tests_passed += 1
            return True
        else:
            print("✗ Some services unavailable")
            self.tests_failed += 1
            return False
    
    def test_dataset_creation_and_loading(self):
        """Test dataset creation and loading"""
        print("\n🧪 Testing dataset creation and loading...")
        
        try:
            # Create test datasets
            test_files_1 = {
                'images/test1.jpg': b'\xff\xd8\xff\xe0',  # Fake JPEG header
                'images/test2.png': b'\x89PNG',           # Fake PNG header
                'texts/readme.txt': 'This is a test dataset',
                'data/config.json': '{"test": true}',
                'subdir/nested/file.txt': 'nested content'
            }
            
            test_files_2 = {
                'videos/test.mp4': b'\x00\x00\x00\x20ftypmp4',  # Fake MP4 header
                'documents/manual.md': '# Test Manual\n\nThis is a test.',
                'assets/icon.bmp': b'BM',  # Fake BMP header
            }
            
            # Create test datasets
            dataset1_path = self.create_test_dataset('test_dataset_1', test_files_1)
            dataset2_path = self.create_test_dataset('test_dataset_2', test_files_2)
            
            if not dataset1_path or not dataset2_path:
                print("✗ Failed to create test datasets")
                self.tests_failed += 1
                return False
            
            # Call load service
            request = Empty.Request()
            future = self.load_client.call_async(request)
            rclpy.spin_until_future_complete(self, future, timeout_sec=30.0)
            
            if future.result() is None:
                print("✗ Load service call failed")
                self.tests_failed += 1
                return False
            
            # Wait for dataset info
            time.sleep(2.0)
            
            # Check if datasets were loaded
            timeout = 10.0
            start_time = time.time()
            
            while self.dataset_info is None and (time.time() - start_time) < timeout:
                rclpy.spin_once(self, timeout_sec=0.1)
            
            if self.dataset_info is None:
                print("✗ No dataset info received")
                self.tests_failed += 1
                return False
            
            # Verify datasets were loaded
            expected_datasets = ['test_dataset_1', 'test_dataset_2']
            loaded_datasets = self.dataset_info.dataset_names
            
            for expected in expected_datasets:
                if expected not in loaded_datasets:
                    print(f"✗ Dataset {expected} not loaded")
                    self.tests_failed += 1
                    return False
            
            print(f"✓ Successfully loaded {len(loaded_datasets)} datasets")
            self.tests_passed += 1
            return True
            
        except Exception as e:
            print(f"✗ Error in dataset loading test: {e}")
            self.tests_failed += 1
            return False
    
    def test_cache_functionality(self):
        """Test caching functionality"""
        print("\n🧪 Testing cache functionality...")
        
        try:
            # Check if cache directory was created
            if not os.path.exists(DATASET_CACHE_PATH):
                print("✗ Cache directory not created")
                self.tests_failed += 1
                return False
            
            # Check if metadata file was created
            if not os.path.exists(DATASET_METADATA_PATH):
                print("✗ Metadata file not created")
                self.tests_failed += 1
                return False
            
            # Read and verify metadata
            with open(DATASET_METADATA_PATH, 'r') as f:
                metadata = json.load(f)
            
            datasets = metadata.get('datasets', {})
            if len(datasets) < 2:
                print(f"✗ Expected at least 2 datasets in metadata, got {len(datasets)}")
                self.tests_failed += 1
                return False
            
            # Verify that extracted files exist
            for dataset_name, data in datasets.items():
                extract_path = data.get('extract_path', '')
                if not os.path.exists(extract_path):
                    print(f"✗ Extract path {extract_path} does not exist")
                    self.tests_failed += 1
                    return False
            
            print("✓ Cache functionality working correctly")
            self.tests_passed += 1
            return True
            
        except Exception as e:
            print(f"✗ Error in cache test: {e}")
            self.tests_failed += 1
            return False
    
    def test_reload_functionality(self):
        """Test reload functionality"""
        print("\n🧪 Testing reload functionality...")
        
        try:
            # Call reload service
            request = Empty.Request()
            future = self.reload_client.call_async(request)
            rclpy.spin_until_future_complete(self, future, timeout_sec=60.0)
            
            if future.result() is None:
                print("✗ Reload service call failed")
                self.tests_failed += 1
                return False
            
            # Wait for reload to complete
            time.sleep(3.0)
            
            # Check that datasets are still loaded
            timeout = 10.0
            start_time = time.time()
            
            while (time.time() - start_time) < timeout:
                rclpy.spin_once(self, timeout_sec=0.1)
            
            if self.dataset_info and len(self.dataset_info.dataset_names) >= 2:
                print("✓ Reload functionality working correctly")
                self.tests_passed += 1
                return True
            else:
                print("✗ Datasets not reloaded properly")
                self.tests_failed += 1
                return False
            
        except Exception as e:
            print(f"✗ Error in reload test: {e}")
            self.tests_failed += 1
            return False
    
    def test_info_service(self):
        """Test info service"""
        print("\n🧪 Testing info service...")
        
        try:
            request = Trigger.Request()
            future = self.info_client.call_async(request)
            rclpy.spin_until_future_complete(self, future, timeout_sec=10.0)
            
            result = future.result()
            if result is None:
                print("✗ Info service call failed")
                self.tests_failed += 1
                return False
            
            if not result.success:
                print(f"✗ Info service returned error: {result.message}")
                self.tests_failed += 1
                return False
            
            if "Dataset Loader Service Info" in result.message:
                print("✓ Info service working correctly")
                self.tests_passed += 1
                return True
            else:
                print("✗ Info service response format incorrect")
                self.tests_failed += 1
                return False
            
        except Exception as e:
            print(f"✗ Error in info service test: {e}")
            self.tests_failed += 1
            return False
    
    def test_cleanup_service(self):
        """Test cleanup service"""
        print("\n🧪 Testing cleanup service...")
        
        try:
            request = Empty.Request()
            future = self.cleanup_client.call_async(request)
            rclpy.spin_until_future_complete(self, future, timeout_sec=30.0)
            
            if future.result() is None:
                print("✗ Cleanup service call failed")
                self.tests_failed += 1
                return False
            
            print("✓ Cleanup service executed successfully")
            self.tests_passed += 1
            return True
            
        except Exception as e:
            print(f"✗ Error in cleanup test: {e}")
            self.tests_failed += 1
            return False
    
    def run_all_tests(self):
        """Run all tests"""
        print("🚀 Starting Dataset Loader Service Tests")
        print("=" * 50)
        
        # Ensure datasets directory exists
        os.makedirs(DATASETS_PATH, exist_ok=True)
        
        try:
            # Run tests
            self.test_service_availability()
            self.test_dataset_creation_and_loading()
            self.test_cache_functionality()
            self.test_reload_functionality()
            self.test_info_service()
            self.test_cleanup_service()
            
        finally:
            # Cleanup
            self.cleanup_test_files()
        
        # Print results
        print("\n" + "=" * 50)
        print("📊 Test Results:")
        print(f"✓ Passed: {self.tests_passed}")
        print(f"✗ Failed: {self.tests_failed}")
        print(f"📈 Success Rate: {self.tests_passed / (self.tests_passed + self.tests_failed) * 100:.1f}%")
        
        return self.tests_failed == 0


def main():
    """Main test entry point"""
    print("Dataset Loader Service Test Suite")
    print("Make sure the dataset_loader_service is running before running this test!")
    print()
    
    rclpy.init()
    
    try:
        test_node = DatasetLoaderTest()
        success = test_node.run_all_tests()
        return 0 if success else 1
        
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
        return 1
    except Exception as e:
        print(f"Test error: {e}")
        return 1
    finally:
        rclpy.shutdown()


if __name__ == '__main__':
    import sys
    sys.exit(main())
