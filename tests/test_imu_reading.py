#!/usr/bin/env python3
"""
Test script to read raw and filtered IMU data from MPU6050 on I2C bus 6 (GPIO 15/16)
and plot the results. This script tests both IMUHardware and FilteredIMUHardware classes.
"""

import sys
import os
import time
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime

# Add DiceMaster_Central to path
sys.path.insert(0, '/home/dice/DiceMaster/DiceMaster_Central')

from DiceMaster_Central.hw.imu import IMUHardware, FilteredIMUHardware

def test_imu_reading(duration=30, sample_rate=50, use_filtered=False, compare_both=False):
    """
    Test IMU reading for specified duration and sample rate
    
    Args:
        duration: Duration in seconds to collect data
        sample_rate: Samples per second
        use_filtered: Use FilteredIMUHardware instead of raw IMUHardware
        compare_both: Test both raw and filtered side by side
    """
    print(f"Starting IMU test on I2C bus 6 (GPIO 15/16 - SDA6/SCL6)")
    print(f"Duration: {duration} seconds")
    print(f"Sample rate: {sample_rate} Hz")
    
    if compare_both:
        print("Mode: Comparing raw vs filtered IMU data")
    elif use_filtered:
        print("Mode: Using filtered IMU with calibration")
    else:
        print("Mode: Using raw IMU data")
    
    print("Make sure the IMU is stationary for consistent readings!")
    
    # Initialize IMU(s)
    if compare_both:
        imu_raw = IMUHardware(i2c_bus=6, i2c_address=0x68)
        imu_filtered = FilteredIMUHardware(i2c_bus=6, i2c_address=0x68)
        
        # Calibrate filtered IMU
        print("\nStarting calibration for filtered IMU...")
        imu_filtered.start_calibration(duration=3.0)
        
        # Wait for calibration to complete
        print("Calibration in progress...")
        while imu_filtered.get_calibration_status()['calibration_requested']:
            # Need to poll IMU data to trigger calibration process
            imu_filtered.get_imu_data()
            time.sleep(0.01)
        
        if not imu_filtered.get_calibration_status()['is_calibrated']:
            print("Calibration failed! Continuing with raw comparison only...")
            imu_filtered = None
        
    elif use_filtered:
        imu_filtered = FilteredIMUHardware(i2c_bus=6, i2c_address=0x68)
        
        # Calibrate filtered IMU
        print("\nStarting calibration...")
        imu_filtered.start_calibration(duration=3.0)
        
        # Wait for calibration to complete
        print("Calibration in progress...")
        while imu_filtered.get_calibration_status()['calibration_requested']:
            # Need to poll IMU data to trigger calibration process
            imu_filtered.get_imu_data()
            time.sleep(0.1)
        
        if not imu_filtered.get_calibration_status()['is_calibrated']:
            print("Calibration failed! Exiting...")
            return None
            
        imu_raw = None
    else:
        imu_raw = IMUHardware(i2c_bus=6, i2c_address=0x68)
        imu_filtered = None
    
    # Data storage
    timestamps = []
    
    # Raw data
    raw_data = {'accel': {'x': [], 'y': [], 'z': []}, 'gyro': {'x': [], 'y': [], 'z': []}}
    
    # Filtered data
    filtered_data = {'accel': {'x': [], 'y': [], 'z': []}, 'gyro': {'x': [], 'y': [], 'z': []}}
    
    # Additional filtered data
    quaternions = []
    euler_angles = []
    
    sample_interval = 1.0 / sample_rate
    start_time = time.time()
    next_sample_time = start_time
    
    print(f"\nStarting data collection at {datetime.now().strftime('%H:%M:%S')}")
    print("Press Ctrl+C to stop early...")
    
    try:
        while time.time() - start_time < duration:
            current_time = time.time()
            
            # Wait for next sample time
            if current_time >= next_sample_time:
                timestamps.append(current_time - start_time)
                
                # Read raw data
                if imu_raw is not None or compare_both:
                    imu_to_use = imu_raw if imu_raw is not None else imu_filtered
                    raw_imu_data = imu_to_use.get_imu_data()
                    
                    if raw_imu_data is not None:
                        raw_data['accel']['x'].append(raw_imu_data[0])
                        raw_data['accel']['y'].append(raw_imu_data[1])
                        raw_data['accel']['z'].append(raw_imu_data[2])
                        raw_data['gyro']['x'].append(raw_imu_data[3])
                        raw_data['gyro']['y'].append(raw_imu_data[4])
                        raw_data['gyro']['z'].append(raw_imu_data[5])
                    else:
                        # Handle None case (shouldn't happen for raw)
                        raw_data['accel']['x'].append(0)
                        raw_data['accel']['y'].append(0)
                        raw_data['accel']['z'].append(-9.81)
                        raw_data['gyro']['x'].append(0)
                        raw_data['gyro']['y'].append(0)
                        raw_data['gyro']['z'].append(0)
                
                # Read filtered data
                if imu_filtered is not None:
                    filtered_imu_data = imu_filtered.get_imu_data()
                    
                    if filtered_imu_data is not None:
                        filtered_data['accel']['x'].append(filtered_imu_data[0])
                        filtered_data['accel']['y'].append(filtered_imu_data[1])
                        filtered_data['accel']['z'].append(filtered_imu_data[2])
                        filtered_data['gyro']['x'].append(filtered_imu_data[3])
                        filtered_data['gyro']['y'].append(filtered_imu_data[4])
                        filtered_data['gyro']['z'].append(filtered_imu_data[5])
                        
                        # Get quaternion and Euler angles
                        quat = imu_filtered.get_quaternion()
                        euler = imu_filtered.get_euler_angles()
                        quaternions.append(quat)
                        euler_angles.append(euler)
                    else:
                        # Handle calibration phase
                        filtered_data['accel']['x'].append(0)
                        filtered_data['accel']['y'].append(0)
                        filtered_data['accel']['z'].append(-9.81)
                        filtered_data['gyro']['x'].append(0)
                        filtered_data['gyro']['y'].append(0)
                        filtered_data['gyro']['z'].append(0)
                        quaternions.append([1, 0, 0, 0])
                        euler_angles.append([0, 0, 0])
                
                # Progress update
                if len(timestamps) % max(1, int(sample_rate * 5)) == 0:  # Every 5 seconds
                    elapsed = time.time() - start_time
                    remaining = duration - elapsed
                    print(f"Progress: {elapsed:.1f}s / {duration}s (remaining: {remaining:.1f}s) - Samples: {len(timestamps)}")
                    
                    if imu_raw is not None:
                        print(f"  Raw accel: X={raw_data['accel']['x'][-1]:.2f}, Y={raw_data['accel']['y'][-1]:.2f}, Z={raw_data['accel']['z'][-1]:.2f} m/s²")
                        print(f"  Raw gyro:  X={raw_data['gyro']['x'][-1]:.3f}, Y={raw_data['gyro']['y'][-1]:.3f}, Z={raw_data['gyro']['z'][-1]:.3f} rad/s")
                    
                    if imu_filtered is not None and filtered_imu_data is not None:
                        print(f"  Filtered accel: X={filtered_data['accel']['x'][-1]:.2f}, Y={filtered_data['accel']['y'][-1]:.2f}, Z={filtered_data['accel']['z'][-1]:.2f} m/s²")
                        print(f"  Filtered gyro:  X={filtered_data['gyro']['x'][-1]:.3f}, Y={filtered_data['gyro']['y'][-1]:.3f}, Z={filtered_data['gyro']['z'][-1]:.3f} rad/s")
                        roll, pitch, yaw = euler_angles[-1]
                        print(f"  Euler angles: Roll={roll:.3f}, Pitch={pitch:.3f}, Yaw={yaw:.3f} rad")
                
                # Update next sample time
                next_sample_time += sample_interval
            else:
                # Sleep for a fraction of the sample interval to avoid busy waiting
                sleep_time = min(sample_interval / 10, 0.001)  # Sleep for 10% of interval or 1ms, whichever is smaller
                time.sleep(sleep_time)
            
    except KeyboardInterrupt:
        print("\nData collection stopped by user")
    
    finally:
        if imu_raw is not None:
            imu_raw.close()
        if imu_filtered is not None:
            imu_filtered.close()
    
    # Convert to numpy arrays
    timestamps = np.array(timestamps)
    
    print(f"\nData collection complete!")
    print(f"Collected {len(timestamps)} samples over {timestamps[-1]:.1f} seconds")
    print(f"Actual sample rate: {len(timestamps) / timestamps[-1]:.1f} Hz")
    
    # Create the plot
    return create_comparison_plot(timestamps, raw_data, filtered_data, quaternions, euler_angles, 
                                compare_both, use_filtered, sample_rate)


