"""
This configures the ROS robot loading with dice.urdf, and subscribes to /dice_hw/imu/pose for the pose of the core of the dice. The remaining frames will need to be inferred from the tf2 transformation automatically for other nodes such as screen orientation detection. 
"""

import rclpy
from rclpy.node import Node
import rclpy.logging
from geometry_msgs.msg import Pose, TransformStamped
from sensor_msgs.msg import Imu
import tf2_ros
from tf2_ros import TransformBroadcaster, StaticTransformBroadcaster
import numpy as np
from scipy.spatial.transform import Rotation as R
import threading
import time

# Conditional imports for optional screen orientation functionality
ChassisOrientation = None
ScreenPose = None
dice_config = None
ConfigRotation = None

def _import_screen_orientation_deps():
    """Import screen orientation dependencies if needed"""
    global ChassisOrientation, ScreenPose, dice_config, ConfigRotation
    try:
        from dicemaster_central_msgs.msg import ChassisOrientation, ScreenPose
        from dicemaster_central.config import dice_config
        from dicemaster_central.constants import Rotation as ConfigRotation
        return True
    except ImportError as e:
        return False

class ChassisNode(Node):
    """
    ROS2 node that manages the dice robot chassis, loads URDF, and handles pose transformations.
    
    This node:
    1. Loads the dice.urdf robot description
    2. Subscribes to /dice_hw/imu/pose for robot orientation
    3. Publishes TF transformations for all robot frames
    4. Provides services for querying robot state
    """
    
    def __init__(self):
        super().__init__('dice_chassis_node')
        
        # Declare parameters
        self.declare_parameter('base_frame', 'base_link')
        self.declare_parameter('imu_frame', 'imu_link')
        self.declare_parameter('world_frame', 'world')
        self.declare_parameter('publish_rate', 50.0)
        self.declare_parameter('orientation_rate', 10.0)
        self.declare_parameter('imu_topic', '/imu/data')
        self.declare_parameter('alternative_imu_topic', '/data/imu')
        self.declare_parameter('rotation_threshold', 0.7)  # Stickiness factor for rotation changes
        self.declare_parameter('enable_screen_orientation', True)  # Enable screen orientation publishing
        
        # Get parameters
        self.base_frame = self.get_parameter('base_frame').get_parameter_value().string_value
        self.imu_frame = self.get_parameter('imu_frame').get_parameter_value().string_value
        self.world_frame = self.get_parameter('world_frame').get_parameter_value().string_value
        self.publish_rate = self.get_parameter('publish_rate').get_parameter_value().double_value
        self.orientation_rate = self.get_parameter('orientation_rate').get_parameter_value().double_value
        self.imu_topic = self.get_parameter('imu_topic').get_parameter_value().string_value
        self.alt_imu_topic = self.get_parameter('alternative_imu_topic').get_parameter_value().string_value
        self.rotation_threshold = self.get_parameter('rotation_threshold').get_parameter_value().double_value
        self.enable_screen_orientation = self.get_parameter('enable_screen_orientation').get_parameter_value().bool_value
        
        # Initialize screen orientation functionality if enabled
        self.screen_orientation_enabled = False
        if self.enable_screen_orientation:
            if _import_screen_orientation_deps():
                self.screen_orientation_enabled = True
                self.get_logger().info('Screen orientation functionality enabled')
            else:
                self.get_logger().warn('Screen orientation functionality requested but dependencies not available')
        else:
            self.get_logger().info('Screen orientation functionality disabled')
        
        # Load URDF (removed - handled by robot_state_publisher)
        # self.robot_description = self._load_urdf()
        
        # Publishers for orientation and screen poses (only if enabled)
        if self.screen_orientation_enabled:
            self.chassis_orientation_pub = self.create_publisher(
                ChassisOrientation, 
                '/chassis/orientation', 
                10
            )
            
            # Screen pose publishers - create one for each screen
            self.screen_pose_publishers = {}
            for screen_config in dice_config.screen_configs:
                screen_id = screen_config.id  # Config now uses 1-6 directly
                topic_name = f'/chassis/screen_{screen_id}_pose'
                self.screen_pose_publishers[screen_id] = self.create_publisher(
                    ScreenPose,
                    topic_name,
                    10
                )
        else:
            self.chassis_orientation_pub = None
            self.screen_pose_publishers = {}
        # TF2 setup
        self.tf_buffer = tf2_ros.Buffer()
        self.tf_listener = tf2_ros.TransformListener(self.tf_buffer, self)
        self.tf_broadcaster = TransformBroadcaster(self)
        self.static_tf_broadcaster = StaticTransformBroadcaster(self)
        
        # Current robot pose - initialize with default (identity) pose
        self.current_pose = Pose()
        self.current_pose.position.x = 0.0
        self.current_pose.position.y = 0.0
        self.current_pose.position.z = 0.0
        self.current_pose.orientation.x = 0.0
        self.current_pose.orientation.y = 0.0
        self.current_pose.orientation.z = 0.0
        self.current_pose.orientation.w = 1.0  # Identity quaternion
        self.pose_lock = threading.Lock()
        self.last_pose_time = None
        self.imu_connected = False
        
        # Screen orientation state tracking with stickiness (only if enabled)
        if self.screen_orientation_enabled:
            self.screen_rotations = {}  # screen_id -> current rotation
            self.screen_up_alignments = {}  # screen_id -> last up_alignment value
            for screen_config in dice_config.screen_configs:
                screen_id = screen_config.id  # Config now uses 1-6 directly
                self.screen_rotations[screen_id] = screen_config.default_orientation
                self.screen_up_alignments[screen_id] = -1.0  # Start with fully down
        else:
            self.screen_rotations = {}
            self.screen_up_alignments = {}
        
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
        
        # Legacy subscriber for existing pose topic (for backward compatibility)
        self.pose_sub = self.create_subscription(
            Pose,
            '/dice_hw/imu/pose',
            self.pose_callback,
            10
        )
        
        # Timer for publishing transforms (50Hz)
        self.timer = self.create_timer(1.0/self.publish_rate, self.timer_callback)
        
        # Timer for orientation detection (10Hz, only if screen orientation is enabled)
        if self.screen_orientation_enabled:
            self.orientation_timer = self.create_timer(1.0/self.orientation_rate, self.orientation_callback)
        else:
            self.orientation_timer = None
        
        # Publish static transforms (IMU to base_link)
        self._publish_static_transforms()
        
        # Robot description is now handled by robot_state_publisher
        # self._publish_robot_description()
        
        self.get_logger().info('Dice chassis node initialized')
        self.get_logger().info(f'Base frame: {self.base_frame}')
        self.get_logger().info(f'IMU frame: {self.imu_frame}')
        self.get_logger().info(f'IMU topics: {self.imu_topic}, {self.alt_imu_topic}')
        self.get_logger().info(f'Screen orientation: {"enabled" if self.screen_orientation_enabled else "disabled"}')
        self.get_logger().info('Using default pose until IMU data is received')
        
    def _publish_static_transforms(self):
        """Publish static transforms for the robot"""
        # IMU is assumed to be at the center of the base_link
        # This transform defines the relationship between base_link and imu_link
        static_transform = TransformStamped()
        static_transform.header.stamp = self.get_clock().now().to_msg()
        static_transform.header.frame_id = self.base_frame
        static_transform.child_frame_id = self.imu_frame
        
        # IMU is at the center of the dice (no translation)
        static_transform.transform.translation.x = 0.0
        static_transform.transform.translation.y = 0.0
        static_transform.transform.translation.z = 0.0
        
        # IMU frame aligned with base_link (no rotation)
        static_transform.transform.rotation.x = 0.0
        static_transform.transform.rotation.y = 0.0
        static_transform.transform.rotation.z = 0.0
        static_transform.transform.rotation.w = 1.0
        
        self.static_tf_broadcaster.sendTransform(static_transform)
        self.get_logger().info(f'Published static transform: {self.base_frame} -> {self.imu_frame}')
    
    def pose_callback(self, msg):
        """Callback for IMU pose messages (legacy support)"""
        with self.pose_lock:
            self.current_pose = msg
            self.last_pose_time = time.time()
            
        # Log pose updates (debug)
        if self.get_logger().get_effective_level() <= rclpy.logging.LoggingSeverity.DEBUG:
            q = msg.orientation
            self.get_logger().debug(f'Received pose: q=({q.w:.3f}, {q.x:.3f}, {q.y:.3f}, {q.z:.3f})')
    
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
        
        # Always publish the world to base_link transform to ensure world frame exists
        transform = TransformStamped()
        transform.header.stamp = self.get_clock().now().to_msg()
        transform.header.frame_id = self.world_frame
        transform.child_frame_id = self.base_frame
        
        # Position (dice position is always at origin)
        transform.transform.translation.x = current_pose.position.x
        transform.transform.translation.y = current_pose.position.y
        transform.transform.translation.z = current_pose.position.z
        
        # Use current orientation if available, otherwise use identity
        if pose_time is not None and (time.time() - pose_time <= 1.0):
            # Use live IMU orientation
            transform.transform.rotation.x = current_pose.orientation.x
            transform.transform.rotation.y = current_pose.orientation.y
            transform.transform.rotation.z = current_pose.orientation.z
            transform.transform.rotation.w = current_pose.orientation.w
        else:
            # Use identity orientation (no rotation) when no IMU data
            transform.transform.rotation.x = 0.0
            transform.transform.rotation.y = 0.0
            transform.transform.rotation.z = 0.0
            transform.transform.rotation.w = 1.0
            
            # Log warning if pose data is stale (but not on first run)
            if pose_time is not None:
                self.get_logger().warn('Using default orientation - IMU pose data is stale', throttle_duration_sec=5.0)
        
        self.tf_broadcaster.sendTransform(transform)
    
    def orientation_callback(self):
        """Timer callback for orientation detection and publishing (10Hz)"""
        if not self.screen_orientation_enabled:
            return
            
        with self.pose_lock:
            current_pose = self.current_pose
            pose_time = self.last_pose_time
        
        if pose_time is None:
            # No pose data received yet
            return
            
        # Check if pose data is recent (within 1 second)
        if time.time() - pose_time > 1.0:
            return
            
        # Calculate orientations for all screens
        screen_orientations = self._calculate_all_screen_orientations(current_pose)
        
        if not screen_orientations:
            return
            
        # Find top and bottom screens
        top_screen = max(screen_orientations, key=lambda x: x['up_alignment'])
        bottom_screen = min(screen_orientations, key=lambda x: x['up_alignment'])
        
        # Publish chassis orientation
        chassis_msg = ChassisOrientation()
        chassis_msg.top_screen_id = top_screen['screen_id']
        chassis_msg.bottom_screen_id = bottom_screen['screen_id']
        chassis_msg.stamp = self.get_clock().now().to_msg()
        self.chassis_orientation_pub.publish(chassis_msg)
        
        # Publish individual screen poses with stickiness
        for orientation in screen_orientations:
            screen_id = orientation['screen_id']
            
            # Calculate rotation based on gravity direction and default orientation
            new_rotation = self._calculate_screen_rotation(orientation, screen_id)
            
            # Apply stickiness - only change rotation if alignment changes significantly
            old_alignment = self.screen_up_alignments.get(screen_id, -1.0)
            alignment_change = abs(orientation['up_alignment'] - old_alignment)
            
            if alignment_change > self.rotation_threshold:
                self.screen_rotations[screen_id] = new_rotation
                self.screen_up_alignments[screen_id] = orientation['up_alignment']
            
            # Publish screen pose
            screen_msg = ScreenPose()
            screen_msg.screen_id = screen_id
            screen_msg.rotation = self.screen_rotations[screen_id]
            screen_msg.up_alignment = orientation['up_alignment']
            screen_msg.is_facing_up = (screen_id == top_screen['screen_id'] and 
                                     orientation['up_alignment'] > 0.7)
            screen_msg.stamp = self.get_clock().now().to_msg()
            
            if screen_id in self.screen_pose_publishers:
                self.screen_pose_publishers[screen_id].publish(screen_msg)
    
    def _calculate_all_screen_orientations(self, pose):
        """Calculate orientations for all screens based on current pose"""
        if not self.screen_orientation_enabled:
            return []
            
        # Convert quaternion to rotation matrix
        q = pose.orientation
        r = R.from_quat([q.x, q.y, q.z, q.w])
        
        # Get gravity vector in robot frame
        gravity_world = np.array([0, 0, -1])  # Gravity points down in world frame
        
        # Screen normal definitions (based on dice geometry)
        screen_normals = {
            1: np.array([0, 0, 1]),   # Top face normal (+Z)
            2: np.array([0, 1, 0]),   # Right face normal (+Y)
            3: np.array([1, 0, 0]),   # Back face normal (+X)
            4: np.array([0, -1, 0]),  # Left face normal (-Y)
            5: np.array([-1, 0, 0]),  # Front face normal (-X)
            6: np.array([0, 0, -1]),  # Bottom face normal (-Z)
        }
        
        orientations = []
        for screen_config in dice_config.screen_configs:
            screen_id = screen_config.id  # Config now uses 1-6 directly
            
            if screen_id not in screen_normals:
                continue
                
            # Transform screen normal to world frame
            screen_normal_world = r.apply(screen_normals[screen_id])
            
            # Calculate alignment with "up" direction (opposite to gravity)
            up_alignment = np.dot(screen_normal_world, -gravity_world)
            
            orientations.append({
                'screen_id': screen_id,
                'up_alignment': float(up_alignment),
                'normal_world': screen_normal_world,
                'gravity_robot': r.inv().apply(gravity_world)
            })
            
        return orientations
    
    def _calculate_screen_rotation(self, orientation, screen_id):
        """Calculate the rotation needed for a screen based on gravity direction and default orientation"""
        if not self.screen_orientation_enabled:
            return 0
            
        # Get the screen's configuration
        screen_config = None
        for config in dice_config.screen_configs:
            if config.id == screen_id:  # Config now uses 1-6 directly
                screen_config = config
                break
                
        if screen_config is None:
            return 0
            
        # For now, use the default orientation from config
        # More sophisticated gravity-based rotation calculation can be added here
        default_rotation = screen_config.default_orientation
        
        # Convert from ConfigRotation enum to integer
        if hasattr(default_rotation, 'value'):
            return default_rotation.value
        else:
            return int(default_rotation)
    
    def get_current_pose(self):
        """Get the current robot pose"""
        with self.pose_lock:
            return self.current_pose
    
    def destroy_node(self):
        """Clean shutdown"""
        self.get_logger().info('Shutting down chassis node')
        if hasattr(self, 'orientation_timer') and self.orientation_timer is not None:
            self.orientation_timer.cancel()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    
    node = ChassisNode()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()

