from math import sin, cos, sqrt, atan2, asin, pi
import numpy as np


class QuaternionKalmanFilter:
    """Advanced Kalman filter for quaternion-based pose estimation"""
    
    def __init__(self, process_noise=0.001, measurement_noise=1.0):
        # State: [q0, q1, q2, q3] (quaternion w, x, y, z)
        self.state = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float64)
        self.P = np.eye(4, dtype=np.float64) * 0.1  # Covariance matrix
        self.Q = np.eye(4, dtype=np.float64) * process_noise  # Process noise
        self.R = np.eye(4, dtype=np.float64) * measurement_noise  # Measurement noise
        self.I = np.eye(4, dtype=np.float64)  # Identity matrix
        
        # Angular velocity for state prediction
        self.omega = np.zeros(3, dtype=np.float64)
        
    def predict(self, dt, gyro):
        """Predict step using gyroscope data"""
        if dt <= 0:
            return
            
        # Update angular velocity
        self.omega = gyro
        
        # State transition matrix A based on angular velocity
        A = self._get_state_transition_matrix(dt)
        
        # Predict state
        self.state = A @ self.state
        
        # Normalize quaternion
        q_norm = np.linalg.norm(self.state)
        if q_norm > 0:
            self.state = self.state / q_norm
        
        # Predict covariance
        self.P = A @ self.P @ A.T + self.Q
        
    def update(self, accel_measurement):
        """Update step using accelerometer data"""
        # Convert accelerometer to quaternion measurement
        z = self._accel_to_quaternion(accel_measurement)
        
        # Measurement matrix H (identity since we're directly measuring quaternion)
        H = self.I
        
        # Innovation
        y = z - H @ self.state
        
        # Innovation covariance
        S = H @ self.P @ H.T + self.R
        
        # Kalman gain
        try:
            K = self.P @ H.T @ np.linalg.inv(S)
        except np.linalg.LinAlgError:
            K = self.P @ H.T @ np.linalg.pinv(S)
        
        # Update state
        self.state = self.state + K @ y
        
        # Normalize quaternion
        q_norm = np.linalg.norm(self.state)
        if q_norm > 0:
            self.state = self.state / q_norm
        
        # Update covariance
        self.P = (self.I - K @ H) @ self.P
        
    def _get_state_transition_matrix(self, dt):
        """Get state transition matrix for quaternion integration"""
        wx, wy, wz = self.omega
        
        # Quaternion integration matrix
        omega_matrix = np.array([
            [0.0, -wx, -wy, -wz],
            [wx,  0.0,  wz, -wy],
            [wy, -wz,  0.0,  wx],
            [wz,  wy, -wx,  0.0]
        ], dtype=np.float64)
        
        return self.I + 0.5 * dt * omega_matrix
        
    def _accel_to_quaternion(self, accel):
        """Convert accelerometer measurement to quaternion"""
        # Normalize accelerometer
        acc_norm = np.linalg.norm(accel)
        if acc_norm == 0:
            return np.array([1.0, 0.0, 0.0, 0.0])
        
        accel_normalized = accel / acc_norm
        
        # Calculate roll and pitch from accelerometer
        roll = atan2(accel_normalized[1], accel_normalized[2])
        pitch = atan2(-accel_normalized[0], 
                     sqrt(accel_normalized[1]**2 + accel_normalized[2]**2))
        yaw = 0.0  # Cannot determine yaw from accelerometer alone
        
        # Convert to quaternion
        return self._euler_to_quaternion(roll, pitch, yaw)
        
    def _euler_to_quaternion(self, roll, pitch, yaw):
        """Convert Euler angles to quaternion"""
        cr = cos(roll / 2.0)
        sr = sin(roll / 2.0)
        cp = cos(pitch / 2.0)
        sp = sin(pitch / 2.0)
        cy = cos(yaw / 2.0)
        sy = sin(yaw / 2.0)
        
        w = cr * cp * cy + sr * sp * sy
        x = sr * cp * cy - cr * sp * sy
        y = cr * sp * cy + sr * cp * sy
        z = cr * cp * sy - sr * sp * cy
        
        return np.array([w, x, y, z], dtype=np.float64)
        
    def get_quaternion(self):
        """Get current quaternion estimate"""
        return self.state.copy()
        
    def get_euler_angles(self):
        """Convert quaternion to Euler angles"""
        w, x, y, z = self.state
        
        # Roll (x-axis rotation)
        sinr_cosp = 2 * (w * x + y * z)
        cosr_cosp = 1 - 2 * (x * x + y * y)
        roll = atan2(sinr_cosp, cosr_cosp)
        
        # Pitch (y-axis rotation)
        sinp = 2 * (w * y - z * x)
        if abs(sinp) >= 1:
            pitch = pi / 2 if sinp > 0 else -pi / 2
        else:
            pitch = asin(sinp)
        
        # Yaw (z-axis rotation)
        siny_cosp = 2 * (w * z + x * y)
        cosy_cosp = 1 - 2 * (y * y + z * z)
        yaw = atan2(siny_cosp, cosy_cosp)
        
        return roll, pitch, yaw