def create_comparison_plot(timestamps, raw_data, filtered_data, quaternions, euler_angles, 
                          compare_both, use_filtered, sample_rate):
    """Create comparison plots for raw vs filtered IMU data"""
    
    plt.style.use('seaborn-v0_8' if 'seaborn-v0_8' in plt.style.available else 'default')
    
    if compare_both:
        # Create comprehensive comparison plot
        fig, axes = plt.subplots(3, 2, figsize=(18, 12))
        fig.suptitle(f'IMU Data Comparison: Raw vs Filtered\nCollected: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}', fontsize=16)
        
        # Convert data to numpy arrays
        raw_accel = np.array([raw_data['accel']['x'], raw_data['accel']['y'], raw_data['accel']['z']]).T
        raw_gyro = np.array([raw_data['gyro']['x'], raw_data['gyro']['y'], raw_data['gyro']['z']]).T
        filtered_accel = np.array([filtered_data['accel']['x'], filtered_data['accel']['y'], filtered_data['accel']['z']]).T
        filtered_gyro = np.array([filtered_data['gyro']['x'], filtered_data['gyro']['y'], filtered_data['gyro']['z']]).T
        euler_array = np.array(euler_angles)
        
        # Accelerometer comparison
        ax1 = axes[0, 0]
        ax1.plot(timestamps, raw_accel[:, 0], 'r-', label='Raw X', alpha=0.7, linewidth=1)
        ax1.plot(timestamps, raw_accel[:, 1], 'g-', label='Raw Y', alpha=0.7, linewidth=1)
        ax1.plot(timestamps, raw_accel[:, 2], 'b-', label='Raw Z', alpha=0.7, linewidth=1)
        ax1.set_xlabel('Time (s)')
        ax1.set_ylabel('Acceleration (m/s²)')
        ax1.set_title('Raw Accelerometer Data')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        ax2 = axes[0, 1]
        ax2.plot(timestamps, filtered_accel[:, 0], 'r-', label='Filtered X', linewidth=1.5)
        ax2.plot(timestamps, filtered_accel[:, 1], 'g-', label='Filtered Y', linewidth=1.5)
        ax2.plot(timestamps, filtered_accel[:, 2], 'b-', label='Filtered Z', linewidth=1.5)
        ax2.set_xlabel('Time (s)')
        ax2.set_ylabel('Acceleration (m/s²)')
        ax2.set_title('Filtered Accelerometer Data')
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        
        # Gyroscope comparison
        ax3 = axes[1, 0]
        ax3.plot(timestamps, raw_gyro[:, 0], 'r-', label='Raw X', alpha=0.7, linewidth=1)
        ax3.plot(timestamps, raw_gyro[:, 1], 'g-', label='Raw Y', alpha=0.7, linewidth=1)
        ax3.plot(timestamps, raw_gyro[:, 2], 'b-', label='Raw Z', alpha=0.7, linewidth=1)
        ax3.set_xlabel('Time (s)')
        ax3.set_ylabel('Angular Velocity (rad/s)')
        ax3.set_title('Raw Gyroscope Data')
        ax3.legend()
        ax3.grid(True, alpha=0.3)
        
        ax4 = axes[1, 1]
        ax4.plot(timestamps, filtered_gyro[:, 0], 'r-', label='Filtered X', linewidth=1.5)
        ax4.plot(timestamps, filtered_gyro[:, 1], 'g-', label='Filtered Y', linewidth=1.5)
        ax4.plot(timestamps, filtered_gyro[:, 2], 'b-', label='Filtered Z', linewidth=1.5)
        ax4.set_xlabel('Time (s)')
        ax4.set_ylabel('Angular Velocity (rad/s)')
        ax4.set_title('Filtered Gyroscope Data')
        ax4.legend()
        ax4.grid(True, alpha=0.3)
        
        # Euler angles
        ax5 = axes[2, 0]
        ax5.plot(timestamps, euler_array[:, 0], 'r-', label='Roll', linewidth=2)
        ax5.plot(timestamps, euler_array[:, 1], 'g-', label='Pitch', linewidth=2)
        ax5.plot(timestamps, euler_array[:, 2], 'b-', label='Yaw', linewidth=2)
        ax5.set_xlabel('Time (s)')
        ax5.set_ylabel('Angle (rad)')
        ax5.set_title('Euler Angles (from Kalman Filter)')
        ax5.legend()
        ax5.grid(True, alpha=0.3)
        
        # Magnitude comparison
        ax6 = axes[2, 1]
        raw_mag = np.sqrt(np.sum(raw_accel**2, axis=1))
        filtered_mag = np.sqrt(np.sum(filtered_accel**2, axis=1))
        ax6.plot(timestamps, raw_mag, 'r-', label='Raw Magnitude', alpha=0.7, linewidth=1)
        ax6.plot(timestamps, filtered_mag, 'b-', label='Filtered Magnitude', linewidth=1.5)
        ax6.axhline(y=9.81, color='black', linestyle='--', alpha=0.7, label='1g (9.81 m/s²)')
        ax6.set_xlabel('Time (s)')
        ax6.set_ylabel('Acceleration Magnitude (m/s²)')
        ax6.set_title('Accelerometer Magnitude Comparison')
        ax6.legend()
        ax6.grid(True, alpha=0.3)
        
        plot_type = "comparison"
        
    elif use_filtered:
        # Filtered data only
        fig, axes = plt.subplots(2, 2, figsize=(15, 10))
        fig.suptitle(f'Filtered IMU Data with Kalman Filter\nCollected: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}', fontsize=14)
        
        # Convert data to numpy arrays
        filtered_accel = np.array([filtered_data['accel']['x'], filtered_data['accel']['y'], filtered_data['accel']['z']]).T
        filtered_gyro = np.array([filtered_data['gyro']['x'], filtered_data['gyro']['y'], filtered_data['gyro']['z']]).T
        euler_array = np.array(euler_angles)
        
        # Accelerometer plot
        ax1 = axes[0, 0]
        ax1.plot(timestamps, filtered_accel[:, 0], 'r-', label='X-axis', linewidth=1.5)
        ax1.plot(timestamps, filtered_accel[:, 1], 'g-', label='Y-axis', linewidth=1.5)
        ax1.plot(timestamps, filtered_accel[:, 2], 'b-', label='Z-axis', linewidth=1.5)
        ax1.set_xlabel('Time (s)')
        ax1.set_ylabel('Acceleration (m/s²)')
        ax1.set_title('Filtered Accelerometer Data')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # Gyroscope plot
        ax2 = axes[0, 1]
        ax2.plot(timestamps, filtered_gyro[:, 0], 'r-', label='X-axis', linewidth=1.5)
        ax2.plot(timestamps, filtered_gyro[:, 1], 'g-', label='Y-axis', linewidth=1.5)
        ax2.plot(timestamps, filtered_gyro[:, 2], 'b-', label='Z-axis', linewidth=1.5)
        ax2.set_xlabel('Time (s)')
        ax2.set_ylabel('Angular Velocity (rad/s)')
        ax2.set_title('Filtered Gyroscope Data')
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        
        # Euler angles
        ax3 = axes[1, 0]
        ax3.plot(timestamps, euler_array[:, 0], 'r-', label='Roll', linewidth=2)
        ax3.plot(timestamps, euler_array[:, 1], 'g-', label='Pitch', linewidth=2)
        ax3.plot(timestamps, euler_array[:, 2], 'b-', label='Yaw', linewidth=2)
        ax3.set_xlabel('Time (s)')
        ax3.set_ylabel('Angle (rad)')
        ax3.set_title('Euler Angles (from Kalman Filter)')
        ax3.legend()
        ax3.grid(True, alpha=0.3)
        
        # Accelerometer magnitude
        ax4 = axes[1, 1]
        accel_magnitude = np.sqrt(np.sum(filtered_accel**2, axis=1))
        ax4.plot(timestamps, accel_magnitude, 'purple', linewidth=2)
        ax4.axhline(y=9.81, color='red', linestyle='--', alpha=0.7, label='1g (9.81 m/s²)')
        ax4.set_xlabel('Time (s)')
        ax4.set_ylabel('Acceleration Magnitude (m/s²)')
        ax4.set_title('Filtered Accelerometer Magnitude')
        ax4.legend()
        ax4.grid(True, alpha=0.3)
        
        plot_type = "filtered"
        
    else:
        # Raw data only (original behavior)
        fig, axes = plt.subplots(2, 2, figsize=(15, 10))
        fig.suptitle(f'Raw IMU Data from I2C Bus 6 (GPIO 15/16)\nCollected: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}', fontsize=14)
        
        # Convert data to numpy arrays
        raw_accel = np.array([raw_data['accel']['x'], raw_data['accel']['y'], raw_data['accel']['z']]).T
        raw_gyro = np.array([raw_data['gyro']['x'], raw_data['gyro']['y'], raw_data['gyro']['z']]).T
        
        # Accelerometer plot
        ax1 = axes[0, 0]
        ax1.plot(timestamps, raw_accel[:, 0], 'r-', label='X-axis', linewidth=1)
        ax1.plot(timestamps, raw_accel[:, 1], 'g-', label='Y-axis', linewidth=1)
        ax1.plot(timestamps, raw_accel[:, 2], 'b-', label='Z-axis', linewidth=1)
        ax1.set_xlabel('Time (s)')
        ax1.set_ylabel('Acceleration (m/s²)')
        ax1.set_title('Raw Accelerometer Data')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # Gyroscope plot
        ax2 = axes[0, 1]
        ax2.plot(timestamps, raw_gyro[:, 0], 'r-', label='X-axis', linewidth=1)
        ax2.plot(timestamps, raw_gyro[:, 1], 'g-', label='Y-axis', linewidth=1)
        ax2.plot(timestamps, raw_gyro[:, 2], 'b-', label='Z-axis', linewidth=1)
        ax2.set_xlabel('Time (s)')
        ax2.set_ylabel('Angular Velocity (rad/s)')
        ax2.set_title('Raw Gyroscope Data')
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        
        # Placeholder plots for consistency
        ax3 = axes[1, 0]
        ax3.text(0.5, 0.5, 'Euler Angles\n(Available with Filtered Mode)', 
                ha='center', va='center', transform=ax3.transAxes, fontsize=12)
        ax3.set_title('Euler Angles (Not Available)')
        
        # Accelerometer magnitude
        ax4 = axes[1, 1]
        accel_magnitude = np.sqrt(np.sum(raw_accel**2, axis=1))
        ax4.plot(timestamps, accel_magnitude, 'purple', linewidth=2)
        ax4.axhline(y=9.81, color='red', linestyle='--', alpha=0.7, label='1g (9.81 m/s²)')
        ax4.set_xlabel('Time (s)')
        ax4.set_ylabel('Acceleration Magnitude (m/s²)')
        ax4.set_title('Raw Accelerometer Magnitude')
        ax4.legend()
        ax4.grid(True, alpha=0.3)
        
        plot_type = "raw"
    
    plt.tight_layout()
    
    # Save plot
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    plot_filename = f'/home/dice/DiceMaster/DiceMaster_Central/tests/imu_data_{plot_type}_{timestamp_str}.png'
    plt.savefig(plot_filename, dpi=300, bbox_inches='tight')
    print(f"\nPlot saved to: {plot_filename}")
    
    # Save raw data
    data_filename = f'/home/dice/DiceMaster/DiceMaster_Central/tests/imu_data_{plot_type}_{timestamp_str}.npz'
    np.savez(data_filename, 
             timestamps=timestamps,
             raw_accel=np.array([raw_data['accel']['x'], raw_data['accel']['y'], raw_data['accel']['z']]).T,
             raw_gyro=np.array([raw_data['gyro']['x'], raw_data['gyro']['y'], raw_data['gyro']['z']]).T,
             filtered_accel=np.array([filtered_data['accel']['x'], filtered_data['accel']['y'], filtered_data['accel']['z']]).T,
             filtered_gyro=np.array([filtered_data['gyro']['x'], filtered_data['gyro']['y'], filtered_data['gyro']['z']]).T,
             quaternions=np.array(quaternions),
             euler_angles=np.array(euler_angles))
    print(f"Raw data saved to: {data_filename}")
    
    # Print statistics
    if compare_both or not use_filtered:
        raw_accel_array = np.array([raw_data['accel']['x'], raw_data['accel']['y'], raw_data['accel']['z']]).T
        raw_gyro_array = np.array([raw_data['gyro']['x'], raw_data['gyro']['y'], raw_data['gyro']['z']]).T
        
        print("\nRaw Accelerometer Statistics (m/s²):")
        print(f"  X-axis: mean={np.mean(raw_accel_array[:, 0]):.3f}, std={np.std(raw_accel_array[:, 0]):.3f}")
        print(f"  Y-axis: mean={np.mean(raw_accel_array[:, 1]):.3f}, std={np.std(raw_accel_array[:, 1]):.3f}")
        print(f"  Z-axis: mean={np.mean(raw_accel_array[:, 2]):.3f}, std={np.std(raw_accel_array[:, 2]):.3f}")
        
        print("\nRaw Gyroscope Statistics (rad/s):")
        print(f"  X-axis: mean={np.mean(raw_gyro_array[:, 0]):.6f}, std={np.std(raw_gyro_array[:, 0]):.6f}")
        print(f"  Y-axis: mean={np.mean(raw_gyro_array[:, 1]):.6f}, std={np.std(raw_gyro_array[:, 1]):.6f}")
        print(f"  Z-axis: mean={np.mean(raw_gyro_array[:, 2]):.6f}, std={np.std(raw_gyro_array[:, 2]):.6f}")
    
    if compare_both or use_filtered:
        filtered_accel_array = np.array([filtered_data['accel']['x'], filtered_data['accel']['y'], filtered_data['accel']['z']]).T
        filtered_gyro_array = np.array([filtered_data['gyro']['x'], filtered_data['gyro']['y'], filtered_data['gyro']['z']]).T
        
        print("\nFiltered Accelerometer Statistics (m/s²):")
        print(f"  X-axis: mean={np.mean(filtered_accel_array[:, 0]):.3f}, std={np.std(filtered_accel_array[:, 0]):.3f}")
        print(f"  Y-axis: mean={np.mean(filtered_accel_array[:, 1]):.3f}, std={np.std(filtered_accel_array[:, 1]):.3f}")
        print(f"  Z-axis: mean={np.mean(filtered_accel_array[:, 2]):.3f}, std={np.std(filtered_accel_array[:, 2]):.3f}")
        
        print("\nFiltered Gyroscope Statistics (rad/s):")
        print(f"  X-axis: mean={np.mean(filtered_gyro_array[:, 0]):.6f}, std={np.std(filtered_gyro_array[:, 0]):.6f}")
        print(f"  Y-axis: mean={np.mean(filtered_gyro_array[:, 1]):.6f}, std={np.std(filtered_gyro_array[:, 1]):.6f}")
        print(f"  Z-axis: mean={np.mean(filtered_gyro_array[:, 2]):.6f}, std={np.std(filtered_gyro_array[:, 2]):.6f}")
    
    # Show plot
    plt.show()
    
    return {
        'timestamps': timestamps,
        'raw_data': raw_data,
        'filtered_data': filtered_data,
        'quaternions': quaternions,
        'euler_angles': euler_angles
    }


