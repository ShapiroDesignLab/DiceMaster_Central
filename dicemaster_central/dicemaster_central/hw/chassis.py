"""
Dice chassis node for managing robot orientation and screen orientation detection.
Subscribes to IMU data and publishes screen orientation messages.
"""

import rclpy
from rclpy.node import Node

from geometry_msgs.msg import Quaternion
from sensor_msgs.msg import Imu
import numpy as np
import os
import threading
import time

from dicemaster_central.constants import Rotation as ConfigRotation
from dicemaster_central.config import dice_config
from dicemaster_central.hw.orientation_math import DiceOrientation
from ament_index_python.packages import get_package_share_directory

# Conditional imports for ROS message types only
ChassisOrientation = None
ScreenPose = None

def _import_ros_message_deps():
    """Import ROS message dependencies if needed"""
    global ChassisOrientation, ScreenPose
    try:
        from dicemaster_central_msgs.msg import ChassisOrientation, ScreenPose
        return True
    except ImportError as e:
        return False

class ChassisNode(Node):
    """
    ROS2 node that manages the dice robot chassis orientation.

    This node:
    1. Subscribes to IMU data for robot orientation
    2. Publishes screen orientation messages based on computed face positions
    """
    
    # Screen color mapping based on URDF
    SCREEN_COLORS = {
        1: "Red",
        2: "Green",
        3: "Blue",
        4: "Yellow",
        5: "Magenta",
        6: "Cyan"
    }
    SCREEN_ROTATIONS = {
        0: "bottom",
        1: "right",
        2: "top",
        3: "left"
    }
    
    def _get_screen_color_name(self, screen_id):
        """Get the color name for a screen ID"""
        return self.SCREEN_COLORS.get(screen_id, "Unknown")
    
    def __init__(self):
        super().__init__('dice_chassis_node')
        
        # Declare parameters
        self.declare_parameter('orientation_rate', 10.0)
        self.declare_parameter('imu_topic', '/imu/data')
        self.declare_parameter('alternative_imu_topic', '/data/imu')
        self.declare_parameter('rotation_threshold', 0.7)  # Stickiness factor for rotation changes
        self.declare_parameter('publish_to_topics', True)  # Publish to ROS topics vs just logging
        self.declare_parameter('edge_detection_frames', 2)  # Required consecutive detections for edge rotation

        # Get parameters
        self.orientation_rate = self.get_parameter('orientation_rate').get_parameter_value().double_value
        self.imu_topic = self.get_parameter('imu_topic').get_parameter_value().string_value
        self.alt_imu_topic = self.get_parameter('alternative_imu_topic').get_parameter_value().string_value
        self.rotation_threshold = self.get_parameter('rotation_threshold').get_parameter_value().double_value
        self.publish_to_topics = self.get_parameter('publish_to_topics').get_parameter_value().bool_value
        self.edge_detection_frames = self.get_parameter('edge_detection_frames').get_parameter_value().integer_value
        
        # Initialize publishers (only if publishing is enabled)
        if self.publish_to_topics:
            # Import message dependencies only when publishing
            if _import_ros_message_deps():
                self.chassis_orientation_pub = self.create_publisher(
                    ChassisOrientation, 
                    '/chassis/orientation', 
                    10
                )
                
                # Screen pose publishers - create one for each screen
                self.screen_pose_publishers = {}
                for screen_config in dice_config.screen_configs.values():
                    screen_id = screen_config.id  # Config now uses 1-6 directly
                    topic_name = f'/chassis/screen_{screen_id}_pose'
                    self.screen_pose_publishers[screen_id] = self.create_publisher(
                        ScreenPose,
                        topic_name,
                        10
                    )
            else:
                self.get_logger().warn('Screen orientation message dependencies not available - disabling topic publishing')
                self.chassis_orientation_pub = None
                self.screen_pose_publishers = {}
        else:
            self.chassis_orientation_pub = None
            self.screen_pose_publishers = {}
        # Vectorized orientation math
        _pkg_share = get_package_share_directory('dicemaster_central')
        _config_path = os.path.join(_pkg_share, 'resource', 'dice_geometry.yaml')
        self._dice_orientation = DiceOrientation(_config_path)
        self._last_orientation_result = None

        # Current IMU orientation quaternion (default: pi around X)
        self._imu_orientation = Quaternion(x=1.0, y=0.0, z=0.0, w=0.0)
        self.pose_lock = threading.Lock()
        self.last_pose_time = None
        self.imu_connected = False
        
        # Screen orientation state tracking with stickiness (always enabled)
        self.screen_rotations = {}  # screen_id -> current rotation
        self.screen_up_alignments = {}  # screen_id -> last up_alignment value
        self.screen_edge_rotations = {}  # screen_id -> last edge-based rotation
        self.screen_edge_detection_history = {}  # screen_id -> list of recent edge detections
        self.screen_edge_consecutive_count = {}  # screen_id -> count of consecutive same edge detections
        for screen_config in dice_config.screen_configs.values():
            screen_id = screen_config.id  # Config now uses 1-6 directly
            self.screen_rotations[screen_id] = screen_config.default_orientation
            self.screen_up_alignments[screen_id] = -1.0  # Start with fully down
            self.screen_edge_rotations[screen_id] = ConfigRotation.ROTATION_0
            self.screen_edge_detection_history[screen_id] = []  # Empty history
            self.screen_edge_consecutive_count[screen_id] = 0  # No consecutive detections yet
        
        # Subscribe to IMU data (try multiple topics)
        self.imu_sub = self.create_subscription(
            Imu,
            self.imu_topic,
            self.imu_callback,
            10
        )
        
        # Alternative IMU subscriber for /data/imu topic
        self.alt_imu_sub = self.create_subscription(
            Imu,
            self.alt_imu_topic,
            self.imu_callback,
            10
        )
        
        # Timer for orientation detection (10Hz, always enabled)
        self.orientation_timer = self.create_timer(1.0/self.orientation_rate, self.orientation_callback)

        self.get_logger().info('Dice chassis node initialized')
        self.get_logger().info(f'IMU topics: {self.imu_topic}, {self.alt_imu_topic}')
        self.get_logger().info('Screen orientation: always enabled')
        self.get_logger().info(f'Edge detection frames required: {self.edge_detection_frames}')
        self.get_logger().info(f'ROS topic publishing: {"enabled" if self.publish_to_topics else "disabled (console only)"}')
        self.get_logger().info('Using default pose until IMU data is received')

    
    def imu_callback(self, msg):
        """Callback for IMU data — store orientation and motion sensor data."""
        first_connect = False
        with self.pose_lock:
            self._imu_orientation = msg.orientation
            self.last_pose_time = time.time()
            if not self.imu_connected:
                self.imu_connected = True
                first_connect = True
        if first_connect:
            self.get_logger().info('IMU data connected - using live orientation')

    def _get_imu_quaternion(self) -> np.ndarray:
        """Extract the current IMU quaternion as [x, y, z, w] numpy array."""
        with self.pose_lock:
            o = self._imu_orientation
            return np.array([o.x, o.y, o.z, o.w])

    def orientation_callback(self):
        """Timer callback for orientation detection and publishing (10Hz)"""
        with self.pose_lock:
            pose_time = self.last_pose_time

        if pose_time is None or time.time() - pose_time > 1.0:
            if self.imu_connected and pose_time is not None:
                self.imu_connected = False
                self.get_logger().warn('IMU signal lost - maintaining last known orientation')
            return

        # Get orientations for all screens
        screen_orientations = self._get_all_screen_orientations()

        if not screen_orientations:
            self.get_logger().debug("No screen orientations detected, skipping publishing")
            return
            
        # Find top and bottom screens
        top_screen = max(screen_orientations, key=lambda x: x['up_alignment'])
        bottom_screen = min(screen_orientations, key=lambda x: x['up_alignment'])

        # Compute edge rotation for top screen only (edges only meaningful for top face)
        top_screen_id = top_screen['screen_id']
        new_rotation = self._calculate_screen_rotation_from_edges(top_screen_id)

        # Apply stickiness per screen — update rotation state for all screens
        for orientation in screen_orientations:
            screen_id = orientation['screen_id']
            old_alignment = self.screen_up_alignments.get(screen_id, -1.0)
            alignment_change = abs(orientation['up_alignment'] - old_alignment)

            if alignment_change > self.rotation_threshold:
                if screen_id == top_screen_id:
                    self.screen_rotations[screen_id] = new_rotation
                self.screen_up_alignments[screen_id] = orientation['up_alignment']

        # Publish or log the orientation data
        self._publish_or_log_orientation_data(top_screen, bottom_screen, screen_orientations)


    def _apply_sticky_selection(self, values_dict, margin=0.01, mode='max'):
        """Generic stickiness helper for selecting max/min values with margin
        
        Args:
            values_dict: Dict of {id: value} to select from
            margin: Margin for considering values as "clearly" different
            mode: 'max' for highest value, 'min' for lowest value
        
        Returns:
            Dict with same keys but potentially modified values for stickiness
        """
        if len(values_dict) < 2:
            return values_dict
        
        values_array = np.array(list(values_dict.values()))
        ids_array = np.array(list(values_dict.keys()))
        
        if mode == 'max':
            target_value = np.max(values_array)
        else:  # mode == 'min'
            target_value = np.min(values_array)
        
        modified_values = values_dict.copy()
        
        # Find the target value(s) and check if they're clearly separated
        target_mask = np.abs(values_array - target_value) < 1e-6
        target_indices = np.where(target_mask)[0]
        
        if len(target_indices) > 0:
            # Get the second-best value for comparison
            non_target_indices = np.where(~target_mask)[0]
            if len(non_target_indices) > 0:
                if mode == 'max':
                    second_best = np.max(values_array[non_target_indices])
                    separation = target_value - second_best
                else:
                    second_best = np.min(values_array[non_target_indices])
                    separation = second_best - target_value
                
                # If separation is less than margin, reduce confidence
                if separation < margin:
                    for idx in target_indices:
                        screen_id = ids_array[idx]
                        modified_values[screen_id] = values_dict[screen_id] * 0.5
        
        return modified_values
    
    def _get_all_screen_orientations(self):
        """Get orientations for all screens using vectorized orientation math."""
        imu_quat = self._get_imu_quaternion()
        self._last_orientation_result = self._dice_orientation.compute(imu_quat)
        result = self._last_orientation_result

        face_z = result['face_z']

        # Apply stickiness to face_z values (reduces jitter near ambiguous orientations)
        sticky_z = self._apply_sticky_selection(face_z, margin=0.01, mode='max')
        sticky_z = self._apply_sticky_selection(sticky_z, margin=0.01, mode='min')

        # Build orientation data (same format as before)
        orientations = []
        for sid in sorted(sticky_z.keys()):
            up_alignment = np.clip(sticky_z[sid] / 0.0508, -1.0, 1.0)
            orientations.append({
                'screen_id': sid,
                'up_alignment': float(up_alignment),
                'z_position': float(face_z[sid]),
                'frame_name': f'screen_{sid}_link',
            })

        return orientations
    
    def _calculate_screen_rotation_from_edges(self, screen_id):
        """Calculate screen rotation based on which edge is lowest (closest to gravity).

        Uses precomputed edge z values from DiceOrientation.compute().
        Only meaningful for the current top screen.
        Requires N consecutive same-edge detections before changing rotation.
        """
        result = self._last_orientation_result
        if result is None:
            return self.screen_edge_rotations.get(screen_id, ConfigRotation.ROTATION_0)

        # Use top_edge_z from compute() — already has the 4 edge z-values
        edge_positions = result['top_edge_z']

        # Apply stickiness to edge selection
        sticky_edges = self._apply_sticky_selection(edge_positions, margin=0.005, mode='min')

        # Find the lowest edge (most aligned with gravity)
        current_lowest_edge = min(sticky_edges.keys(), key=sticky_edges.get)

        # Debouncing: require consecutive detections before changing rotation
        detection_history = self.screen_edge_detection_history[screen_id]

        if len(detection_history) > 0 and detection_history[-1] == current_lowest_edge:
            self.screen_edge_consecutive_count[screen_id] += 1
        else:
            self.screen_edge_consecutive_count[screen_id] = 1

        detection_history.append(current_lowest_edge)
        if len(detection_history) > self.edge_detection_frames:
            detection_history.pop(0)

        consecutive_count = self.screen_edge_consecutive_count[screen_id]
        if consecutive_count >= self.edge_detection_frames:
            edge_to_rotation = {
                'bottom': ConfigRotation.ROTATION_0,
                'right': ConfigRotation.ROTATION_90,
                'top': ConfigRotation.ROTATION_180,
                'left': ConfigRotation.ROTATION_270,
            }
            new_rotation = edge_to_rotation.get(current_lowest_edge, ConfigRotation.ROTATION_0)
            current_rotation = self.screen_edge_rotations.get(screen_id, ConfigRotation.ROTATION_0)
            if new_rotation != current_rotation:
                self.screen_edge_rotations[screen_id] = new_rotation
                return new_rotation
            return current_rotation
        else:
            return self.screen_edge_rotations.get(screen_id, ConfigRotation.ROTATION_0)
            
    def _publish_or_log_orientation_data(self, top_screen, bottom_screen, screen_orientations):
        """Publish orientation data to ROS topics or log to console based on configuration"""
        
        # Publish to ROS topics if publishing is enabled and we have publishers
        if self.publish_to_topics and self.chassis_orientation_pub:
            # Dependencies should already be imported since we have publishers
            # Publish chassis orientation
            chassis_msg = ChassisOrientation()
            chassis_msg.top_screen_id = top_screen['screen_id']
            chassis_msg.bottom_screen_id = bottom_screen['screen_id']
            chassis_msg.stamp = self.get_clock().now().to_msg()
            self.chassis_orientation_pub.publish(chassis_msg)
            
            # Publish individual screen poses
            for orientation in screen_orientations:
                screen_id = orientation['screen_id']
                
                # Create and publish screen pose message
                screen_msg = ScreenPose()
                screen_msg.screen_id = screen_id
                screen_msg.rotation = self.screen_edge_rotations[screen_id]
                screen_msg.up_alignment = orientation['up_alignment']
                screen_msg.is_facing_up = (screen_id == top_screen['screen_id'] and 
                                         orientation['up_alignment'] > 0.7)
                screen_msg.stamp = self.get_clock().now().to_msg()
                
                if screen_id in self.screen_pose_publishers:
                    self.screen_pose_publishers[screen_id].publish(screen_msg)

        # Otherwise, just print to console
        else:
            # Info logging for screen positions with colors
            info_msg = "Screen positions: "
            top_color = self._get_screen_color_name(top_screen['screen_id'])
            bottom_color = self._get_screen_color_name(bottom_screen['screen_id'])
            info_msg += f"Top: {top_screen['screen_id']} ({top_color}), Bottom: {bottom_screen['screen_id']} ({bottom_color})\n"

            for screen in screen_orientations:
                screen_id = screen['screen_id']
                rotation = self.screen_rotations[screen_id]
                info_msg += f".   Screen {screen_id} ({self._get_screen_color_name(screen_id)}): {self.SCREEN_ROTATIONS[rotation]}\n"

            self.get_logger().info(info_msg)

    def destroy_node(self):
        """Clean shutdown"""
        self.get_logger().info('Shutting down chassis node')
        if hasattr(self, 'orientation_timer') and self.orientation_timer is not None:
            self.orientation_timer.cancel()
        super().destroy_node()


def main(args=None):
    import rclpy
    from rclpy.executors import SingleThreadedExecutor
    rclpy.init(args=args)
    node = None
    executor = None
    try:
        node = ChassisNode()
        executor = SingleThreadedExecutor()
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

