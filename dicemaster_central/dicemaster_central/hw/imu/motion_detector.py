"""
DiceMaster Motion Detection Module

USAGE IN ROS2:
==============

1. Import and Initialize:
   from dicemaster_central.hw.motion_detector import MotionDetector
   
   motion_detector = MotionDetector(history_size=50)

2. Update with IMU data:
   # accel: [x, y, z] in m/s²
   # gyro: [x, y, z] in rad/s  
   # quaternion: [w, x, y, z]
   motion_detector.update(accel, gyro, quaternion)

3. Get motion detection results:
   # Individual detections
   is_rolling_pos = motion_detector.detect_rotation_x_pos()
   is_shaking = motion_detector.detect_shaking()
   
   # Get all motion data at once
   motion_summary = motion_detector.get_motion_summary()
   
   # Intensity values (0.0 to 1.0)
   rotation_intensity = motion_detector.get_rotation_intensity()
   shake_intensity = motion_detector.get_shake_intensity()
   stillness_factor = motion_detector.get_stillness_factor()

4. Example ROS2 Integration:
   class IMUNode(Node):
       def __init__(self):
           super().__init__('imu_node')
           self.motion_detector = MotionDetector()
           
       def imu_callback(self, msg):
           accel = [msg.linear_acceleration.x, 
                   msg.linear_acceleration.y, 
                   msg.linear_acceleration.z]
           gyro = [msg.angular_velocity.x,
                  msg.angular_velocity.y, 
                  msg.angular_velocity.z]
           quat = [msg.orientation.w, msg.orientation.x,
                  msg.orientation.y, msg.orientation.z]
                  
           self.motion_detector.update(accel, gyro, quat)
           motion_data = self.motion_detector.get_motion_summary()
           
           # Publish motion detection results
           motion_msg = MotionDetection()
           motion_msg.rotation_x_pos = motion_data['rotation_x_pos']
           motion_msg.shaking = motion_data['shaking']
           # ... set other fields
           self.motion_pub.publish(motion_msg)

MOTION TYPES DETECTED:
=====================
- Axis rotations: +/- 90° around X, Y, Z axes
- Shaking: High-frequency oscillations
- Rotation intensity: Overall rotation magnitude
- Shake intensity: Overall shake magnitude  
- Stillness factor: How still the device is (1.0 = perfectly still)
"""

import numpy as np
from collections import deque


class MotionDetector:
    """Detects various motion patterns from IMU data"""
    
    def __init__(self, history_size=50):
        self.history_size = history_size
        self.accel_history = deque(maxlen=history_size)
        self.gyro_history = deque(maxlen=history_size)
        self.quat_history = deque(maxlen=history_size)
        
        # Detection thresholds
        self.rotation_threshold = 1.5  # rad/s
        self.shake_threshold = 15.0    # m/s²
        self.shake_frequency_min = 2.0  # Hz
        self.shake_frequency_max = 8.0  # Hz
        self.stillness_threshold = 0.5  # Combined motion threshold for stillness
        
    def update(self, accel, gyro, quaternion):
        """Update motion detector with new data"""
        self.accel_history.append(accel.copy())
        self.gyro_history.append(gyro.copy())
        self.quat_history.append(quaternion.copy())
        
    def detect_rotation_x_pos(self):
        """Detect +90 degree rotation around world X-axis (roll)"""
        return self._detect_axis_rotation(0, 1)
        
    def detect_rotation_x_neg(self):
        """Detect -90 degree rotation around world X-axis (roll)"""
        return self._detect_axis_rotation(0, -1)
        
    def detect_rotation_y_pos(self):
        """Detect +90 degree rotation around world Y-axis (pitch)"""
        return self._detect_axis_rotation(1, 1)
        
    def detect_rotation_y_neg(self):
        """Detect -90 degree rotation around world Y-axis (pitch)"""
        return self._detect_axis_rotation(1, -1)
        
    def detect_rotation_z_pos(self):
        """Detect +90 degree rotation around world Z-axis (yaw)"""
        return self._detect_axis_rotation(2, 1)
        
    def detect_rotation_z_neg(self):
        """Detect -90 degree rotation around world Z-axis (yaw)"""
        return self._detect_axis_rotation(2, -1)
        
    def _detect_axis_rotation(self, axis, direction):
        """Detect rotation around specific axis in specific direction"""
        if len(self.gyro_history) < 10:
            return False
            
        # Get recent angular velocity data
        recent_gyro = list(self.gyro_history)[-10:]
        
        # Check if there's sustained rotation around the specified axis
        axis_velocities = [gyro[axis] for gyro in recent_gyro]
        avg_velocity = np.mean(axis_velocities)
        
        # Check if rotation is in the correct direction and above threshold
        if direction > 0:
            return avg_velocity > self.rotation_threshold
        else:
            return avg_velocity < -self.rotation_threshold
            
    def detect_shaking(self):
        """Detect shaking motion"""
        if len(self.accel_history) < 20:
            return False
            
        # Get recent acceleration data
        recent_accel = np.array(list(self.accel_history)[-20:])
        
        # Calculate acceleration magnitude
        accel_magnitude = np.linalg.norm(recent_accel, axis=1)
        
        # Remove gravity component (approximate)
        accel_magnitude -= 9.81
        
        # Check for high-frequency, high-amplitude variations
        accel_std = np.std(accel_magnitude)
        accel_peak = np.max(np.abs(accel_magnitude))
        
        # Simple shake detection based on variation
        return accel_std > 3.0 and accel_peak > self.shake_threshold
        
    def get_rotation_intensity(self):
        """Calculate overall rotation intensity (0.0 to 1.0)"""
        if len(self.gyro_history) < 5:
            return 0.0
            
        recent_gyro = np.array(list(self.gyro_history)[-5:])
        gyro_magnitude = np.linalg.norm(recent_gyro, axis=1)
        avg_magnitude = np.mean(gyro_magnitude)
        
        # Normalize to 0-1 range (assume max meaningful rotation is 5 rad/s)
        return min(avg_magnitude / 5.0, 1.0)
        
    def get_shake_intensity(self):
        """Calculate shake intensity (0.0 to 1.0)"""
        if len(self.accel_history) < 10:
            return 0.0
            
        recent_accel = np.array(list(self.accel_history)[-10:])
        accel_magnitude = np.linalg.norm(recent_accel, axis=1)
        accel_std = np.std(accel_magnitude)
        
        # Normalize to 0-1 range (assume max meaningful shake std is 10)
        return min(accel_std / 10.0, 1.0)
        
    def get_stillness_factor(self):
        """Calculate stillness factor (1.0 = perfectly still, 0.0 = very active)"""
        rotation_intensity = self.get_rotation_intensity()
        shake_intensity = self.get_shake_intensity()
        
        # Combine both intensities
        combined_motion = (rotation_intensity + shake_intensity) / 2.0
        
        # Return inverse (1.0 - motion)
        return max(0.0, 1.0 - combined_motion)
        
    def get_motion_summary(self):
        """Get summary of all detected motions"""
        return {
            'rotation_x_pos': self.detect_rotation_x_pos(),
            'rotation_x_neg': self.detect_rotation_x_neg(),
            'rotation_y_pos': self.detect_rotation_y_pos(),
            'rotation_y_neg': self.detect_rotation_y_neg(),
            'rotation_z_pos': self.detect_rotation_z_pos(),
            'rotation_z_neg': self.detect_rotation_z_neg(),
            'shaking': self.detect_shaking(),
            'rotation_intensity': self.get_rotation_intensity(),
            'shake_intensity': self.get_shake_intensity(),
            'stillness_factor': self.get_stillness_factor()
        }
