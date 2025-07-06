#!/usr/bin/env python3
"""
Dataset Loader Integration Example

This example shows how to integrate the dataset loader service
with other parts of the DiceMaster system, such as strategies
and file management.
"""

import os
import json
import time
from typing import Dict, List, Optional

import rclpy
from rclpy.node import Node
from DiceMaster_Central.msg import DatasetInfo

from DiceMaster_Central.config.constants import (
    DATASET_METADATA_PATH, TYPE_IMG, TYPE_TXT, TYPE_VID
)


class DatasetConsumer(Node):
    """
    Example node that consumes dataset information from the dataset loader.
    
    This demonstrates how other components can:
    - Subscribe to dataset updates
    - Access file trees and metadata
    - Filter files by type
    - Build custom processing pipelines
    """
    
    def __init__(self):
        super().__init__('dataset_consumer_example')
        
        # Dataset state
        self.current_datasets: Dict[str, Dict] = {}
        self.dataset_trees: Dict[str, Dict] = {}
        self.last_update_time = 0.0
        
        # Subscribe to dataset updates
        self.dataset_subscriber = self.create_subscription(
            DatasetInfo,
            '/dice_system/datasets',
            self._handle_dataset_update,
            10
        )
        
        # Example timer for processing
        self.processing_timer = self.create_timer(
            5.0,  # Process every 5 seconds
            self._process_datasets
        )
        
        self.get_logger().info('Dataset Consumer Example started')
    
    def _handle_dataset_update(self, msg: DatasetInfo):
        """Handle incoming dataset information"""
        try:
            self.get_logger().info(f'Received dataset update with {len(msg.dataset_names)} datasets')
            
            # Update current dataset list
            self.current_datasets.clear()
            
            for i, name in enumerate(msg.dataset_names):
                if i < len(msg.dataset_paths):
                    self.current_datasets[name] = {
                        'path': msg.dataset_paths[i],
                        'md5': msg.md5_hashes[i] if i < len(msg.md5_hashes) else '',
                        'size': msg.file_sizes[i] if i < len(msg.file_sizes) else 0,
                        'extraction_time': msg.extraction_times[i] if i < len(msg.extraction_times) else 0
                    }
            
            # Load detailed metadata and file trees
            self._load_detailed_metadata()
            self.last_update_time = time.time()
            
        except Exception as e:
            self.get_logger().error(f'Error handling dataset update: {str(e)}')
    
    def _load_detailed_metadata(self):
        """Load detailed metadata including file trees"""
        try:
            if os.path.exists(DATASET_METADATA_PATH):
                with open(DATASET_METADATA_PATH, 'r') as f:
                    metadata = json.load(f)
                    self.dataset_trees = metadata.get('trees', {})
                    self.get_logger().info(f'Loaded file trees for {len(self.dataset_trees)} datasets')
        except Exception as e:
            self.get_logger().error(f'Error loading detailed metadata: {str(e)}')
    
    def get_files_by_type(self, dataset_name: str, file_type: int) -> List[Dict]:
        """
        Get all files of a specific type from a dataset.
        
        Args:
            dataset_name: Name of the dataset
            file_type: File type constant (TYPE_IMG, TYPE_TXT, TYPE_VID)
        
        Returns:
            List of file information dictionaries
        """
        files = []
        
        if dataset_name not in self.dataset_trees:
            return files
        
        def _scan_tree(tree_node):
            """Recursively scan file tree"""
            if isinstance(tree_node, dict):
                for key, value in tree_node.items():
                    if key.startswith('_'):
                        continue  # Skip metadata keys
                    
                    if isinstance(value, dict):
                        if value.get('_type') == 'file':
                            if value.get('file_type') == file_type:
                                files.append(value)
                        elif value.get('_type') == 'directory':
                            _scan_tree(value.get('_files', {}))
                        else:
                            _scan_tree(value)
        
        _scan_tree(self.dataset_trees[dataset_name])
        return files
    
    def get_images(self, dataset_name: str) -> List[Dict]:
        """Get all image files from a dataset"""
        return self.get_files_by_type(dataset_name, TYPE_IMG)
    
    def get_text_files(self, dataset_name: str) -> List[Dict]:
        """Get all text files from a dataset"""
        return self.get_files_by_type(dataset_name, TYPE_TXT)
    
    def get_videos(self, dataset_name: str) -> List[Dict]:
        """Get all video files from a dataset"""
        return self.get_files_by_type(dataset_name, TYPE_VID)
    
    def get_dataset_summary(self, dataset_name: str) -> Dict:
        """Get a summary of files in a dataset"""
        if dataset_name not in self.dataset_trees:
            return {}
        
        summary = {
            'images': len(self.get_images(dataset_name)),
            'text_files': len(self.get_text_files(dataset_name)),
            'videos': len(self.get_videos(dataset_name)),
            'total_files': 0,
            'size_mb': self.current_datasets.get(dataset_name, {}).get('size', 0) / (1024 * 1024)
        }
        
        summary['total_files'] = summary['images'] + summary['text_files'] + summary['videos']
        return summary
    
    def find_files_by_pattern(self, dataset_name: str, pattern: str) -> List[Dict]:
        """Find files matching a pattern in their path or name"""
        files = []
        
        if dataset_name not in self.dataset_trees:
            return files
        
        def _scan_tree(tree_node):
            """Recursively scan file tree for pattern matches"""
            if isinstance(tree_node, dict):
                for key, value in tree_node.items():
                    if key.startswith('_'):
                        continue
                    
                    if isinstance(value, dict):
                        if value.get('_type') == 'file':
                            file_path = value.get('path', '')
                            if pattern.lower() in file_path.lower() or pattern.lower() in key.lower():
                                files.append(value)
                        elif value.get('_type') == 'directory':
                            _scan_tree(value.get('_files', {}))
                        else:
                            _scan_tree(value)
        
        _scan_tree(self.dataset_trees[dataset_name])
        return files
    
    def _process_datasets(self):
        """Example processing of available datasets"""
        if not self.current_datasets:
            return
        
        self.get_logger().info(f'Processing {len(self.current_datasets)} datasets...')
        
        for dataset_name in self.current_datasets.keys():
            try:
                # Get dataset summary
                summary = self.get_dataset_summary(dataset_name)
                
                self.get_logger().info(
                    f'Dataset {dataset_name}: '
                    f'{summary["images"]} images, '
                    f'{summary["text_files"]} text files, '
                    f'{summary["videos"]} videos, '
                    f'{summary["size_mb"]:.2f} MB total'
                )
                
                # Example: Process images for a computer vision strategy
                images = self.get_images(dataset_name)
                if images:
                    self.get_logger().info(f'Found {len(images)} images in {dataset_name}')
                    # Here you could:
                    # - Load images for training
                    # - Validate image formats
                    # - Build image processing pipelines
                    # - Extract features
                
                # Example: Process text files for NLP strategies
                text_files = self.get_text_files(dataset_name)
                if text_files:
                    self.get_logger().info(f'Found {len(text_files)} text files in {dataset_name}')
                    # Here you could:
                    # - Parse text content
                    # - Extract keywords
                    # - Build text classification models
                    # - Generate summaries
                
                # Example: Find configuration files
                config_files = self.find_files_by_pattern(dataset_name, 'config')
                if config_files:
                    self.get_logger().info(f'Found {len(config_files)} config files in {dataset_name}')
                
            except Exception as e:
                self.get_logger().error(f'Error processing dataset {dataset_name}: {str(e)}')
    
    def get_file_content(self, file_info: Dict) -> Optional[bytes]:
        """
        Read content from a file using its file info.
        
        Args:
            file_info: File information dictionary from file tree
        
        Returns:
            File content as bytes, or None if error
        """
        try:
            full_path = file_info.get('full_path')
            if not full_path or not os.path.exists(full_path):
                return None
            
            with open(full_path, 'rb') as f:
                return f.read()
                
        except Exception as e:
            self.get_logger().error(f'Error reading file {file_info.get("path", "unknown")}: {str(e)}')
            return None


def main(args=None):
    """Main entry point for the dataset consumer example"""
    rclpy.init(args=args)
    
    consumer = DatasetConsumer()
    
    try:
        rclpy.spin(consumer)
    except KeyboardInterrupt:
        pass
    finally:
        consumer.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
