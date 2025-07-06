# IMU pose estimation result
# Contains orientation as quaternion and Euler angles

std_msgs/Header header

# Orientation as quaternion (w, x, y, z)
geometry_msgs/Quaternion orientation

# Orientation as Euler angles in radians
float64 roll
float64 pitch 
float64 yaw

# Corrected linear acceleration (bias removed) in m/s²
geometry_msgs/Vector3 linear_acceleration

# Corrected angular velocity (bias removed) in rad/s
geometry_msgs/Vector3 angular_velocity

# Covariance matrices (row-major order)
float64[9] orientation_covariance     # Orientation covariance
float64[9] acceleration_covariance    # Linear acceleration covariance
float64[9] angular_velocity_covariance # Angular velocity covariance
