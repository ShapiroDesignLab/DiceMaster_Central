"""
This configures the ROS robot loading with dice.urdf, and subscribes to /dice_hw/imu/pose for the pose of the core of the dice. The remaining frames will need to be inferred from the tf2 transformation automatically for other nodes such as screen orientation detection. 
"""

