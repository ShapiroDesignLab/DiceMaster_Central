#!/usr/bin/env python3
"""
IMU Data Recording and Plotting Test

This script records IMU data from the DiceMaster system, stores it in a CSV file,
and generates plots showing accelerometer and gyroscope data over time.

Author: GitHub Copilot
Date: July 6, 2025
"""

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Vector3
from dicemaster_central_msgs.msg import RawIMU
import matplotlib.pyplot as plt
import numpy as np
import csv
import os
import time
from datetime import datetime
import threading
import signal
import sys


class IMUDataRecorder(Node):
    """Node to record IMU data and create plots"""
    
    def __init__(self, recording_duration=30.0, output_dir="/tmp/imu_data"):
        super().__init__('imu_data_recorder')
        
        # Parameters
        self.recording_duration = recording_duration
        self.output_dir = output_dir
        self.start_time = None
        self.data_lock = threading.Lock()
        
        # Data storage
        self.imu_data = []
        self.timestamps = []
        
        # Create output directory
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Subscribers for IMU data
        self.raw_imu_sub = self.create_subscription(
            RawIMU,
            '/dice_hw/imu/raw',
            self.raw_imu_callback,
            10
        )
        
        # Alternative subscribers in case raw IMU is not available
        self.accel_sub = self.create_subscription(
            Vector3,
            '/dice_hw/imu/accel',
            self.accel_callback,
            10
        )
        
        self.angvel_sub = self.create_subscription(
            Vector3,
            '/dice_hw/imu/angvel',
            self.angvel_callback,
            10
        )
        
        # Recording state
        self.recording = False
        self.recording_complete = False
        
        # Storage for separate accel/gyro data if using individual topics
        self.latest_accel = None
        self.latest_gyro = None
        
        # Timer for recording duration
        self.recording_timer = None
        
        self.get_logger().info(f'IMU Data Recorder initialized')
        self.get_logger().info(f'Output directory: {self.output_dir}')
        self.get_logger().info(f'Recording duration: {self.recording_duration} seconds')
        
    def start_recording(self):
        """Start recording IMU data"""
        if self.recording:
            self.get_logger().warn('Recording already in progress')
            return
            
        self.recording = True
        self.start_time = self.get_clock().now()
        self.data_lock = threading.Lock()
        
        # Clear previous data
        with self.data_lock:
            self.imu_data.clear()
            self.timestamps.clear()
        
        self.get_logger().info('Starting IMU data recording...')
        
        # Set timer to stop recording
        self.recording_timer = self.create_timer(
            self.recording_duration,
            self.stop_recording
        )
        
    def stop_recording(self):
        """Stop recording and process data"""
        if not self.recording:
            return
            
        self.recording = False
        if self.recording_timer:
            self.recording_timer.cancel()
            self.recording_timer = None
            
        self.get_logger().info('Stopping IMU data recording...')
        
        # Process and save data
        self.save_data_to_csv()
        self.create_plots()
        
        self.recording_complete = True
        self.get_logger().info('Recording complete!')
        
    def raw_imu_callback(self, msg):
        """Callback for raw IMU data"""
        if not self.recording:
            return
            
        current_time = self.get_clock().now()
        time_diff = (current_time - self.start_time).nanoseconds * 1e-9
        
        data_point = {
            'timestamp': time_diff,
            'accel_x': msg.accel_x,
            'accel_y': msg.accel_y,
            'accel_z': msg.accel_z,
            'gyro_x': msg.gyro_x,
            'gyro_y': msg.gyro_y,
            'gyro_z': msg.gyro_z,
            'temperature': msg.temperature
        }
        
        with self.data_lock:
            self.imu_data.append(data_point)
            self.timestamps.append(time_diff)
            
    def accel_callback(self, msg):
        """Callback for accelerometer data"""
        if not self.recording:
            return
            
        self.latest_accel = {
            'x': msg.x,
            'y': msg.y,
            'z': msg.z
        }
        
        # If we have both accel and gyro, combine them
        if self.latest_gyro is not None:
            self._combine_and_store_data()
            
    def angvel_callback(self, msg):
        """Callback for gyroscope data"""
        if not self.recording:
            return
            
        self.latest_gyro = {
            'x': msg.x,
            'y': msg.y,
            'z': msg.z
        }
        
        # If we have both accel and gyro, combine them
        if self.latest_accel is not None:
            self._combine_and_store_data()
            
    def _combine_and_store_data(self):
        """Combine accelerometer and gyroscope data and store"""
        if self.latest_accel is None or self.latest_gyro is None:
            return
            
        current_time = self.get_clock().now()
        time_diff = (current_time - self.start_time).nanoseconds * 1e-9
        
        data_point = {
            'timestamp': time_diff,
            'accel_x': self.latest_accel['x'],
            'accel_y': self.latest_accel['y'],
            'accel_z': self.latest_accel['z'],
            'gyro_x': self.latest_gyro['x'],
            'gyro_y': self.latest_gyro['y'],
            'gyro_z': self.latest_gyro['z'],
            'temperature': 0.0  # Not available from separate topics
        }
        
        with self.data_lock:
            self.imu_data.append(data_point)
            self.timestamps.append(time_diff)
            
    def save_data_to_csv(self):
        """Save recorded data to CSV file"""
        if not self.imu_data:
            self.get_logger().warn('No data to save')
            return
            
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_filename = os.path.join(self.output_dir, f'imu_data_{timestamp_str}.csv')
        
        with open(csv_filename, 'w', newline='') as csvfile:
            fieldnames = ['timestamp', 'accel_x', 'accel_y', 'accel_z', 
                         'gyro_x', 'gyro_y', 'gyro_z', 'temperature']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            writer.writeheader()
            with self.data_lock:
                for data_point in self.imu_data:
                    writer.writerow(data_point)
                    
        self.get_logger().info(f'Data saved to: {csv_filename}')
        return csv_filename
        
    def create_plots(self):
        """Create and save plots of IMU data"""
        if not self.imu_data:
            self.get_logger().warn('No data to plot')
            return
            
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Extract data for plotting
        with self.data_lock:
            timestamps = [d['timestamp'] for d in self.imu_data]
            accel_x = [d['accel_x'] for d in self.imu_data]
            accel_y = [d['accel_y'] for d in self.imu_data]
            accel_z = [d['accel_z'] for d in self.imu_data]
            gyro_x = [d['gyro_x'] for d in self.imu_data]
            gyro_y = [d['gyro_y'] for d in self.imu_data]
            gyro_z = [d['gyro_z'] for d in self.imu_data]
            
        # Create accelerometer plot
        plt.figure(figsize=(12, 8))
        
        plt.subplot(2, 1, 1)
        plt.plot(timestamps, accel_x, 'r-', label='Accel X', linewidth=1)
        plt.plot(timestamps, accel_y, 'g-', label='Accel Y', linewidth=1)
        plt.plot(timestamps, accel_z, 'b-', label='Accel Z', linewidth=1)
        plt.xlabel('Time (seconds)')
        plt.ylabel('Acceleration (m/s²)')
        plt.title('Accelerometer Data')
        plt.legend()
        plt.grid(True, alpha=0.3)
        
        # Create gyroscope plot
        plt.subplot(2, 1, 2)
        plt.plot(timestamps, gyro_x, 'r-', label='Gyro X', linewidth=1)
        plt.plot(timestamps, gyro_y, 'g-', label='Gyro Y', linewidth=1)
        plt.plot(timestamps, gyro_z, 'b-', label='Gyro Z', linewidth=1)
        plt.xlabel('Time (seconds)')
        plt.ylabel('Angular Velocity (rad/s)')
        plt.title('Gyroscope Data')
        plt.legend()
        plt.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        # Save the plot
        plot_filename = os.path.join(self.output_dir, f'imu_plots_{timestamp_str}.png')
        plt.savefig(plot_filename, dpi=300, bbox_inches='tight')
        plt.close()
        
        self.get_logger().info(f'Plots saved to: {plot_filename}')
        
        # Create separate plots for better readability
        self._create_separate_plots(timestamps, accel_x, accel_y, accel_z, 
                                  gyro_x, gyro_y, gyro_z, timestamp_str)
        
    def _create_separate_plots(self, timestamps, accel_x, accel_y, accel_z, 
                              gyro_x, gyro_y, gyro_z, timestamp_str):
        """Create separate plots for accelerometer and gyroscope data"""
        
        # Accelerometer plot
        plt.figure(figsize=(12, 6))
        plt.plot(timestamps, accel_x, 'r-', label='X-axis', linewidth=1.5)
        plt.plot(timestamps, accel_y, 'g-', label='Y-axis', linewidth=1.5)
        plt.plot(timestamps, accel_z, 'b-', label='Z-axis', linewidth=1.5)
        plt.xlabel('Time (seconds)')
        plt.ylabel('Acceleration (m/s²)')
        plt.title('Accelerometer Data - All Axes')
        plt.legend()
        plt.grid(True, alpha=0.3)
        
        accel_filename = os.path.join(self.output_dir, f'accelerometer_{timestamp_str}.png')
        plt.savefig(accel_filename, dpi=300, bbox_inches='tight')
        plt.close()
        
        # Gyroscope plot
        plt.figure(figsize=(12, 6))
        plt.plot(timestamps, gyro_x, 'r-', label='X-axis', linewidth=1.5)
        plt.plot(timestamps, gyro_y, 'g-', label='Y-axis', linewidth=1.5)
        plt.plot(timestamps, gyro_z, 'b-', label='Z-axis', linewidth=1.5)
        plt.xlabel('Time (seconds)')
        plt.ylabel('Angular Velocity (rad/s)')
        plt.title('Gyroscope Data - All Axes')
        plt.legend()
        plt.grid(True, alpha=0.3)
        
        gyro_filename = os.path.join(self.output_dir, f'gyroscope_{timestamp_str}.png')
        plt.savefig(gyro_filename, dpi=300, bbox_inches='tight')
        plt.close()
        
        self.get_logger().info(f'Separate plots saved:')
        self.get_logger().info(f'  Accelerometer: {accel_filename}')
        self.get_logger().info(f'  Gyroscope: {gyro_filename}')
        
    def get_data_summary(self):
        """Get summary statistics of recorded data"""
        if not self.imu_data:
            return "No data recorded"
            
        with self.data_lock:
            data_count = len(self.imu_data)
            duration = self.timestamps[-1] - self.timestamps[0] if self.timestamps else 0
            sample_rate = data_count / duration if duration > 0 else 0
            
            # Calculate statistics
            accel_x_vals = [d['accel_x'] for d in self.imu_data]
            accel_y_vals = [d['accel_y'] for d in self.imu_data]
            accel_z_vals = [d['accel_z'] for d in self.imu_data]
            gyro_x_vals = [d['gyro_x'] for d in self.imu_data]
            gyro_y_vals = [d['gyro_y'] for d in self.imu_data]
            gyro_z_vals = [d['gyro_z'] for d in self.imu_data]
            
            summary = f"""
IMU Data Recording Summary:
==========================
Data Points: {data_count}
Duration: {duration:.2f} seconds
Sample Rate: {sample_rate:.1f} Hz

Accelerometer Statistics (m/s²):
  X-axis: min={min(accel_x_vals):.3f}, max={max(accel_x_vals):.3f}, mean={np.mean(accel_x_vals):.3f}, std={np.std(accel_x_vals):.3f}
  Y-axis: min={min(accel_y_vals):.3f}, max={max(accel_y_vals):.3f}, mean={np.mean(accel_y_vals):.3f}, std={np.std(accel_y_vals):.3f}
  Z-axis: min={min(accel_z_vals):.3f}, max={max(accel_z_vals):.3f}, mean={np.mean(accel_z_vals):.3f}, std={np.std(accel_z_vals):.3f}

Gyroscope Statistics (rad/s):
  X-axis: min={min(gyro_x_vals):.3f}, max={max(gyro_x_vals):.3f}, mean={np.mean(gyro_x_vals):.3f}, std={np.std(gyro_x_vals):.3f}
  Y-axis: min={min(gyro_y_vals):.3f}, max={max(gyro_y_vals):.3f}, mean={np.mean(gyro_y_vals):.3f}, std={np.std(gyro_y_vals):.3f}
  Z-axis: min={min(gyro_z_vals):.3f}, max={max(gyro_z_vals):.3f}, mean={np.mean(gyro_z_vals):.3f}, std={np.std(gyro_z_vals):.3f}
"""
            
            return summary


