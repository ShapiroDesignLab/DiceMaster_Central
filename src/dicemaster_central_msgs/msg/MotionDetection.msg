# Motion detection results
# Contains boolean flags for various detected motions

std_msgs/Header header

# Rotation detections around world axes (90-degree rotations)
bool rotation_x_positive    # +90° rotation around world X-axis (roll)
bool rotation_x_negative    # -90° rotation around world X-axis (roll)
bool rotation_y_positive    # +90° rotation around world Y-axis (pitch)
bool rotation_y_negative    # -90° rotation around world Y-axis (pitch)
bool rotation_z_positive    # +90° rotation around world Z-axis (yaw)
bool rotation_z_negative    # -90° rotation around world Z-axis (yaw)

# Shake detection
bool shaking                # Rapid shaking motion detected

# Motion intensity metrics (0.0 to 1.0)
float64 rotation_intensity  # Overall rotation intensity
float64 shake_intensity     # Shake motion intensity
float64 stillness_factor    # How still the device is (1.0 = perfectly still)
