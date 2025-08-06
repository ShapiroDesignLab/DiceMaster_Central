"""
U-M Shapiro Design Lab
Daniel Hou @2024

ROS2 node for battery level monitoring.
Publishes battery level percentage to /hw/battery_level topic.
"""

import rclpy
from rclpy.node import Node
from std_msgs.msg import Float32, String

class BatteryCheckerNode(Node):
    """ROS2 node for battery level monitoring"""
    
    def __init__(self):
        super().__init__('battery_checker_node')
        
        # Declare parameters
        self.declare_parameter('publishing_rate', 1.0)  # Hz
        self.declare_parameter('check_interval', 20.0)  # seconds
        
        # Get parameters
        self.publishing_rate = self.get_parameter('publishing_rate').get_parameter_value().double_value
        self.check_interval = self.get_parameter('check_interval').get_parameter_value().double_value
        
        # Publishers
        self.battery_level_pub = self.create_publisher(Float32, '/hw/battery_level', 10)
        self.battery_status_pub = self.create_publisher(String, '/hw/battery_status', 10)
        
        # Internal state
        self.current_battery_level = 0.0
        self.is_checking = False
        
        # Create timer for publishing
        self.publish_timer = self.create_timer(
            1.0 / self.publishing_rate, 
            self.publish_battery_level
        )
        
        # Create timer for battery checking
        self.check_timer = self.create_timer(
            self.check_interval,
            self._check_battery
        )
        
        self.get_logger().info('Battery checker node started')
    
    def _check_battery(self):
        """Check the current battery level"""
        if self.is_checking:
            return
        
        self.is_checking = True
        try:
            # Call the internal check function
            battery_level = self._check_internal()
            self.current_battery_level = battery_level
            
            self.get_logger().debug(f'Battery level checked: {battery_level:.1f}%')
            
        except Exception as e:
            self.get_logger().error(f'Error checking battery: {str(e)}')
        finally:
            self.is_checking = False
    
    def _check_internal(self):
        """
        Internal function to check battery level.
        
        This function will be implemented later to actually check the battery.
        For now, it returns 0%.
        
        Returns:
            float: Battery level as a percentage (0.0 - 100.0)
        """
        # TODO: Implement actual battery level checking
        # This could involve reading from:
        # - ADC pins for voltage measurement
        # - I2C battery management IC
        # - System files in /sys/class/power_supply/
        # - Hardware-specific battery monitoring
        
        return 0.0
    
    def publish_battery_level(self):
        """Publish the current battery level"""
        try:
            # Publish battery level as percentage
            level_msg = Float32()
            level_msg.data = self.current_battery_level
            self.battery_level_pub.publish(level_msg)
            
            # Publish battery status string
            status_msg = String()
            if self.current_battery_level <= 5.0:
                status_msg.data = "CRITICAL"
            elif self.current_battery_level <= 15.0:
                status_msg.data = "LOW"
            elif self.current_battery_level <= 30.0:
                status_msg.data = "MEDIUM"
            else:
                status_msg.data = "GOOD"
            
            self.battery_status_pub.publish(status_msg)
            
        except Exception as e:
            self.get_logger().error(f'Error publishing battery level: {str(e)}')
    
    def get_battery_level(self):
        """
        Get the current battery level
        
        Returns:
            float: Current battery level percentage
        """
        return self.current_battery_level
    
    def force_check(self):
        """Force an immediate battery check"""
        self._check_battery()


def main(args=None):
    """Main entry point for the battery checker node"""
    from rclpy.executors import MultiThreadedExecutor
    
    rclpy.init(args=args)
    
    node = None
    executor = None
    try:
        node = BatteryCheckerNode()
        
        # Use multithreaded executor
        executor = MultiThreadedExecutor()
        executor.add_node(node)
        executor.spin()
        
    except KeyboardInterrupt:
        pass
    finally:
        if node is not None:
            node.destroy_node()
        if executor is not None:
            executor.shutdown()
        rclpy.shutdown()


if __name__ == '__main__':
    main()