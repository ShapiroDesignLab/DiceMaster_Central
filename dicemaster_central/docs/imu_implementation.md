# DiceMaster IMU Implementation

## Overview

This is an advanced IMU implementation for the DiceMaster project using a quaternion-based Kalman filter for pose estimation. The implementation is based on the MPU6050-with-Kalman-Filter algorithm but translated to Python and enhanced with motion detection capabilities. It includes custom ROS2 message types for enhanced functionality and backward compatibility.

## Features

### Core Functionality
- **Quaternion-based Kalman Filter**: Advanced pose estimation using quaternions to avoid gimbal lock
- **Automatic Calibration**: Self-calibrating accelerometer and gyroscope bias compensation
- **ROS2 Integration**: Full ROS2 node with custom and standard message types
- **High Performance**: Optimized for real-time operation
- **Dual Input Support**: Accepts both custom RawIMU messages and standard sensor_msgs/Imu

### Custom Message Types

#### RawIMU.msg
Raw sensor data from MPU6050:
```
std_msgs/Header header
float64 accel_x
float64 accel_y  
float64 accel_z
float64 gyro_x
float64 gyro_y
float64 gyro_z
float64 temperature
```

#### IMUPose.msg
Complete pose estimation with orientation, Euler angles, and corrected sensor data:
```
std_msgs/Header header
geometry_msgs/Quaternion orientation
float64 roll
float64 pitch
float64 yaw
geometry_msgs/Vector3 linear_acceleration
geometry_msgs/Vector3 angular_velocity
float64[9] orientation_covariance
float64[9] acceleration_covariance
float64[9] angular_velocity_covariance
```

#### MotionDetection.msg
Comprehensive motion detection results:
```
std_msgs/Header header
bool rotation_x_positive
bool rotation_x_negative
bool rotation_y_positive
bool rotation_y_negative
bool rotation_z_positive
bool rotation_z_negative
bool shaking
float64 rotation_intensity
float64 shake_intensity
float64 stillness_factor
```

#### IMUCalibration.msg
Calibration status and quality metrics:
```
std_msgs/Header header
string status
float64 progress
float64 calibration_duration
geometry_msgs/Vector3 accelerometer_bias
geometry_msgs/Vector3 gyroscope_bias
float64 accelerometer_std
float64 gyroscope_std
int32 sample_count
```

### Motion Detection
The implementation includes sophisticated motion detectors:

1. **Rotation Detectors**: Detect 90-degree rotations around world axes
   - `rotation_x_positive`: +90° rotation around world X-axis (roll)
   - `rotation_x_negative`: -90° rotation around world X-axis (roll)
   - `rotation_y_positive`: +90° rotation around world Y-axis (pitch)
   - `rotation_y_negative`: -90° rotation around world Y-axis (pitch)
   - `rotation_z_positive`: +90° rotation around world Z-axis (yaw)
   - `rotation_z_negative`: -90° rotation around world Z-axis (yaw)

2. **Shaking Detector**: Detects rapid, high-amplitude motion patterns

3. **Motion Intensity Metrics**:
   - `rotation_intensity`: Overall rotation intensity (0.0-1.0)
   - `shake_intensity`: Shake motion intensity (0.0-1.0)
   - `stillness_factor`: Device stillness (1.0 = perfectly still)

## Topics

### Published Topics

#### Core IMU Data (Custom Messages)
- `/imu/pose` (dicemaster_central/IMUPose): Complete pose estimation with orientation, Euler angles, and sensor data
- `/imu/motion` (dicemaster_central/MotionDetection): Comprehensive motion detection results
- `/imu/calibration` (dicemaster_central/IMUCalibration): Calibration status and quality metrics

#### Legacy/Compatibility Topics
- `/imu/pose_legacy` (geometry_msgs/Pose): Simple orientation as quaternion
- `/imu/accel` (geometry_msgs/Vector3): Corrected linear acceleration
- `/imu/angvel` (geometry_msgs/Vector3): Corrected angular velocity
- `/imu/status` (std_msgs/String): Node status (STARTING, CALIBRATING, READY, etc.)

