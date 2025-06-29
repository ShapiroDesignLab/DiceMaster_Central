#!/usr/bin/env python3
"""
ROS2 Screen Node Entry Point
Spawns a single screen node with specified parameters
"""

import rclpy
import sys
from DiceMaster_Central.screen import ScreenNode


def main(args=None):
    rclpy.init(args=args)
    
    # Parse command line arguments
    if len(sys.argv) < 4:
        print("Usage: screen_node.py <screen_id> <bus_num> <dev_num> [auto_rotate] [rotation_margin]")
        print("Example: screen_node.py 1 0 0 true 0.2")
        sys.exit(1)
    
    try:
        screen_id = int(sys.argv[1])
        bus_num = int(sys.argv[2])
        dev_num = int(sys.argv[3])
        auto_rotate = sys.argv[4].lower() == 'true' if len(sys.argv) > 4 else True
        rotation_margin = float(sys.argv[5]) if len(sys.argv) > 5 else 0.2
        
        # Create and spin the screen node
        screen_node = ScreenNode(screen_id, bus_num, dev_num, auto_rotate, rotation_margin)
        
        try:
            rclpy.spin(screen_node)
        except KeyboardInterrupt:
            pass
        finally:
            screen_node.destroy_node()
            rclpy.shutdown()
            
    except ValueError as e:
        print(f"Error parsing arguments: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error running screen node: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
