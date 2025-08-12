"""
Dice chassis node for managing robot pose transformations and screen orientation detection.
Subscribes to IMU data and publishes TF transforms and screen orientation messages.
"""

import rclpy
from rclpy.node import Node
import rclpy.logging
import rclpy.duration
from geometry_msgs.msg import Pose, TransformStamped
from sensor_msgs.msg import Imu
import tf2_ros
from tf2_ros import TransformBroadcaster, StaticTransformBroadcaster
import numpy as np
import threading
import time
from time import perf_counter

# Debugging for macos
# from config_copy import dice_config
# from constants_copy import Rotation as ConfigRotation

from dicemaster_central.constants import Rotation as ConfigRotation
from dicemaster_central.config import dice_config

# from constants_copy import Rotation as ConfigRotation
# from config_copy import dice_config

# class LatchedValue:
#     def __init__(self):
#         self.last_val = 

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
    ROS2 node that manages the dice robot chassis and handles pose transformations.
    
    This node:
    1. Subscribes to IMU data for robot orientation
    2. Publishes TF transformations for all robot frames
    3. Publishes screen orientation messages based on tf frame positions
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
        self.declare_parameter('base_frame', 'base_link')
        self.declare_parameter('imu_frame', 'imu_link')
        self.declare_parameter('world_frame', 'world')
        self.declare_parameter('publish_rate', 10.0)
        self.declare_parameter('orientation_rate', 10.0)
        self.declare_parameter('imu_topic', '/imu/data')
        self.declare_parameter('alternative_imu_topic', '/data/imu')
        self.declare_parameter('rotation_threshold', 0.7)  # Stickiness factor for rotation changes
        self.declare_parameter('publish_to_topics', True)  # Publish to ROS topics vs just logging
        self.declare_parameter('edge_detection_frames', 5)  # Required consecutive detections for edge rotation
        
        # Get parameters
        self.base_frame = self.get_parameter('base_frame').get_parameter_value().string_value
        self.imu_frame = self.get_parameter('imu_frame').get_parameter_value().string_value
        self.world_frame = self.get_parameter('world_frame').get_parameter_value().string_value
        self.publish_rate = self.get_parameter('publish_rate').get_parameter_value().double_value
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
        # TF2 setup
        self.tf_buffer = tf2_ros.Buffer()
        self.tf_listener = tf2_ros.TransformListener(self.tf_buffer, self)
        self.tf_broadcaster = TransformBroadcaster(self)
        self.static_tf_broadcaster = StaticTransformBroadcaster(self)
        
        # Current robot pose - initialize with default pose rotated π around roll axis
        self.current_pose = Pose()
        self.current_pose.position.x = 0.0
        self.current_pose.position.y = 0.0
        self.current_pose.position.z = 0.0
        self.current_pose.orientation.x = 1.0  # π rotation around X-axis (roll)
        self.current_pose.orientation.y = 0.0
        self.current_pose.orientation.z = 0.0
        self.current_pose.orientation.w = 0.0  # π rotation quaternion
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
            self.screen_edge_rotations[screen_id] = 0  # Start with 0 rotation
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
        
        # Timer for publishing transforms (50Hz)
        self.timer = self.create_timer(1.0/self.publish_rate, self.timer_callback)
        
        # Timer for orientation detection (10Hz, always enabled)
        self.orientation_timer = self.create_timer(1.0/self.orientation_rate, self.orientation_callback)

        self.get_logger().info('Dice chassis node initialized')
        self.get_logger().info(f'Base frame: {self.base_frame}')
        self.get_logger().info(f'IMU frame: {self.imu_frame}')
        self.get_logger().info(f'IMU topics: {self.imu_topic}, {self.alt_imu_topic}')
        self.get_logger().info('Screen orientation: always enabled')
        self.get_logger().info(f'Edge detection frames required: {self.edge_detection_frames}')
        self.get_logger().info(f'ROS topic publishing: {"enabled" if self.publish_to_topics else "disabled (console only)"}')
        self.get_logger().info('Using default pose until IMU data is received')

    
    def imu_callback(self, msg):
        """Callback for IMU data - converts sensor_msgs/Imu to internal Pose"""
        # Create pose from IMU orientation
        pose = Pose()
        pose.position.x = 0.0  # IMU only provides orientation
        pose.position.y = 0.0
        pose.position.z = 0.0
        pose.orientation = msg.orientation
        
        # Update internal pose
        with self.pose_lock:
            self.current_pose = pose
            self.last_pose_time = time.time()
            if not self.imu_connected:
                self.imu_connected = True
                self.get_logger().info('IMU data connected - using live orientation')
        
        # Log IMU updates (debug)
        if self.get_logger().get_effective_level() <= rclpy.logging.LoggingSeverity.DEBUG:
            q = msg.orientation
            self.get_logger().debug(f'Received IMU: q=({q.w:.3f}, {q.x:.3f}, {q.y:.3f}, {q.z:.3f})')
    
    def timer_callback(self):
        """Timer callback for publishing transforms"""
        # Publish dynamic transforms
        self._publish_dynamic_transforms()
    
    def _publish_dynamic_transforms(self):
        """Publish dynamic transforms based on current pose"""
        with self.pose_lock:
            current_pose = self.current_pose
            pose_time = self.last_pose_time
        
        # Publish the world to imu_link transform (imu_link is now the root frame)
        transform = TransformStamped()
        transform.header.stamp = self.get_clock().now().to_msg()
        transform.header.frame_id = self.world_frame
        transform.child_frame_id = self.imu_frame  # Changed from base_frame to imu_frame
        
        # Position (dice position is always at origin)
        transform.transform.translation.x = current_pose.position.x
        transform.transform.translation.y = current_pose.position.y
        transform.transform.translation.z = current_pose.position.z
        
        # Always use current pose orientation (maintain last known orientation when stale)
        transform.transform.rotation.x = current_pose.orientation.x
        transform.transform.rotation.y = current_pose.orientation.y
        transform.transform.rotation.z = current_pose.orientation.z
        transform.transform.rotation.w = current_pose.orientation.w
        
        # Log warning if pose data is stale (but not on first run)
        if pose_time is not None and (time.time() - pose_time > 1.0):
            self.get_logger().warn('IMU pose data is stale - maintaining last known orientation', throttle_duration_sec=5.0)
        
        self.tf_broadcaster.sendTransform(transform)
    
    def orientation_callback(self):
        """Timer callback for orientation detection and publishing (10Hz)"""
        st = perf_counter()
        with self.pose_lock:
            pose_time = self.last_pose_time

        if pose_time is None or time.time() - pose_time > 1.0:
            # No pose data received yet
            return

        # Get orientations for all screens using tf frames
        screen_orientations = self._get_all_screen_orientations()

        if not screen_orientations:
            print("No screen orientations detected, skipping publishing")
            return
            
        # Find top and bottom screens
        top_screen = max(screen_orientations, key=lambda x: x['up_alignment'])
        bottom_screen = min(screen_orientations, key=lambda x: x['up_alignment'])

        # Always compute individual screen poses with stickiness
        for orientation in screen_orientations:
            screen_id = orientation['screen_id']
            
            # Calculate rotation based on gravity direction and default orientation
            new_rotation = self._calculate_screen_rotation_from_edges(screen_id)
            # Apply stickiness - only change rotation if alignment changes significantly
            old_alignment = self.screen_up_alignments.get(screen_id, -1.0)
            alignment_change = abs(orientation['up_alignment'] - old_alignment)
            
            if alignment_change > self.rotation_threshold:
                self.screen_rotations[screen_id] = new_rotation
                self.screen_up_alignments[screen_id] = orientation['up_alignment']

        # Publish or log the orientation data
        self._publish_or_log_orientation_data(top_screen, bottom_screen, screen_orientations)


    def _get_screen_z_position(self, screen_id):
        """Get the z position of a single screen frame in world coordinates"""
        screen_frame = f'screen_{screen_id}_link'
        
        try:
            # Try with latest available transform instead of current time
            transform = self.tf_buffer.lookup_transform(
                self.world_frame,
                screen_frame,
                rclpy.time.Time(),  # Use latest available transform
                timeout=rclpy.duration.Duration(seconds=0.01)  # Increased timeout
            )
            return transform.transform.translation.z
        except tf2_ros.LookupException as e:
            self.get_logger().info(f'LookupException for {screen_frame}: {e}')
            return None
        except tf2_ros.ExtrapolationException as e:
            self.get_logger().info(f'ExtrapolationException for {screen_frame}: {e}')
            return None
        except Exception as e:
            self.get_logger().info(f'Other exception for {screen_frame}: {e}')
            return None
    
    def _calculate_up_alignment(self, z_position):
        """Convert z position to up_alignment value [-1, 1]"""
        # The dice has screens at ±0.0508m, so max range is about 0.1016m
        up_alignment = z_position / 0.0508  # This gives -1 to +1 for bottom to top
        return max(-1.0, min(1.0, up_alignment))  # Clamp to [-1, 1]
    
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
        """Get orientations for all screens based on tf frame positions"""
        st = perf_counter()
        # Get z positions for all screens
        screen_positions = {}
        for screen_config in dice_config.screen_configs.values():
            screen_id = screen_config.id
            z_position = self._get_screen_z_position(screen_id)
            if z_position is not None:
                screen_positions[screen_id] = z_position

        if not screen_positions:
            self.get_logger().info("No screen positions detected, cannot determine orientations")
            return []
            
        # Apply stickiness factor using generic helper
        sticky_positions = self._apply_sticky_selection(screen_positions, margin=0.01, mode='max')
        sticky_positions = self._apply_sticky_selection(sticky_positions, margin=0.01, mode='min')
        
        # Build orientation data
        orientations = []
        for screen_id, z_position in sticky_positions.items():
            up_alignment = self._calculate_up_alignment(z_position)
            orientations.append({
                'screen_id': screen_id,
                'up_alignment': float(up_alignment),
                'z_position': float(screen_positions[screen_id]),  # Use original z for debug
                'frame_name': f'screen_{screen_id}_link'
            })
        
        return orientations
    
    def _get_screen_edge_positions(self, screen_id):
        """Get the z positions of all edge frames for a screen"""
        edge_names = ['top', 'right', 'bottom', 'left']
        edge_positions = {}
        
        for edge_name in edge_names:
            edge_frame = f'screen_{screen_id}_edge_{edge_name}'
            try:
                transform = self.tf_buffer.lookup_transform(
                    self.world_frame,
                    edge_frame,
                    rclpy.time.Time(),  # Use latest available transform
                    timeout=rclpy.duration.Duration(seconds=0.01)  # Much shorter timeout
                )
                edge_positions[edge_name] = transform.transform.translation.z
                print(f"Edge {edge_name} position for screen {screen_id}: {edge_positions[edge_name]:.4f}")
            except (tf2_ros.LookupException, tf2_ros.ExtrapolationException, Exception):
                # Skip this edge if transform not available - don't log to avoid spam
                pass
                
        return edge_positions if edge_positions else None
    
    def _calculate_screen_rotation_from_edges(self, screen_id):
        """Calculate screen rotation based on which edge is lowest (closest to gravity)
        
        Only updates rotation after detecting the same edge for 10 consecutive frames.
        If the edge changes within the 10 frames, the counter resets.
        """
        edge_positions = self._get_screen_edge_positions(screen_id)
        if not edge_positions:
            # No edge data - keep current rotation and reset detection history
            self.screen_edge_detection_history[screen_id] = []
            self.screen_edge_consecutive_count[screen_id] = 0
            return self.screen_edge_rotations.get(screen_id, ConfigRotation.ROTATION_0)
            
        # Apply stickiness to edge selection
        sticky_edges = self._apply_sticky_selection(edge_positions, margin=0.005, mode='min')
        
        # Find the lowest edge (most aligned with gravity)  
        current_lowest_edge = min(sticky_edges.keys(), key=sticky_edges.get)
        
        # Update detection history
        detection_history = self.screen_edge_detection_history[screen_id]
        
        # Check if this is the same edge as the last detection
        if len(detection_history) > 0 and detection_history[-1] == current_lowest_edge:
            # Same edge as last time - increment consecutive count
            self.screen_edge_consecutive_count[screen_id] += 1
        else:
            # Different edge - reset consecutive count and start new sequence
            self.screen_edge_consecutive_count[screen_id] = 1
        
        # Add current detection to history (keep only recent detections)
        detection_history.append(current_lowest_edge)
        if len(detection_history) > self.edge_detection_frames:
            detection_history.pop(0)  # Remove oldest detection
        
        # Check if we have enough consecutive detections
        consecutive_count = self.screen_edge_consecutive_count[screen_id]
        if consecutive_count >= self.edge_detection_frames:
            # We have enough consecutive detections - calculate new rotation
            
            # Map edge names to rotation values
            edge_to_rotation = {
                'bottom': ConfigRotation.ROTATION_0,    # Already at bottom
                'right': ConfigRotation.ROTATION_90,    # Rotate 90° clockwise
                'top': ConfigRotation.ROTATION_180,     # Rotate 180°
                'left': ConfigRotation.ROTATION_270     # Rotate 270° clockwise
            }
            
            new_rotation = edge_to_rotation.get(current_lowest_edge, ConfigRotation.ROTATION_0)
            if screen_id == 2:
                self.get_logger().info(f"Screen 2 rotation: {new_rotation}")

            # Check if this is actually a change from current rotation
            current_rotation = self.screen_edge_rotations.get(screen_id, ConfigRotation.ROTATION_0)
            if new_rotation != current_rotation:
                # Update rotation
                self.screen_edge_rotations[screen_id] = new_rotation
                self.get_logger().info(
                    f"Screen {screen_id} rotation updated to {new_rotation} "
                    f"after {consecutive_count} consecutive detections of '{current_lowest_edge}' edge"
                )
                return new_rotation
            else:
                # Same rotation - no change needed
                return current_rotation
        else:
            # Not enough consecutive detections yet - keep current rotation
            current_rotation = self.screen_edge_rotations.get(screen_id, ConfigRotation.ROTATION_0)
            self.get_logger().debug(
                f"Screen {screen_id}: {consecutive_count}/{self.edge_detection_frames} "
                f"consecutive detections of '{current_lowest_edge}' edge"
            )
            return current_rotation
            
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
        # else:
        # Info logging for screen positions with colors
        info_msg = "Screen positions: "
        top_color = self._get_screen_color_name(top_screen['screen_id'])
        bottom_color = self._get_screen_color_name(bottom_screen['screen_id'])
        info_msg += f"Top: {top_screen['screen_id']} ({top_color}), Bottom: {bottom_screen['screen_id']} ({bottom_color})\n"

        for screen in screen_orientations:
            screen_id = screen['screen_id']
            rotation = self.screen_rotations[screen_id]
            info_msg += f".   Screen {screen_id} ({self._get_screen_color_name(screen_id)}): {self.SCREEN_ROTATIONS[rotation]}\n"

        # self.get_logger().info(info_msg)

    def destroy_node(self):
        """Clean shutdown"""
        self.get_logger().info('Shutting down chassis node')
        if hasattr(self, 'orientation_timer') and self.orientation_timer is not None:
            self.orientation_timer.cancel()
        super().destroy_node()


def main(args=None):
    import rclpy
    from rclpy.executors import MultiThreadedExecutor
    
    rclpy.init(args=args)
    
    node = None
    executor = None
    try:
        node = ChassisNode()
        
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

if __name__ == '__main__':
    main()

