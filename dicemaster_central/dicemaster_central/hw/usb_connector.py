"""
U-M Shapiro Design Lab
Daniel Hou @2024

ROS2 node for USB connection monitoring.
Monitors GPIO 13 voltage level and publishes USB connection status to /hw/usb_connected topic.
Uses GPIO interrupts for efficient resource usage.
"""

import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool, String
import time
import threading

try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False


class USBConnectorCheckerNode(Node):
    """ROS2 node for USB connection monitoring using GPIO interrupts"""
    
    def __init__(self):
        super().__init__('usb_connector_checker_node')
        
        # Declare parameters
        self.declare_parameter('gpio_pin', 13)
        self.declare_parameter('publishing_rate', 10.0)  # Hz
        self.declare_parameter('debounce_time', 50)  # milliseconds
        
        # Get parameters
        self.gpio_pin = self.get_parameter('gpio_pin').get_parameter_value().integer_value
        self.publishing_rate = self.get_parameter('publishing_rate').get_parameter_value().double_value
        self.debounce_time = self.get_parameter('debounce_time').get_parameter_value().integer_value
        
        # Publishers
        self.usb_connected_pub = self.create_publisher(Bool, '/hw/usb_connected', 10)
        self.usb_status_pub = self.create_publisher(String, '/hw/usb_status', 10)
        
        # Internal state
        self.usb_connected = False
        self.last_interrupt_time = 0.0
        self.gpio_initialized = False
        self._state_lock = threading.Lock()
        
        # Initialize GPIO
        self._init_gpio()
        
        # Create timer for publishing
        self.publish_timer = self.create_timer(
            1.0 / self.publishing_rate, 
            self.publish_usb_status
        )
        
        # Perform initial read
        self._read_gpio_state()
        
        self.get_logger().info(f'USB connector checker node started on GPIO {self.gpio_pin}')
    
    def _init_gpio(self):
        """Initialize GPIO settings and interrupt"""
        if not GPIO_AVAILABLE:
            self.get_logger().error('RPi.GPIO not available. Running in simulation mode.')
            self.gpio_initialized = False
            return
        
        try:
            # Setup GPIO
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self.gpio_pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
            
            # Setup interrupt for both rising and falling edges
            GPIO.add_event_detect(
                self.gpio_pin,
                GPIO.BOTH,
                callback=self._gpio_interrupt_callback,
                bouncetime=self.debounce_time
            )
            
            self.gpio_initialized = True
            self.get_logger().info(f'GPIO {self.gpio_pin} initialized with interrupts')
            
        except Exception as e:
            self.get_logger().error(f'Failed to initialize GPIO: {str(e)}')
            self.gpio_initialized = False
    
    def _gpio_interrupt_callback(self, channel):
        """
        GPIO interrupt callback function.
        Called when GPIO state changes (rising or falling edge).
        """
        current_time = time.time()
        
        # Simple debouncing check
        if current_time - self.last_interrupt_time < (self.debounce_time / 1000.0):
            return
        
        self.last_interrupt_time = current_time
        
        try:
            # Read current GPIO state
            self._read_gpio_state()
            
            self.get_logger().debug(f'GPIO {channel} interrupt: USB connected = {self.usb_connected}')
            
        except Exception as e:
            self.get_logger().error(f'Error in GPIO interrupt callback: {str(e)}')
    
    def _read_gpio_state(self):
        """Read the current GPIO state and update USB connection status"""
        if not self.gpio_initialized:
            # Simulation mode - alternate state for testing
            with self._state_lock:
                self.usb_connected = not self.usb_connected
            return
        
        try:
            # Read GPIO pin state
            gpio_state = GPIO.input(self.gpio_pin)
            
            with self._state_lock:
                # USB is connected if GPIO is HIGH (voltage present)
                self.usb_connected = bool(gpio_state)
            
        except Exception as e:
            self.get_logger().error(f'Error reading GPIO state: {str(e)}')
    
    def publish_usb_status(self):
        """Publish the current USB connection status"""
        try:
            with self._state_lock:
                current_status = self.usb_connected
            
            # Publish USB connection status
            connected_msg = Bool()
            connected_msg.data = current_status
            self.usb_connected_pub.publish(connected_msg)
            
            # Publish USB status string
            status_msg = String()
            status_msg.data = "CONNECTED" if current_status else "DISCONNECTED"
            self.usb_status_pub.publish(status_msg)
            
        except Exception as e:
            self.get_logger().error(f'Error publishing USB status: {str(e)}')
    
    def get_usb_status(self):
        """
        Get the current USB connection status
        
        Returns:
            bool: True if USB is connected, False otherwise
        """
        with self._state_lock:
            return self.usb_connected
    
    def force_check(self):
        """Force an immediate GPIO state check"""
        self._read_gpio_state()
    
    def cleanup(self):
        """Clean up GPIO resources"""
        if self.gpio_initialized and GPIO_AVAILABLE:
            try:
                GPIO.remove_event_detect(self.gpio_pin)
                GPIO.cleanup(self.gpio_pin)
                self.get_logger().info('GPIO cleanup completed')
            except Exception as e:
                self.get_logger().error(f'Error during GPIO cleanup: {str(e)}')
    
    def destroy_node(self):
        """Override destroy_node to clean up GPIO"""
        self.cleanup()
        super().destroy_node()


def main(args=None):
    """Main entry point for the USB connector checker node"""
    from rclpy.executors import MultiThreadedExecutor
    
    rclpy.init(args=args)
    
    node = None
    executor = None
    try:
        node = USBConnectorCheckerNode()
        
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