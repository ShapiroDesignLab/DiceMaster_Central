"""
This configures the ROS robot loading with dice.urdf, and subscribes to /dice_hw/imu/pose for the pose of the core of the dice. The remaining frames will need to be inferred from the tf2 transformation automatically for other nodes such as screen orientation detection. 
"""

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Pose, TransformStamped
from std_msgs.msg import String
import tf2_ros
import tf2_geometry_msgs
from tf2_ros import TransformBroadcaster, StaticTransformBroadcaster
from math import sin, cos, sqrt, atan2, pi
import numpy as np
from scipy.spatial.transform import Rotation as R
import threading
import time
import os

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
        self.declare_parameter('urdf_path', '/home/dice/DiceMaster/DiceMaster_Central/resource/dice.urdf')
        self.declare_parameter('base_frame', 'base_link')
        self.declare_parameter('imu_frame', 'imu_link')
        self.declare_parameter('world_frame', 'world')
        self.declare_parameter('publish_rate', 50.0)
        
        # Get parameters
        self.urdf_path = self.get_parameter('urdf_path').get_parameter_value().string_value
        self.base_frame = self.get_parameter('base_frame').get_parameter_value().string_value
        self.imu_frame = self.get_parameter('imu_frame').get_parameter_value().string_value
        self.world_frame = self.get_parameter('world_frame').get_parameter_value().string_value
        self.publish_rate = self.get_parameter('publish_rate').get_parameter_value().double_value
        
        # Load URDF
        self.robot_description = self._load_urdf()
        
        # Publishers
        self.robot_description_pub = self.create_publisher(
            String, '/robot_description', 10)
        
        # TF2 setup
        self.tf_buffer = tf2_ros.Buffer()
        self.tf_listener = tf2_ros.TransformListener(self.tf_buffer, self)
        self.tf_broadcaster = TransformBroadcaster(self)
        self.static_tf_broadcaster = StaticTransformBroadcaster(self)
        
        # Current robot pose
        self.current_pose = Pose()
        self.current_pose.orientation.w = 1.0  # Identity quaternion
        self.pose_lock = threading.Lock()
        self.last_pose_time = None
        
        # Subscribe to IMU pose
        self.pose_sub = self.create_subscription(
            Pose,
            '/dice_hw/imu/pose',
            self.pose_callback,
            10
        )
        
        # Timer for publishing transforms and robot description
        self.timer = self.create_timer(1.0/self.publish_rate, self.timer_callback)
        
        # Publish static transforms (IMU to base_link)
        self._publish_static_transforms()
        
        # Publish robot description
        self._publish_robot_description()
        
        self.get_logger().info(f'Dice chassis node initialized')
        self.get_logger().info(f'URDF loaded from: {self.urdf_path}')
        self.get_logger().info(f'Base frame: {self.base_frame}')
        self.get_logger().info(f'IMU frame: {self.imu_frame}')
        
    def _load_urdf(self):
        """Load URDF file and return its contents"""
        try:
            if not os.path.exists(self.urdf_path):
                self.get_logger().error(f'URDF file not found: {self.urdf_path}')
                return ""
                
            with open(self.urdf_path, 'r') as file:
                urdf_content = file.read()
                
            self.get_logger().info(f'Successfully loaded URDF: {len(urdf_content)} characters')
            return urdf_content
            
        except Exception as e:
            self.get_logger().error(f'Failed to load URDF: {str(e)}')
            return ""
    
    def _publish_robot_description(self):
        """Publish robot description to /robot_description topic"""
        if self.robot_description:
            msg = String()
            msg.data = self.robot_description
            self.robot_description_pub.publish(msg)
            self.get_logger().info('Published robot description')
    
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
        """Callback for IMU pose messages"""
        with self.pose_lock:
            self.current_pose = msg
            self.last_pose_time = time.time()
            
        # Log pose updates (debug)
        if self.get_logger().get_effective_level() <= rclpy.logging.LoggingSeverity.DEBUG:
            q = msg.orientation
            self.get_logger().debug(f'Received pose: q=({q.w:.3f}, {q.x:.3f}, {q.y:.3f}, {q.z:.3f})')
    
    def timer_callback(self):
        """Timer callback for publishing transforms and robot description"""
        # Publish robot description periodically
        self._publish_robot_description()
        
        # Publish dynamic transforms
        self._publish_dynamic_transforms()
    
    def _publish_dynamic_transforms(self):
        """Publish dynamic transforms based on current pose"""
        with self.pose_lock:
            current_pose = self.current_pose
            pose_time = self.last_pose_time
        
        if pose_time is None:
            # No pose data received yet
            return
        
        # Check if pose data is recent (within 1 second)
        if time.time() - pose_time > 1.0:
            self.get_logger().warn('IMU pose data is stale', throttle_duration_sec=5.0)
            return
        
        # Publish transform from world to base_link
        transform = TransformStamped()
        transform.header.stamp = self.get_clock().now().to_msg()
        transform.header.frame_id = self.world_frame
        transform.child_frame_id = self.base_frame
        
        # Position (IMU only provides orientation, so position is fixed)
        transform.transform.translation.x = current_pose.position.x
        transform.transform.translation.y = current_pose.position.y
        transform.transform.translation.z = current_pose.position.z
        
        # Orientation from IMU
        transform.transform.rotation.x = current_pose.orientation.x
        transform.transform.rotation.y = current_pose.orientation.y
        transform.transform.rotation.z = current_pose.orientation.z
        transform.transform.rotation.w = current_pose.orientation.w
        
        self.tf_broadcaster.sendTransform(transform)
    
    def get_current_pose(self):
        """Get the current robot pose"""
        with self.pose_lock:
            return self.current_pose
    
    def get_screen_orientation(self, screen_id):
        """
        Get the current orientation of a specific screen based on robot pose.
        
        Args:
            screen_id: Screen ID (1-6)
            
        Returns:
            dict: Screen orientation info including gravity direction
        """
        with self.pose_lock:
            current_pose = self.current_pose
        
        if self.last_pose_time is None:
            return None
        
        # Convert quaternion to rotation matrix
        q = current_pose.orientation
        r = R.from_quat([q.x, q.y, q.z, q.w])
        
        # Get gravity vector in robot frame
        gravity_world = np.array([0, 0, -1])  # Gravity points down in world frame
        gravity_robot = r.inv().apply(gravity_world)
        
        # Screen frame definitions (from URDF)
        screen_frames = {
            1: 'screen_1_link',  # Top face (+Z)
            2: 'screen_2_link',  # Right face (+Y)
            3: 'screen_3_link',  # Back face (+X)
            4: 'screen_4_link',  # Left face (-Y)
            5: 'screen_5_link',  # Front face (-X)
            6: 'screen_6_link',  # Bottom face (-Z)
        }
        
        if screen_id not in screen_frames:
            return None
        
        # Calculate which screen is most "up" (opposite to gravity)
        screen_normals = {
            1: np.array([0, 0, 1]),   # Top face normal
            2: np.array([0, 1, 0]),   # Right face normal
            3: np.array([1, 0, 0]),   # Back face normal
            4: np.array([0, -1, 0]),  # Left face normal
            5: np.array([-1, 0, 0]),  # Front face normal
            6: np.array([0, 0, -1]),  # Bottom face normal
        }
        
        # Transform screen normal to world frame
        screen_normal_world = r.apply(screen_normals[screen_id])
        
        # Calculate alignment with "up" direction (opposite to gravity)
        up_alignment = np.dot(screen_normal_world, -gravity_world)
        
        return {
            'screen_id': screen_id,
            'frame_id': screen_frames[screen_id],
            'normal_world': screen_normal_world.tolist(),
            'up_alignment': float(up_alignment),
            'is_facing_up': up_alignment > 0.7,  # Threshold for "facing up"
            'gravity_direction': gravity_robot.tolist()
        }
    
    def get_top_facing_screen(self):
        """Get the screen ID that is currently facing up (most aligned with -gravity)"""
        orientations = []
        for screen_id in range(1, 7):
            orientation = self.get_screen_orientation(screen_id)
            if orientation:
                orientations.append(orientation)
        
        if not orientations:
            return None
        
        # Find screen with highest up_alignment
        top_screen = max(orientations, key=lambda x: x['up_alignment'])
        return top_screen['screen_id'] if top_screen['up_alignment'] > 0.5 else None
    
    def destroy_node(self):
        """Clean shutdown"""
        self.get_logger().info('Shutting down chassis node')
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

