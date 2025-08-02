"""
U-M Shapiro Design Lab
Daniel Hou @2024

Dataset Loader Service for DiceMaster Central

This module provides a ROS2 service for managing datasets stored as ZIP files.
It handles:
- Loading and validating ZIP files from SD_ROOT/datasets/
- MD5 hash computation and verification
- Intelligent caching with size management
- Automatic cleanup of old cached data
- File tree indexing and management
- Integration with USB connection monitoring
"""

import os
import json
import hashlib
import zipfile
import shutil
import threading
import time
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
from pathlib import Path

import rclpy
from rclpy.node import Node
from rclpy.service import Service
from std_srvs.srv import Empty, Trigger
from std_msgs.msg import Bool, String, Header
from dicemaster_central_msgs.msg import DatasetInfo

from dicemaster_central.config.constants import (
    CACHE_PATH, DATASETS_PATH, DATASET_CACHE_PATH, 
    DATASET_METADATA_PATH, CACHE_SIZE_LIMIT, CACHE_SIZE_TARGET,
    TYPE_IMG, TYPE_TXT, TYPE_VID, TYPE_UNKNOWN,
    TXT_EXTS, IMG_EXTS, VID_EXTS
)


class DatasetLoaderService(Node):
    """
    ROS2 service node for managing dataset ZIP files with intelligent caching.
    
    Features:
    - Automatic dataset discovery and validation
    - MD5-based cache management to avoid redundant processing
    - Size-based cache cleanup (1GB limit, cleanup to 300MB)
    - File tree indexing for quick access
    - USB connection integration
    """
    
    def __init__(self):
        super().__init__('dataset_loader_service')
        
        # Initialize paths
        self._ensure_directories()
        
        # Threading locks
        self._cache_lock = threading.RLock()
        self._dataset_lock = threading.RLock()
        
        # Dataset metadata storage
        self.dataset_metadata: Dict[str, Dict] = {}
        self.dataset_trees: Dict[str, Dict] = {}
        self.last_load_time = 0.0
        
        # Load existing metadata
        self._load_metadata()
        
        # ROS2 Services
        self.load_service = self.create_service(
            Empty, 
            '/datasets/load', 
            self._handle_load_request
        )
        
        self.reload_service = self.create_service(
            Empty,
            '/datasets/reload',
            self._handle_reload_request
        )
        
        self.cleanup_service = self.create_service(
            Empty,
            '/datasets/cleanup',
            self._handle_cleanup_request
        )
        
        self.info_service = self.create_service(
            Trigger,
            '/datasets/info',
            self._handle_info_request
        )
        
        # ROS2 Publishers
        self.dataset_info_pub = self.create_publisher(
            DatasetInfo, 
            '/datasets', 
            10
        )
        
        # ROS2 Subscribers
        self.usb_subscriber = self.create_subscription(
            Bool,
            '/hw/usb_connected',
            self._handle_usb_status,
            10
        )
        
        # Internal state
        self.usb_connected = True  # Default to connected
        self.auto_load_on_usb_disconnect = True
        
        # Perform initial load
        self._perform_dataset_load()
        
        self.get_logger().info('Dataset Loader Service initialized')
    
    def _ensure_directories(self):
        """Ensure all required directories exist"""
        os.makedirs(DATASETS_PATH, exist_ok=True)
        os.makedirs(DATASET_CACHE_PATH, exist_ok=True)
        os.makedirs(os.path.dirname(DATASET_METADATA_PATH), exist_ok=True)
    
    def _load_metadata(self):
        """Load existing dataset metadata from disk"""
        try:
            if os.path.exists(DATASET_METADATA_PATH):
                with open(DATASET_METADATA_PATH, 'r') as f:
                    data = json.load(f)
                    self.dataset_metadata = data.get('datasets', {})
                    self.dataset_trees = data.get('trees', {})
                    self.last_load_time = data.get('last_load_time', 0.0)
                    self.get_logger().info(f'Loaded metadata for {len(self.dataset_metadata)} datasets')
        except Exception as e:
            self.get_logger().warn(f'Failed to load metadata: {str(e)}')
            self.dataset_metadata = {}
            self.dataset_trees = {}
    
    def _save_metadata(self):
        """Save dataset metadata to disk"""
        try:
            metadata = {
                'datasets': self.dataset_metadata,
                'trees': self.dataset_trees,
                'last_load_time': self.last_load_time,
                'cache_info': self._get_cache_info()
            }
            
            with open(DATASET_METADATA_PATH, 'w') as f:
                json.dump(metadata, f, indent=2, default=str)
                
        except Exception as e:
            self.get_logger().error(f'Failed to save metadata: {str(e)}')
    
    def _get_cache_info(self) -> Dict:
        """Get cache directory information"""
        try:
            total_size = 0
            file_count = 0
            
            for root, dirs, files in os.walk(CACHE_PATH):
                for file in files:
                    file_path = os.path.join(root, file)
                    if os.path.exists(file_path):
                        total_size += os.path.getsize(file_path)
                        file_count += 1
            
            return {
                'total_size_bytes': total_size,
                'total_size_mb': total_size / (1024 * 1024),
                'file_count': file_count,
                'last_cleanup': getattr(self, 'last_cleanup_time', 0.0)
            }
        except Exception as e:
            self.get_logger().error(f'Error getting cache info: {str(e)}')
            return {}
    
    def _compute_file_md5(self, file_path: str) -> str:
        """Compute MD5 hash of a file"""
        hash_md5 = hashlib.md5()
        try:
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception as e:
            self.get_logger().error(f'Error computing MD5 for {file_path}: {str(e)}')
            return ""
    
    def _validate_zip_file(self, file_path: str) -> bool:
        """Validate that a ZIP file is not corrupted"""
        try:
            with zipfile.ZipFile(file_path, 'r') as zip_file:
                # Test the ZIP file integrity
                corrupt_files = zip_file.testzip()
                return corrupt_files is None
        except Exception as e:
            self.get_logger().warn(f'ZIP file validation failed for {file_path}: {str(e)}')
            return False
    
    def _cleanup_cache(self) -> bool:
        """Cleanup cache if it exceeds size limits"""
        try:
            cache_info = self._get_cache_info()
            current_size = cache_info.get('total_size_bytes', 0)
            
            if current_size <= CACHE_SIZE_LIMIT:
                return True
            
            self.get_logger().info(f'Cache size ({current_size / (1024*1024):.2f} MB) exceeds limit. Starting cleanup...')
            
            # Get all first-order directories in cache with their modification times
            cache_dirs = []
            for item in os.listdir(CACHE_PATH):
                item_path = os.path.join(CACHE_PATH, item)
                if os.path.isdir(item_path):
                    mtime = os.path.getmtime(item_path)
                    size = self._get_directory_size(item_path)
                    cache_dirs.append((item_path, mtime, size))
            
            # Sort by modification time (oldest first)
            cache_dirs.sort(key=lambda x: x[1])
            
            # Remove oldest directories until we're under the target size
            for dir_path, mtime, dir_size in cache_dirs:
                if current_size <= CACHE_SIZE_TARGET:
                    break
                
                try:
                    # Don't remove the datasets directory or metadata files
                    if 'datasets' in os.path.basename(dir_path) or dir_path.endswith('.json'):
                        continue
                    
                    self.get_logger().info(f'Removing old cache directory: {dir_path}')
                    shutil.rmtree(dir_path)
                    current_size -= dir_size
                    
                    # Update metadata to remove references to deleted datasets
                    self._update_metadata_after_cleanup(dir_path)
                    
                except Exception as e:
                    self.get_logger().error(f'Error removing {dir_path}: {str(e)}')
            
            self.last_cleanup_time = time.time()
            self.get_logger().info(f'Cache cleanup completed. New size: {current_size / (1024*1024):.2f} MB')
            return True
            
        except Exception as e:
            self.get_logger().error(f'Cache cleanup failed: {str(e)}')
            return False
    
    def _get_directory_size(self, directory: str) -> int:
        """Get the total size of a directory"""
        total_size = 0
        try:
            for dirpath, dirnames, filenames in os.walk(directory):
                for filename in filenames:
                    file_path = os.path.join(dirpath, filename)
                    if os.path.exists(file_path):
                        total_size += os.path.getsize(file_path)
        except Exception as e:
            self.get_logger().error(f'Error calculating directory size for {directory}: {str(e)}')
        return total_size
    
    def _update_metadata_after_cleanup(self, removed_path: str):
        """Update metadata after cache cleanup removes directories"""
        # Remove dataset metadata for datasets whose cache was deleted
        datasets_to_remove = []
        for dataset_name, metadata in self.dataset_metadata.items():
            cache_path = metadata.get('cache_path', '')
            if cache_path and removed_path in cache_path:
                datasets_to_remove.append(dataset_name)
        
        for dataset_name in datasets_to_remove:
            del self.dataset_metadata[dataset_name]
            if dataset_name in self.dataset_trees:
                del self.dataset_trees[dataset_name]
    
    def _get_file_type(self, file_path: str) -> int:
        """Determine file type based on extension"""
        if os.path.basename(file_path.lower()).startswith('.'):
            return TYPE_UNKNOWN
        
        # Skip README files
        if os.path.basename(file_path).lower().startswith('readme'):
            return TYPE_UNKNOWN
        
        ext = os.path.splitext(file_path)[1][1:].lower()  # Remove the dot
        
        if ext in TXT_EXTS:
            return TYPE_TXT
        elif ext in IMG_EXTS:
            return TYPE_IMG
        elif ext in VID_EXTS:
            return TYPE_VID
        else:
            return TYPE_UNKNOWN
    
    def _build_file_tree(self, extract_path: str) -> Dict:
        """Build a hierarchical file tree from extracted dataset"""
        tree = {}
        
        try:
            for root, dirs, files in os.walk(extract_path):
                # Get relative path from extract_path
                rel_root = os.path.relpath(root, extract_path)
                if rel_root == '.':
                    rel_root = ''
                
                # Build nested dictionary structure
                current_level = tree
                if rel_root:
                    for part in rel_root.split(os.sep):
                        if part not in current_level:
                            current_level[part] = {'_type': 'directory', '_files': {}}
                        current_level = current_level[part]['_files']
                
                # Add files to current level
                for file in files:
                    if not file.startswith('.'):  # Skip hidden files
                        file_path = os.path.join(root, file)
                        rel_file_path = os.path.relpath(file_path, extract_path)
                        
                        file_info = {
                            '_type': 'file',
                            'path': rel_file_path,
                            'full_path': file_path,
                            'size': os.path.getsize(file_path) if os.path.exists(file_path) else 0,
                            'file_type': self._get_file_type(file_path),
                            'extension': os.path.splitext(file)[1][1:].lower()
                        }
                        current_level[file] = file_info
                
                # Add subdirectories to current level
                for dir_name in dirs:
                    if not dir_name.startswith('.'):  # Skip hidden directories
                        if dir_name not in current_level:
                            current_level[dir_name] = {'_type': 'directory', '_files': {}}
        
        except Exception as e:
            self.get_logger().error(f'Error building file tree: {str(e)}')
        
        return tree
    
    def _extract_dataset(self, zip_path: str, dataset_name: str) -> Tuple[bool, str]:
        """Extract a dataset ZIP file to cache"""
        try:
            extract_path = os.path.join(DATASET_CACHE_PATH, dataset_name)
            
            # Remove existing extraction if it exists
            if os.path.exists(extract_path):
                shutil.rmtree(extract_path)
            
            # Extract the ZIP file
            with zipfile.ZipFile(zip_path, 'r') as zip_file:
                zip_file.extractall(extract_path)
            
            self.get_logger().info(f'Extracted dataset {dataset_name} to {extract_path}')
            return True, extract_path
            
        except Exception as e:
            self.get_logger().error(f'Error extracting {zip_path}: {str(e)}')
            return False, ""
    
    def _process_dataset(self, zip_path: str) -> bool:
        """Process a single dataset ZIP file"""
        try:
            dataset_name = os.path.splitext(os.path.basename(zip_path))[0]
            
            # Compute MD5 hash
            md5_hash = self._compute_file_md5(zip_path)
            if not md5_hash:
                return False
            
            # Check if we already have this dataset cached with same MD5
            if dataset_name in self.dataset_metadata:
                cached_md5 = self.dataset_metadata[dataset_name].get('md5_hash', '')
                if cached_md5 == md5_hash:
                    self.get_logger().info(f'Dataset {dataset_name} already cached with matching MD5')
                    return True
            
            # Validate ZIP file
            if not self._validate_zip_file(zip_path):
                self.get_logger().error(f'ZIP file validation failed: {zip_path}')
                return False
            
            # Copy ZIP to cache
            cache_zip_path = os.path.join(DATASET_CACHE_PATH, f"{dataset_name}.zip")
            shutil.copy2(zip_path, cache_zip_path)
            
            # Extract dataset
            success, extract_path = self._extract_dataset(cache_zip_path, dataset_name)
            if not success:
                return False
            
            # Build file tree
            file_tree = self._build_file_tree(extract_path)
            
            # Update metadata
            self.dataset_metadata[dataset_name] = {
                'name': dataset_name,
                'source_path': zip_path,
                'cache_zip_path': cache_zip_path,
                'extract_path': extract_path,
                'md5_hash': md5_hash,
                'file_size': os.path.getsize(zip_path),
                'extraction_time': time.time(),
                'last_accessed': time.time()
            }
            
            self.dataset_trees[dataset_name] = file_tree
            
            self.get_logger().info(f'Successfully processed dataset: {dataset_name}')
            return True
            
        except Exception as e:
            self.get_logger().error(f'Error processing dataset {zip_path}: {str(e)}')
            return False
    
    def _perform_dataset_load(self) -> Tuple[int, int]:
        """Perform the main dataset loading operation"""
        with self._dataset_lock:
            try:
                self.get_logger().info('Starting dataset load operation')
                
                # Cleanup cache if needed
                self._cleanup_cache()
                
                # Find all ZIP files in datasets directory
                zip_files = []
                if os.path.exists(DATASETS_PATH):
                    for file in os.listdir(DATASETS_PATH):
                        if file.lower().endswith('.zip'):
                            zip_path = os.path.join(DATASETS_PATH, file)
                            if os.path.isfile(zip_path):
                                zip_files.append(zip_path)
                
                self.get_logger().info(f'Found {len(zip_files)} ZIP files')
                
                # Process each ZIP file
                processed = 0
                failed = 0
                
                for zip_path in zip_files:
                    if self._process_dataset(zip_path):
                        processed += 1
                    else:
                        failed += 1
                
                # Update timestamp and save metadata
                self.last_load_time = time.time()
                self._save_metadata()
                
                # Publish dataset information
                self._publish_dataset_info()
                
                self.get_logger().info(f'Dataset load completed: {processed} processed, {failed} failed')
                return processed, failed
                
            except Exception as e:
                self.get_logger().error(f'Dataset load operation failed: {str(e)}')
                return 0, 0
    
    def _publish_dataset_info(self):
        """Publish dataset information to ROS topic"""
        try:
            msg = DatasetInfo()
            msg.header = Header()
            msg.header.stamp = self.get_clock().now().to_msg()
            msg.header.frame_id = "dataset_loader"
            
            # Populate message fields
            msg.dataset_names = []
            msg.dataset_paths = []
            msg.md5_hashes = []
            msg.file_sizes = []
            msg.extraction_times = []
            
            for dataset_name, metadata in self.dataset_metadata.items():
                msg.dataset_names.append(dataset_name)
                msg.dataset_paths.append(metadata.get('extract_path', ''))
                msg.md5_hashes.append(metadata.get('md5_hash', ''))
                msg.file_sizes.append(metadata.get('file_size', 0))
                msg.extraction_times.append(int(metadata.get('extraction_time', 0)))
            
            msg.json_metadata_path = DATASET_METADATA_PATH
            
            self.dataset_info_pub.publish(msg)
            self.get_logger().debug(f'Published dataset info for {len(msg.dataset_names)} datasets')
            
        except Exception as e:
            self.get_logger().error(f'Error publishing dataset info: {str(e)}')
    
    def _handle_usb_status(self, msg: Bool):
        """Handle USB connection status updates"""
        try:
            previous_status = self.usb_connected
            self.usb_connected = msg.data
            
            # If USB was disconnected and auto-load is enabled, trigger dataset load
            if previous_status and not self.usb_connected and self.auto_load_on_usb_disconnect:
                self.get_logger().info('USB disconnected - triggering dataset load')
                # Use timer to avoid blocking the callback
                self.create_timer(1.0, lambda: self._perform_dataset_load(), clock=self.get_clock())
                
        except Exception as e:
            self.get_logger().error(f'Error handling USB status: {str(e)}')
    
    def _handle_load_request(self, request, response):
        """Handle dataset load service request"""
        try:
            processed, failed = self._perform_dataset_load()
            self.get_logger().info(f'Load request completed: {processed} processed, {failed} failed')
            return response
        except Exception as e:
            self.get_logger().error(f'Error handling load request: {str(e)}')
            return response
    
    def _handle_reload_request(self, request, response):
        """Handle dataset reload service request (clears cache first)"""
        try:
            with self._dataset_lock:
                # Clear cached metadata
                self.dataset_metadata.clear()
                self.dataset_trees.clear()
                
                # Remove cached files
                if os.path.exists(DATASET_CACHE_PATH):
                    shutil.rmtree(DATASET_CACHE_PATH)
                os.makedirs(DATASET_CACHE_PATH, exist_ok=True)
                
                # Perform fresh load
                processed, failed = self._perform_dataset_load()
                self.get_logger().info(f'Reload request completed: {processed} processed, {failed} failed')
                
            return response
        except Exception as e:
            self.get_logger().error(f'Error handling reload request: {str(e)}')
            return response
    
    def _handle_cleanup_request(self, request, response):
        """Handle cache cleanup service request"""
        try:
            success = self._cleanup_cache()
            if success:
                self._save_metadata()
                self._publish_dataset_info()
            return response
        except Exception as e:
            self.get_logger().error(f'Error handling cleanup request: {str(e)}')
            return response
    
    def _handle_info_request(self, request, response):
        """Handle dataset info service request"""
        try:
            cache_info = self._get_cache_info()
            
            info_text = f"""Dataset Loader Service Info:
- Datasets loaded: {len(self.dataset_metadata)}
- Cache size: {cache_info.get('total_size_mb', 0):.2f} MB
- Cache files: {cache_info.get('file_count', 0)}
- Last load: {datetime.fromtimestamp(self.last_load_time).isoformat() if self.last_load_time else 'Never'}
- USB connected: {self.usb_connected}
- Metadata path: {DATASET_METADATA_PATH}

Datasets:
"""
            for name, metadata in self.dataset_metadata.items():
                size_mb = metadata.get('file_size', 0) / (1024 * 1024)
                info_text += f"  - {name}: {size_mb:.2f} MB (MD5: {metadata.get('md5_hash', '')[:8]}...)\n"
            
            response.success = True
            response.message = info_text
            
        except Exception as e:
            response.success = False
            response.message = f"Error getting info: {str(e)}"
        
        return response


def main(args=None):
    """Main entry point for the dataset loader service"""
    rclpy.init(args=args)
    
    dataset_loader = DatasetLoaderService()
    
    try:
        rclpy.spin(dataset_loader)
    except KeyboardInterrupt:
        pass
    finally:
        dataset_loader.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
