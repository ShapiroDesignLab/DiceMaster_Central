# IMU calibration status and parameters
# Contains calibration state and computed bias values

std_msgs/Header header

# Calibration status
string status               # STARTING, CALIBRATING, READY, CALIBRATION_FAILED
float64 progress            # Calibration progress (0.0 to 1.0)
float64 calibration_duration # Total calibration time in seconds

# Computed bias values
geometry_msgs/Vector3 accelerometer_bias  # Accelerometer bias in m/s²
geometry_msgs/Vector3 gyroscope_bias      # Gyroscope bias in rad/s

# Calibration quality metrics
float64 accelerometer_std   # Standard deviation of accelerometer readings during calibration
float64 gyroscope_std       # Standard deviation of gyroscope readings during calibration
int32 sample_count          # Number of samples used for calibration