#### Individual Motion Detection (Backward Compatibility)
- `/imu/motion/rotation_x_pos` (std_msgs/Bool): +90° X-axis rotation detected
- `/imu/motion/rotation_x_neg` (std_msgs/Bool): -90° X-axis rotation detected
- `/imu/motion/rotation_y_pos` (std_msgs/Bool): +90° Y-axis rotation detected
- `/imu/motion/rotation_y_neg` (std_msgs/Bool): -90° Y-axis rotation detected
- `/imu/motion/rotation_z_pos` (std_msgs/Bool): +90° Z-axis rotation detected
- `/imu/motion/rotation_z_neg` (std_msgs/Bool): -90° Z-axis rotation detected
- `/imu/motion/shaking` (std_msgs/Bool): Shaking motion detected

### Subscribed Topics
- `/imu/raw` (dicemaster_central/RawIMU): Primary input for raw IMU data with temperature
- `/sensor` (sensor_msgs/Imu): Fallback input for standard IMU data

## Parameters

- `calibration_duration` (double, default: 3.0): Duration of calibration phase in seconds
- `raw_imu_topic` (string, default: '/imu/raw'): Topic name for custom RawIMU input data
- `process_noise` (double, default: 0.001): Kalman filter process noise
- `measurement_noise` (double, default: 1.0): Kalman filter measurement noise
- `publishing_rate` (double, default: 30.0): Rate for publishing output data in Hz

## Algorithm Details

### Kalman Filter Implementation

The quaternion-based Kalman filter uses a 4-state vector representing the orientation quaternion [w, x, y, z]. The filter:

1. **Prediction Step**: Uses gyroscope data to predict quaternion changes via integration
2. **Update Step**: Uses accelerometer data converted to quaternion measurements for correction
3. **Normalization**: Ensures quaternion remains unit length

### Motion Detection Algorithm

#### Rotation Detection
- Monitors sustained angular velocity around specific axes
- Threshold-based detection (default: 1.5 rad/s)
- Distinguishes between positive and negative rotations

#### Shake Detection
- Analyzes high-frequency acceleration variations
- Removes gravity component for pure motion detection
- Uses statistical measures (standard deviation and peak detection)

#### Intensity Metrics
- **Rotation Intensity**: Normalized angular velocity magnitude (0.0-1.0)
- **Shake Intensity**: Normalized acceleration variation (0.0-1.0)
- **Stillness Factor**: Inverse of combined motion intensity (1.0 = perfectly still)

## Usage

### Basic Usage

```bash
# Launch the IMU node
ros2 run dicemaster_central imu_node

# Or with custom parameters
ros2 run dicemaster_central imu_node --ros-args \
    -p calibration_duration:=5.0 \
    -p process_noise:=0.002 \
    -p measurement_noise:=0.5
```

### Using Launch File

```bash
# Launch with default parameters
ros2 launch dicemaster_central launch_imu.py

# Launch with custom parameters
ros2 launch dicemaster_central launch_imu.py \
    calibration_duration:=5.0 \
    process_noise:=0.002
```

### Testing

```bash
# Run the test node to generate simulated IMU data
ros2 run dicemaster_central test_imu

# In another terminal, run the IMU node
ros2 run dicemaster_central imu_node

# Monitor comprehensive motion detection
ros2 topic echo /imu/motion

# Monitor calibration status
ros2 topic echo /imu/calibration

# Monitor complete pose data
ros2 topic echo /imu/pose
```

### Monitoring

