"""
IMU Hardware Module for DiceMaster
"""

from .imu_hardware import IMUHardwareNode
from .motion_detector import MotionDetectorNode

# Make node class and main available at module level
__all__ = ['IMUHardwareNode', 'MotionDetectorNode']