def signal_handler(signum, frame):
    """Handle Ctrl+C gracefully"""
    print("\nShutting down IMU data recorder...")
    rclpy.shutdown()
    sys.exit(0)


def main(args=None):
    """Main function"""
    rclpy.init(args=args)
    
    # Set up signal handler for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    
    # Create recorder node
    duration = 30.0  # Default recording duration
    output_dir = "/tmp/imu_data"
    
    if len(sys.argv) > 1:
        try:
            duration = float(sys.argv[1])
        except ValueError:
            print(f"Invalid duration: {sys.argv[1]}. Using default: {duration}s")
            
    if len(sys.argv) > 2:
        output_dir = sys.argv[2]
    
    recorder = IMUDataRecorder(recording_duration=duration, output_dir=output_dir)
    
    print(f"\nIMU Data Recorder")
    print(f"================")
    print(f"Recording Duration: {duration} seconds")
    print(f"Output Directory: {output_dir}")
    print(f"\nWaiting for IMU data...")
    print(f"Press Ctrl+C to stop early\n")
    
    # Start recording automatically
    recorder.start_recording()
    
    try:
        # Spin until recording is complete
        while rclpy.ok() and not recorder.recording_complete:
            rclpy.spin_once(recorder, timeout_sec=0.1)
            
        if recorder.recording_complete:
            print("\n" + recorder.get_data_summary())
            
    except KeyboardInterrupt:
        print("\nStopping recording early...")
        recorder.stop_recording()
        if recorder.imu_data:
            print("\n" + recorder.get_data_summary())
        
    finally:
        recorder.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
