# DiceMaster Custom IMU Messages

This directory contains custom ROS2 message definitions for the DiceMaster IMU system.

## Message Types

### RawIMU.msg
Raw sensor readings from the MPU6050 IMU sensor.

**Fields:**
- `header`: Standard ROS header with timestamp and frame ID
- `accel_x/y/z`: Linear acceleration in m/s² along X, Y, Z axes
- `gyro_x/y/z`: Angular velocity in rad/s around X, Y, Z axes  
- `temperature`: Temperature reading in degrees Celsius

**Usage:**
```python
from dicemaster_central.msg import RawIMU

# Publishing raw IMU data
raw_msg = RawIMU()
raw_msg.header.stamp = node.get_clock().now().to_msg()
raw_msg.accel_x = 0.0
raw_msg.accel_y = 0.0
raw_msg.accel_z = -9.81
# ... set other fields
publisher.publish(raw_msg)
```

### IMUPose.msg
Complete pose estimation result with orientation, Euler angles, and corrected sensor data.

**Fields:**
- `header`: Standard ROS header
- `orientation`: Orientation as quaternion (geometry_msgs/Quaternion)
- `roll/pitch/yaw`: Euler angles in radians
- `linear_acceleration`: Bias-corrected acceleration (geometry_msgs/Vector3)
- `angular_velocity`: Bias-corrected angular velocity (geometry_msgs/Vector3)
- `orientation_covariance[9]`: 3x3 orientation covariance matrix (row-major)
- `acceleration_covariance[9]`: 3x3 acceleration covariance matrix
- `angular_velocity_covariance[9]`: 3x3 angular velocity covariance matrix

**Usage:**
```python
from dicemaster_central.msg import IMUPose

def pose_callback(msg):
    # Get Euler angles
    roll, pitch, yaw = msg.roll, msg.pitch, msg.yaw
    
    # Get quaternion
    quat = msg.orientation
    
    # Get corrected sensor data
    accel = msg.linear_acceleration
    gyro = msg.angular_velocity
```

### MotionDetection.msg
Comprehensive motion detection results with boolean flags and intensity metrics.

**Fields:**
- `header`: Standard ROS header
- `rotation_x_positive/negative`: ±90° rotation around X-axis detected
- `rotation_y_positive/negative`: ±90° rotation around Y-axis detected  
- `rotation_z_positive/negative`: ±90° rotation around Z-axis detected
- `shaking`: Rapid shaking motion detected
- `rotation_intensity`: Overall rotation intensity (0.0-1.0)
- `shake_intensity`: Shake motion intensity (0.0-1.0)
- `stillness_factor`: Device stillness factor (1.0 = perfectly still)

**Usage:**
```python
from dicemaster_central.msg import MotionDetection

def motion_callback(msg):
    if msg.shaking:
        print("Device is being shaken!")
        
    if msg.rotation_x_positive:
        print("90° rotation around X-axis detected!")
        
    # Check motion intensity
    if msg.stillness_factor > 0.9:
        print("Device is very still")
    elif msg.rotation_intensity > 0.7:
        print("High rotation activity")
```

### IMUCalibration.msg
Calibration status and quality metrics.

**Fields:**
- `header`: Standard ROS header
- `status`: Calibration status string ("STARTING", "CALIBRATING", "READY", "CALIBRATION_FAILED")
- `progress`: Calibration progress (0.0-1.0)
- `calibration_duration`: Total calibration time in seconds
- `accelerometer_bias`: Computed accelerometer bias (geometry_msgs/Vector3)
- `gyroscope_bias`: Computed gyroscope bias (geometry_msgs/Vector3)
- `accelerometer_std`: Standard deviation of accelerometer readings during calibration
- `gyroscope_std`: Standard deviation of gyroscope readings during calibration
- `sample_count`: Number of samples used for calibration

**Usage:**
```python
from dicemaster_central.msg import IMUCalibration

def calibration_callback(msg):
    if msg.status == "CALIBRATING":
        print(f"Calibration progress: {msg.progress*100:.1f}%")
    elif msg.status == "READY":
        print("Calibration complete!")
        print(f"Accelerometer bias: {msg.accelerometer_bias}")
        print(f"Calibration quality (std): {msg.accelerometer_std:.3f}")
```

### NotificationRequest.msg
Notification request message for the DiceMaster notification system.

**Fields:**
- `screen_id`: Target screen ID (int32)
- `level`: Notification level - "info" or "error" (string)
- `content`: Notification text content (string)
- `duration`: Display duration in seconds (float64)

**Usage:**
```python
from dicemaster_central.msg import NotificationRequest

# Publishing a notification
notif_msg = NotificationRequest()
notif_msg.screen_id = 0
notif_msg.level = 'info'
notif_msg.content = 'System startup complete'
notif_msg.duration = 3.0
publisher.publish(notif_msg)
```

**Topic:** `/dice_system/notifications`

The notification system displays messages with appropriate colors:
- INFO: Black text on white background
- ERROR: Red text on white background

## Topic Structure

The IMU system publishes to the following topics:

```
/imu/
├── raw              # RawIMU - input topic for raw sensor data
├── pose             # IMUPose - complete pose estimation
├── motion           # MotionDetection - motion detection results
├── calibration      # IMUCalibration - calibration status
├── pose_legacy      # geometry_msgs/Pose - legacy compatibility
├── accel            # geometry_msgs/Vector3 - acceleration only
├── angvel           # geometry_msgs/Vector3 - angular velocity only
├── status           # std_msgs/String - simple status
└── motion/
    ├── rotation_x_pos   # std_msgs/Bool - individual motion flags
    ├── rotation_x_neg   # std_msgs/Bool
    ├── rotation_y_pos   # std_msgs/Bool
    ├── rotation_y_neg   # std_msgs/Bool
    ├── rotation_z_pos   # std_msgs/Bool
    ├── rotation_z_neg   # std_msgs/Bool
    └── shaking          # std_msgs/Bool
```

## Building and Using

1. **Build the package:**
   ```bash
   cd /path/to/workspace
   colcon build --packages-select dicemaster_central
   source install/setup.bash
   ```

2. **Import in Python:**
   ```python
   from dicemaster_central.msg import RawIMU, IMUPose, MotionDetection, IMUCalibration
   ```

3. **Use in other packages:**
   Add to your package.xml:
   ```xml
   <depend>dicemaster_central</depend>
   ```

4. **Launch the system:**
   ```bash
   # Run IMU node
   ros2 run dicemaster_central imu_node
   
   # Run test/example
   ros2 run dicemaster_central test_imu
   ros2 run dicemaster_central imu_example
   ```

## Message Advantages

- **Rich Data**: Custom messages provide more information than standard types
- **Efficiency**: Single message contains multiple related data points
- **Type Safety**: Strong typing prevents data interpretation errors
- **Backward Compatibility**: Legacy topics maintain compatibility with existing code
- **Extensibility**: Easy to add new fields without breaking existing code
- **Documentation**: Self-documenting through message field names and types
