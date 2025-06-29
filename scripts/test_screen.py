#!/usr/bin/env python3
"""
Test script for DiceMaster Screen Node functionality
"""

import rclpy
import time
from DiceMaster_Central.screen import ScreenNode
from DiceMaster_Central.protocol import Rotation, ImageResolution


def test_screen_node():
    """Test the screen node functionality"""
    rclpy.init()
    
    # Create a test screen node
    screen_node = ScreenNode(
        screen_id=1,
        bus_num=0,
        dev_num=0,
        auto_rotate=True,
        rotation_margin=0.2
    )
    
    # Test text drawing
    print("Testing text drawing...")
    screen_node.draw_text(
        bg_color=0x0000,  # Black background
        font_color=0xFFFF,  # White text
        texts=[(240, 200, 1, "Hello DiceMaster!"), (240, 240, 1, "Screen Node Test")]
    )
    
    # Test manual rotation
    print("Testing manual rotation...")
    time.sleep(2)
    screen_node.set_rotation(Rotation.ROTATION_90)
    
    time.sleep(2)
    screen_node.set_rotation(Rotation.ROTATION_180)
    
    time.sleep(2)
    screen_node.set_rotation(Rotation.ROTATION_270)
    
    time.sleep(2)
    screen_node.set_rotation(Rotation.ROTATION_0)
    
    # Re-enable auto-rotation
    print("Re-enabling auto-rotation...")
    screen_node.set_auto_rotate(True)
    
    # Keep running for a bit to test auto-rotation
    print("Testing auto-rotation (keep for 10 seconds)...")
    start_time = time.time()
    while time.time() - start_time < 10:
        rclpy.spin_once(screen_node, timeout_sec=0.1)
    
    # Clean up
    screen_node.destroy_node()
    rclpy.shutdown()
    print("Test completed!")


if __name__ == '__main__':
    test_screen_node()