```bash
# Monitor primary pose output (custom message)
ros2 topic echo /imu/pose

# Monitor motion detection (custom message)
ros2 topic echo /imu/motion

# Monitor calibration progress
ros2 topic echo /imu/calibration

# Monitor legacy outputs
ros2 topic echo /imu/pose_legacy
ros2 topic echo /imu/accel
ros2 topic echo /imu/angvel

# List all motion detection topics
ros2 topic list | grep /imu/motion
```

## Message Integration

### Using Custom Messages in Python

```python
from dicemaster_central_msgs.msg import RawIMU, IMUPose, MotionDetection, IMUCalibration

# Subscribe to comprehensive motion detection
def motion_callback(msg):
    if msg.shaking:
        print("Device is being shaken!")
    if msg.rotation_x_positive:
        print("90° rotation around X-axis detected!")
    print(f"Rotation intensity: {msg.rotation_intensity:.2f}")
    print(f"Stillness factor: {msg.stillness_factor:.2f}")

# Subscribe to complete pose data
def pose_callback(msg):
    print(f"Roll: {msg.roll:.2f}, Pitch: {msg.pitch:.2f}, Yaw: {msg.yaw:.2f}")
    print(f"Acceleration: {msg.linear_acceleration}")
```

### Publishing Raw IMU Data

```python
from dicemaster_central_msgs.msg import RawIMU

# Create and publish raw IMU data
raw_msg = RawIMU()
raw_msg.header.stamp = node.get_clock().now().to_msg()
raw_msg.header.frame_id = 'imu_link'
raw_msg.accel_x = 0.0
raw_msg.accel_y = 0.0  
raw_msg.accel_z = -9.81
raw_msg.gyro_x = 0.0
raw_msg.gyro_y = 0.0
raw_msg.gyro_z = 0.0
raw_msg.temperature = 25.0

publisher.publish(raw_msg)
```

## Calibration Process

1. **Initialization**: Node starts in "STARTING" state
2. **Calibration**: Automatically transitions to "CALIBRATING" state
   - Collects sensor data for the specified duration
   - Computes accelerometer and gyroscope biases
   - Assumes device is stationary with Z-axis pointing up
   - Reports progress and quality metrics
3. **Ready**: Transitions to "READY" state and begins normal operation

## Performance Considerations

- **Memory Usage**: Maintains history buffers for motion detection
- **CPU Usage**: Optimized matrix operations using NumPy
- **Publishing Rate**: Configurable to balance performance and responsiveness
- **Real-time**: Designed for real-time operation with minimal latency
- **Message Efficiency**: Custom messages reduce bandwidth and provide richer data

## Dependencies

- ROS2 (Humble or later)
- NumPy
- SciPy (for spatial transformations)
- Python 3.8+
- rosidl_default_generators (for custom messages)

## Building

```bash
# Build the package with custom messages
cd /path/to/workspace
colcon build --packages-select dicemaster_central

# Source the workspace
source install/setup.bash
```

## Troubleshooting

### Common Issues

1. **"CALIBRATION_FAILED"**: Ensure sensor is connected and publishing data
2. **Drift in orientation**: Adjust process_noise and measurement_noise parameters
3. **False motion detection**: Adjust motion detection thresholds in the code
4. **High CPU usage**: Reduce publishing_rate parameter
5. **Custom message not found**: Ensure package is built and sourced properly

### Debug Topics

Monitor the calibration topic for detailed node state:
```bash
ros2 topic echo /imu/calibration
```

Check if raw sensor data is being received:
```bash
ros2 topic echo /imu/raw
# or for fallback
ros2 topic echo /sensor
```

Monitor motion intensity metrics:
```bash
ros2 topic echo /imu/motion --field stillness_factor
ros2 topic echo /imu/motion --field rotation_intensity
```

## Future Enhancements

- Magnetometer integration for absolute yaw reference
- Advanced motion pattern recognition
- Adaptive noise estimation
- Machine learning-based motion classification
- Integration with dice face detection algorithms
- Frequency domain analysis for shake detection
- Orientation-aware motion detection (world vs. body frame)
