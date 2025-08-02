# Screen Rotation Management

The `Screen` class in `DiceMaster_Central/hw/screen.py` has been cleaned up and enhanced with optional rotation tracking capabilities.

## Key Features

### 1. Optional Rotation Tracking
- Rotation tracking is now **optional** and controlled by the `using_rotation` parameter
- When disabled, no TF2 setup or orientation checking occurs
- Can be enabled/disabled dynamically at runtime

### 2. Clean Initialization
```python
# Screen without rotation tracking (lightweight)
screen = Screen(
    node=node,
    screen_id=1,
    bus_manager=bus_manager,
    using_rotation=False  # Default: False
)

# Screen with rotation tracking enabled
screen = Screen(
    node=node,
    screen_id=2,
    bus_manager=bus_manager,
    using_rotation=True,
    rotation_margin=0.2  # Threshold for rotation changes
)
```

### 3. Dynamic Rotation Control
```python
# Enable rotation tracking at runtime
screen.enable_rotation_tracking()

# Disable rotation tracking at runtime
screen.disable_rotation_tracking()

# Check rotation status
status = screen.get_rotation_status()
# Returns: {
#     'using_rotation': bool,
#     'current_rotation': Rotation,
#     'rotation_margin': float,
#     'tf_tracking_active': bool
# }
```

### 4. Manual Rotation Setting
```python
from DiceMaster_Central.config.constants import Rotation

# Set rotation manually (works regardless of tracking mode)
screen.set_rotation(Rotation.ROTATION_90)
```

## Implementation Details

### Rotation Protocol Support
- **Text Messages**: `TextBatchMessage` has a `rotation` attribute that gets updated
- **Image Messages**: Only `ImageStartMessage` (first message) has `rotation` - chunks don't need it
- **GIF Messages**: Each frame's `ImageStartMessage` gets updated with current rotation

### Performance Optimizations
- TF2 transforms and orientation checking only occur when `using_rotation=True`
- Rotation updates only affect content when rotation tracking is enabled
- Efficient frame-by-frame GIF rotation updates

### Thread Safety
- Media processing occurs in a separate daemon thread
- GIF playback is protected with locks
- Safe cleanup on destruction

## Usage Examples

### Basic Media Display (No Rotation)
```python
# Lightweight screen for fixed orientation displays
screen = Screen(node, screen_id=1, bus_manager=bus_mgr, using_rotation=False)

# Queue media requests
screen.queue_media_request(text_request)
screen.queue_media_request(image_request)
```

### Automatic Rotation Tracking
```python
# Screen that automatically rotates based on TF2 transforms
screen = Screen(
    node, 
    screen_id=2, 
    bus_manager=bus_mgr,
    using_rotation=True,
    rotation_margin=0.15  # 15cm threshold
)

# Content will automatically re-orient when device rotates
screen.queue_media_request(gif_request)
```

### Hybrid Usage
```python
# Start without rotation, enable later
screen = Screen(node, screen_id=3, bus_manager=bus_mgr, using_rotation=False)

# ... do some fixed-orientation work ...

# Enable rotation for dynamic content
screen.enable_rotation_tracking()

# Later disable for performance
screen.disable_rotation_tracking()
```

## Benefits of This Design

1. **Performance**: No TF2 overhead when rotation is not needed
2. **Flexibility**: Can be enabled/disabled at runtime
3. **Clarity**: Clear separation between rotation and non-rotation modes
4. **Robustness**: Proper error handling and resource cleanup
5. **Type Safety**: Improved type handling with proper rotation attribute management

## Testing

Run the rotation feature test:
```bash
cd DiceMaster_Central/tests
python test_screen_rotation.py
```

This demonstrates all the rotation features and verifies proper initialization and cleanup.
