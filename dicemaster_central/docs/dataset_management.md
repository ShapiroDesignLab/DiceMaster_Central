# Dataset Management System

The Dataset Management System provides comprehensive functionality for loading, validating, caching, and managing datasets stored as ZIP files.

## Features

- **Automatic Dataset Discovery**: Scans `SD_ROOT/datasets/` for ZIP files
- **MD5 Validation**: Computes and verifies MD5 hashes to avoid redundant processing
- **Intelligent Caching**: Stores processed datasets in `CACHE_PATH` with size management
- **Cache Cleanup**: Automatically removes old cached data when exceeding 1GB (target: 300MB)
- **File Tree Indexing**: Builds hierarchical file trees for quick access
- **USB Integration**: Automatically loads datasets when USB is disconnected
- **ROS2 Integration**: Provides services and topics for system integration

## Directory Structure

```
~/.dicemaster/cache/
├── datasets/              # Extracted dataset contents
│   ├── dataset1/         # Individual dataset extraction
│   └── dataset2/
└── dataset_metadata.json  # Metadata and file trees

SD_ROOT/datasets/          # Source ZIP files
├── training_data.zip
├── test_images.zip
└── custom_strategies.zip
```

## Services

- `/dice_system/datasets/load` - Load/refresh datasets
- `/dice_system/datasets/reload` - Force reload (clears cache)
- `/dice_system/datasets/cleanup` - Manual cache cleanup
- `/dice_system/datasets/info` - Get service information

## Topics

- `/dice_system/datasets` - Published dataset information (DatasetInfo message)
- `/hw/usb_connected` - USB connection status (triggers auto-load)

## Usage

### Command Line Interface

```bash
# Load datasets
python3 scripts/dataset_manager.py load

# Reload datasets (clears cache)
python3 scripts/dataset_manager.py reload

# List available datasets
python3 scripts/dataset_manager.py list

# Get service information
python3 scripts/dataset_manager.py info

# Clean up cache
python3 scripts/dataset_manager.py cleanup

# Show detailed metadata
python3 scripts/dataset_manager.py metadata
```

### ROS2 Services

```bash
# Load datasets
ros2 service call /dice_system/datasets/load std_srvs/srv/Empty

# Get service information
ros2 service call /dice_system/datasets/info std_srvs/srv/Trigger

# Listen to dataset updates
ros2 topic echo /dice_system/datasets
```

### Launching the Service

```bash
# Launch dataset loader service
ros2 launch dicemaster_central launch_dataset_loader.py

# With custom parameters
ros2 launch dicemaster_central launch_dataset_loader.py auto_load_on_usb_disconnect:=false
```

## Dataset Format

Datasets should be ZIP files containing any combination of:

- **Images**: `.jpg`, `.png`, `.jpeg`, `.bmp`, `.heic`, `.heif`
- **Text**: `.txt`, `.md`, `.rtf`
- **Videos**: `.mpeg`
- **Other**: Any other file types (marked as unknown)

Example dataset structure:
```
training_data.zip
├── images/
│   ├── class1/
│   │   ├── image1.jpg
│   │   └── image2.png
│   └── class2/
│       └── image3.jpg
├── labels/
│   └── annotations.json
└── README.md
```

## Metadata Format

The system maintains metadata in JSON format:

```json
{
  "datasets": {
    "dataset_name": {
      "name": "dataset_name",
      "source_path": "/path/to/source.zip",
      "cache_zip_path": "/cache/path/dataset.zip",
      "extract_path": "/cache/path/dataset/",
      "md5_hash": "abc123...",
      "file_size": 1048576,
      "extraction_time": 1234567890.123,
      "last_accessed": 1234567890.123
    }
  },
  "trees": {
    "dataset_name": {
      "images": {
        "_type": "directory",
        "_files": {
          "image1.jpg": {
            "_type": "file",
            "path": "images/image1.jpg",
            "full_path": "/full/path/to/image1.jpg",
            "size": 12345,
            "file_type": 2,
            "extension": "jpg"
          }
        }
      }
    }
  },
  "last_load_time": 1234567890.123,
  "cache_info": {
    "total_size_bytes": 1073741824,
    "total_size_mb": 1024.0,
    "file_count": 1000,
    "last_cleanup": 1234567890.123
  }
}
```

## File Type Constants

- `TYPE_UNKNOWN = 0`
- `TYPE_TXT = 1`
- `TYPE_IMG = 2`
- `TYPE_VID = 3`

## Testing

Run the test suite to verify functionality:

```bash
# Start the service first
ros2 run dicemaster_central dataset_loader_service

# Run tests (in another terminal)
python3 scripts/test_dataset_loader.py
```

## Integration with Strategies

The system is designed to support future custom strategies:

- Strategies will have a dedicated section in `CACHE_PATH`
- File trees provide easy navigation for strategy implementations
- Metadata includes file type information for filtering
- ROS2 integration allows strategies to subscribe to dataset updates

## Error Handling

The system handles various error conditions:

- **Corrupted ZIP files**: Validation using zipfile.testzip()
- **Missing files**: Graceful handling with logging
- **Cache overflow**: Automatic cleanup based on modification time
- **Service timeouts**: Configurable timeouts for long operations
- **Disk space**: Monitoring and cleanup to prevent disk full conditions

## Performance Considerations

- **MD5 caching**: Avoids reprocessing unchanged datasets
- **Incremental loading**: Only processes new or modified datasets
- **Background processing**: Uses threading for non-blocking operations
- **Memory efficiency**: Streams large files rather than loading entirely
- **Cache management**: Proactive cleanup prevents disk space issues