if __name__ == "__main__":
    print("IMU Test Script")
    print("===============")
    print("This script will read IMU data from MPU6050 on I2C bus 6")
    print("(GPIO pins 15 and 16 - SDA6 and SCL6)")
    print()
    
    # Test parameters
    duration = 30  # seconds
    sample_rate = 50  # Hz
    
    # Test mode selection
    print("Select test mode:")
    print("1. Raw IMU data only")
    print("2. Filtered IMU data only (with calibration)")
    print("3. Compare both raw and filtered data")
    
    try:
        mode = input("Enter mode (1-3, default: 1): ").strip()
        if not mode:
            mode = "1"
        
        use_filtered = mode == "2"
        compare_both = mode == "3"
        
        if mode not in ["1", "2", "3"]:
            print("Invalid mode, using raw data only")
            use_filtered = False
            compare_both = False
        
        # Allow user to customize duration and sample rate
        duration_input = input(f"Enter duration in seconds (default: {duration}): ").strip()
        if duration_input:
            duration = float(duration_input)
            
        rate_input = input(f"Enter sample rate in Hz (default: {sample_rate}): ").strip()
        if rate_input:
            sample_rate = float(rate_input)
            
    except ValueError:
        print("Invalid input, using defaults")
        use_filtered = False
        compare_both = False
    
    print(f"\nUsing duration: {duration}s, sample rate: {sample_rate} Hz")
    
    if use_filtered or compare_both:
        print("Note: Filtered mode includes automatic calibration")
    
    print("Keep the IMU perfectly still for consistent readings!")
    
    input("Press Enter to start data collection...")
    
    # Run the test
    data = test_imu_reading(duration, sample_rate, use_filtered, compare_both)
    
    print("\nTest completed successfully!")
