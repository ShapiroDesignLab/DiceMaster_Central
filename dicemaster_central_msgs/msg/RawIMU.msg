# Raw IMU sensor data message
# This message contains raw accelerometer and gyroscope readings from the MPU6050 sensor

std_msgs/Header header

# Accelerometer readings in m/s²
float64 accel_x
float64 accel_y
float64 accel_z

# Gyroscope readings in rad/s
float64 gyro_x
float64 gyro_y
float64 gyro_z

# Temperature reading in degrees Celsius (optional)
float64 temperature
