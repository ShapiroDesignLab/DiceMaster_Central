# DiceMaster Notification System

The DiceMaster notification system provides a simple way for ROS nodes to send visual notifications to screens with appropriate formatting and colors.

## Overview

The notification system consists of:
- **NotificationManager**: A ROS node that listens for notification messages and displays them on screens
- **NotificationRequest**: A ROS message type for sending notification requests
- **Topic**: `/dice_system/notifications` - the topic where notification requests are published

## Features

- **Two logging levels**: INFO and ERROR with different visual styling
- **Color-coded display**: INFO uses black text on white background, ERROR uses red text on white background
- **Automatic text wrapping**: Long messages are wrapped across multiple lines
- **Configurable duration**: Control how long notifications are displayed
- **Multi-screen support**: Send notifications to specific screens by ID

## Message Format

```
# NotificationRequest.msg
int32 screen_id     # Target screen ID (0-based)
string level        # "info" or "error"
string content      # Notification text content
float64 duration    # Display duration in seconds (default: 5.0)
```

## Usage

### Starting the Notification Manager

```bash
# Launch the notification manager
python3 /home/dice/DiceMaster/DiceMaster_Central/launch/launch_notification_manager.py
```

### Sending Notifications from Python Code

```python
import rclpy
from rclpy.node import Node
from DiceMaster_Central.msg import NotificationRequest

class YourNode(Node):
    def __init__(self):
        super().__init__('your_node')
        
        # Create publisher for notifications
        self.notification_pub = self.create_publisher(
            NotificationRequest,
            '/dice_system/notifications',
            10
        )
    
    def send_info(self, screen_id, message, duration=5.0):
        """Send an INFO notification"""
        msg = NotificationRequest()
        msg.screen_id = screen_id
        msg.level = 'info'
        msg.content = message
        msg.duration = duration
        self.notification_pub.publish(msg)
    
    def send_error(self, screen_id, message, duration=5.0):
        """Send an ERROR notification"""
        msg = NotificationRequest()
        msg.screen_id = screen_id
        msg.level = 'error'
        msg.content = message
        msg.duration = duration
        self.notification_pub.publish(msg)

# Example usage
node = YourNode()
node.send_info(0, "System initialized successfully")
node.send_error(0, "Battery level critically low!")
```

### Sending Notifications from Command Line

```bash
# Send an INFO notification
ros2 topic pub /dice_system/notifications DiceMaster_Central/msg/NotificationRequest \
  '{screen_id: 0, level: "info", content: "System startup complete", duration: 3.0}'

# Send an ERROR notification  
ros2 topic pub /dice_system/notifications DiceMaster_Central/msg/NotificationRequest \
  '{screen_id: 0, level: "error", content: "Critical error detected!", duration: 5.0}'
```

## Visual Formatting

### INFO Notifications
- **Background**: White (`0xFFFF` RGB565)
- **Text Color**: Black (`0x0000` RGB565)
- **Header**: `[INFO]` displayed at top-left
- **Content**: Starts on the next line, wrapped as needed

### ERROR Notifications
- **Background**: White (`0xFFFF` RGB565)
- **Text Color**: Red (`0xF800` RGB565)
- **Header**: `[ERROR]` displayed at top-left
- **Content**: Starts on the next line, wrapped as needed

## Testing

Run the test script to see example notifications:

```bash
python3 /home/dice/DiceMaster/DiceMaster_Central/scripts/test_notifications.py
```

This will send several test notifications demonstrating both INFO and ERROR levels.

## Integration with Screen Manager

The notification system integrates with the existing DiceMaster screen system:
- Uses `VirtualTextGroup` objects for efficient text rendering
- Leverages the existing screen request queue system
- Supports screen rotation and orientation features
- Compatible with the SPI communication protocol

## Architecture

```
[Your ROS Node] --> [/dice_system/notifications topic] --> [NotificationManager] --> [ScreenManager] --> [Screen Hardware]
```

The NotificationManager:
1. Listens to the `/dice_system/notifications` topic
2. Validates incoming notification requests
3. Creates `VirtualTextGroup` objects with appropriate formatting
4. Queues screen requests through the ScreenManager
5. Logs notification activity

## Error Handling

- Invalid notification levels are logged and ignored
- Empty content messages are rejected
- Screen manager availability is checked before processing
- All errors are logged with appropriate detail

## Configuration

The notification system uses these constants (RGB565 format):
- `COLOR_WHITE = 0xFFFF` - White background
- `COLOR_BLACK = 0x0000` - Black text for INFO
- `COLOR_RED = 0xF800` - Red text for ERROR

Text positioning:
- Level indicator: Position (10, 20)
- Content text: Starts at (10, 50) with 25-pixel line spacing
- Text wrapping: ~70 characters per line
