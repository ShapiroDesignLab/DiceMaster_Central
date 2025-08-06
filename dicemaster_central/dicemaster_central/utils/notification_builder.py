"""
Simplified notification builder for DiceMaster system.

This module provides a simple function to generate JSON files compatible with
the TextGroup media type for displaying notifications on screens.

Supports INFO, WARNING, and ERROR notification levels with appropriate
colors and formatting.
"""

import json
import os
import tempfile
from typing import List
from dicemaster_central_msgs.msg import ScreenMediaCmd


def build_notification(content: str, notif_level: str, screen_id: int) -> ScreenMediaCmd:
    """
    Build a notification ScreenMediaCmd message compatible with TextGroup media type.
    
    Args:
        content: The notification message content
        notif_level: Notification level ('info', 'warning', or 'error')
        screen_id: The target screen ID for the notification
        
    Returns:
        ScreenMediaCmd: Message ready to be published to screen_{id}_cmd
        
    Raises:
        ValueError: If notif_level is not supported
    """
    # Validate notification level
    notif_level = notif_level.lower()
    if notif_level not in ['info', 'warning', 'error']:
        raise ValueError(f"Unsupported notification level: {notif_level}. Must be 'info', 'warning', or 'error'")
    
    # Define color schemes for each level
    color_schemes = {
        'info': {
            'bg_color': '0xFFFF',      # White background
            'font_color': '0x0000',    # Black text
            'level_text': '[INFO]'
        },
        'warning': {
            'bg_color': '0xFFFF',      # White background  
            'font_color': '0xFD20',    # Orange text (RGB565: 0b11111 101000 00000)
            'level_text': '[WARNING]'
        },
        'error': {
            'bg_color': '0xFFFF',      # White background
            'font_color': '0xF800',    # Red text
            'level_text': '[ERROR]'
        }
    }
    
    scheme = color_schemes[notif_level]
    
    # Create text entries list
    texts = []
    
    # Add level indicator at top-left (10, 20)
    texts.append({
        'x_cursor': 10,
        'y_cursor': 20,
        'font_id': 0,
        'font_color': scheme['font_color'],
        'text': scheme['level_text']
    })
    
    # Wrap content text and add entries
    content_lines = _wrap_text(content, max_width=70)
    
    y_position = 50  # Start content below the level indicator
    line_height = 25  # Spacing between lines
    
    for i, line in enumerate(content_lines):
        texts.append({
            'x_cursor': 10,
            'y_cursor': y_position + (i * line_height),
            'font_id': 0,
            'font_color': scheme['font_color'],
            'text': line
        })
    
    # Create JSON structure compatible with TextGroup
    notification_data = {
        'bg_color': scheme['bg_color'],
        'texts': texts
    }
    
    # Generate JSON file in temporary directory
    temp_dir = tempfile.gettempdir()
    temp_file = tempfile.NamedTemporaryFile(
        mode='w',
        suffix=f'_{notif_level}_notification.json',
        prefix='dicemaster_',
        dir=temp_dir,
        delete=False,  # Keep the file after closing
        encoding='utf-8'
    )
    
    try:
        # Write JSON data to file
        json.dump(notification_data, temp_file, indent=2, ensure_ascii=False)
        temp_file.flush()
        
        # Get the absolute path
        json_file_path = os.path.abspath(temp_file.name)
        
        # Create and return ScreenMediaCmd message
        msg = ScreenMediaCmd()
        msg.screen_id = screen_id
        msg.media_type = 0  # ContentType.TEXT = 0
        msg.file_path = json_file_path
        
        return msg
        
    finally:
        temp_file.close()


def _wrap_text(text: str, max_width: int = 70) -> List[str]:
    """
    Wrap text into lines that fit within the specified character width.
    
    Args:
        text: Text to wrap
        max_width: Maximum characters per line
        
    Returns:
        List of text lines
    """
    words = text.split()
    lines = []
    current_line = ""
    
    for word in words:
        # Check if adding this word would exceed the line length
        test_line = current_line + (" " if current_line else "") + word
        
        if len(test_line) <= max_width:
            current_line = test_line
        else:
            # Start a new line
            if current_line:
                lines.append(current_line)
                current_line = word
            else:
                # Word is longer than max_width, split it
                lines.append(word[:max_width])
                current_line = word[max_width:]
    
    # Add the last line if there's content
    if current_line:
        lines.append(current_line)
    
    return lines if lines else [""]


# Convenience functions for each notification level
def build_info_notification(content: str, screen_id: int) -> ScreenMediaCmd:
    """Build an INFO notification ScreenMediaCmd message."""
    return build_notification(content, 'info', screen_id)


def build_warning_notification(content: str, screen_id: int) -> ScreenMediaCmd:
    """Build a WARNING notification ScreenMediaCmd message."""
    return build_notification(content, 'warning', screen_id)


def build_error_notification(content: str, screen_id: int) -> ScreenMediaCmd:
    """Build an ERROR notification ScreenMediaCmd message."""
    return build_notification(content, 'error', screen_id)


# Example usage and testing function
def _test_notification_builder():
    """Test function to generate sample notifications."""
    test_cases = [
        ("System initialized successfully", "info"),
        ("Battery level is low", "warning"),
        ("Critical system failure detected", "error"),
        ("This is a very long notification message that should be wrapped across multiple lines to demonstrate the text wrapping functionality of the notification builder system", "info")
    ]
    
    print("Testing notification builder...")
    for content, level in test_cases:
        try:
            test_screen_id = 1  # Use screen 1 for testing
            msg = build_notification(content, level, test_screen_id)
            print(f"Generated {level} notification message:")
            print(f"  - Screen ID: {msg.screen_id}")
            print(f"  - Media Type: {msg.media_type}")
            print(f"  - File Path: {msg.file_path}")
            
            # Verify the file was created and is valid JSON
            with open(msg.file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                print(f"  - Background color: {data['bg_color']}")
                print(f"  - Number of text entries: {len(data['texts'])}")
                print(f"  - Level text: {data['texts'][0]['text']}")
            
            # Clean up test file
            os.unlink(msg.file_path)
            
        except Exception as e:
            print(f"Error testing {level} notification: {e}")
    
    print("Testing completed.")


if __name__ == '__main__':
    _test_notification_builder()
