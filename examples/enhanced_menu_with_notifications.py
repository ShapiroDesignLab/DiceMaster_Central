"""
Example integration showing how to use the notification system in an existing node.

This demonstrates how the menu_manager can be enhanced to send notifications
when actions are performed.
"""

import rclpy
from rclpy.node import Node
from DiceMaster_Central.utils.notification_helper import NotificationHelper


class ActionItem:
    def __init__(self, fn, *args, **kwargs):
        """
        Initialize an action item with a function and its arguments.
        
        Args:
            fn: The function to call when the action is triggered.
            args: Positional arguments for the function.
            kwargs: Keyword arguments for the function.
        """
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
    
    def __call__(self):
        """
        Call the stored function with its arguments.
        
        Returns:
            The result of the function call.
        """
        return self.fn(*self.args, **self.kwargs)


class EnhancedMenuManager(Node):
    """
    Enhanced MenuManager that integrates with the notification system.
    
    This shows how existing nodes can be upgraded to send notifications
    to screens when actions are performed.
    """
    
    def __init__(self):
        super().__init__('enhanced_menu_manager')
        
        # Initialize notification helper
        self.notifications = NotificationHelper(self)
        
        # Default screen for notifications (can be made configurable)
        self.notification_screen = 0
        
        self.menu_tree = {
            "Switch Strategy": {},  # Populate later
            "Calibrate IMU": ActionItem(self._calibrate_imu),
            "Check Battery": ActionItem(self._check_battery),
            "Shutdown": ActionItem(self._shutdown),
        }
        
        self.get_logger().info('Enhanced Menu Manager with notifications initialized')
    
    def _load_strategies(self):
        """From strategy manager, load all strategies discovered, and display"""
        self.notifications.info(
            self.notification_screen, 
            "Loading available strategies...",
            duration=2.0
        )
        
        # Simulate strategy loading
        import time
        time.sleep(1)
        
        # Simulate successful loading
        strategies = ["Random Strategy", "Bottom Answer", "Sequential"]
        self.notifications.info(
            self.notification_screen,
            f"Found {len(strategies)} strategies: {', '.join(strategies)}",
            duration=4.0
        )
    
    def _calibrate_imu(self):
        """
        Call the IMU calibration service and notify user of progress
        """
        self.get_logger().info("Starting IMU calibration...")
        
        # Notify start of calibration
        self.notifications.info(
            self.notification_screen,
            "Starting IMU calibration. Please keep the dice still...",
            duration=3.0
        )
        
        # Simulate calibration process
        import time
        time.sleep(3)
        
        try:
            # Simulate calibration logic here
            # In real implementation, this would call the actual IMU calibration service
            
            # Simulate some progress updates
            self.notifications.info(
                self.notification_screen,
                "Calibration in progress... 50% complete",
                duration=2.0
            )
            
            time.sleep(2)
            
            # Simulate successful completion
            success = True  # In real code, this would be the result of the calibration
            
            if success:
                self.notifications.info(
                    self.notification_screen,
                    "IMU calibration completed successfully! Dice is ready for use.",
                    duration=4.0
                )
                self.get_logger().info("IMU calibration completed successfully")
            else:
                self.notifications.error(
                    self.notification_screen,
                    "IMU calibration failed! Please try again or check sensor connection.",
                    duration=5.0
                )
                self.get_logger().error("IMU calibration failed")
                
        except Exception as e:
            self.notifications.error(
                self.notification_screen,
                f"Calibration error: {str(e)}",
                duration=5.0
            )
            self.get_logger().error(f"Calibration error: {str(e)}")
    
    def _check_battery(self):
        """
        Check battery level and notify user
        """
        self.get_logger().info("Checking battery level...")
        
        # Simulate battery check
        import random
        battery_level = random.randint(10, 100)  # Simulate battery percentage
        
        if battery_level > 50:
            self.notifications.info(
                self.notification_screen,
                f"Battery level: {battery_level}% - Good",
                duration=3.0
            )
        elif battery_level > 20:
            self.notifications.info(
                self.notification_screen,
                f"Battery level: {battery_level}% - Consider charging soon",
                duration=4.0
            )
        else:
            self.notifications.error(
                self.notification_screen,
                f"Battery level: {battery_level}% - Critical! Charge immediately!",
                duration=6.0
            )
    
    def _shutdown(self):
        """
        Shutdown the system with notification
        """
        self.get_logger().info("Initiating system shutdown...")
        
        # Notify of shutdown
        self.notifications.info(
            self.notification_screen,
            "System shutdown initiated. Saving state...",
            duration=3.0
        )
        
        # Simulate shutdown process
        import time
        time.sleep(2)
        
        self.notifications.info(
            self.notification_screen,
            "Goodbye! System will shut down in 5 seconds.",
            duration=5.0
        )
        
        # In real implementation, this would trigger actual shutdown
        self.get_logger().info("System shutdown complete")
    
    def execute_menu_item(self, item_name: str):
        """
        Execute a menu item by name.
        
        Args:
            item_name: Name of the menu item to execute
        """
        if item_name in self.menu_tree:
            item = self.menu_tree[item_name]
            if isinstance(item, ActionItem):
                try:
                    item()
                except Exception as e:
                    self.notifications.error(
                        self.notification_screen,
                        f"Error executing {item_name}: {str(e)}",
                        duration=5.0
                    )
                    self.get_logger().error(f"Error executing {item_name}: {str(e)}")
            else:
                self.notifications.info(
                    self.notification_screen,
                    f"Submenu: {item_name}",
                    duration=2.0
                )
        else:
            self.notifications.error(
                self.notification_screen,
                f"Unknown menu item: {item_name}",
                duration=3.0
            )


def main():
    """Main entry point for testing the enhanced menu manager"""
    rclpy.init()
    
    menu_manager = EnhancedMenuManager()
    
    try:
        # Demonstrate the menu system
        import time
        
        # Test different menu items
        menu_manager.execute_menu_item("Check Battery")
        time.sleep(6)
        
        menu_manager.execute_menu_item("Calibrate IMU")
        time.sleep(12)
        
        menu_manager.execute_menu_item("Shutdown")
        time.sleep(8)
        
    except KeyboardInterrupt:
        menu_manager.get_logger().info('Enhanced Menu Manager shutting down')
    finally:
        menu_manager.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
