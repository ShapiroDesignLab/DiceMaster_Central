#!/usr/bin/env python3
"""
Test script for the Remote Logger
Can be used to test the remote logger functionality without ROS
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import threading
import subprocess
from DiceMaster_Central.remote_logger import RemoteLogger, LogEntry
from datetime import datetime


def simulate_ros_logs(remote_logger):
    """Simulate some ROS logs for testing"""
    test_logs = [
        ("INFO", "test_node", "Starting test node"),
        ("WARN", "screen_1", "Screen connection timeout"),
        ("ERROR", "imu_node", "IMU calibration failed"),
        ("DEBUG", "strategy", "Processing dice roll"),
        ("INFO", "protocol", "Message sent successfully"),
        ("WARN", "media", "Low disk space warning"),
        ("INFO", "test_node", "Test completed successfully"),
    ]
    
    for i in range(50):  # Add 50 test logs
        level, source, message = test_logs[i % len(test_logs)]
        timestamp = datetime.now().isoformat()
        
        # Add sequence number to make logs unique
        full_message = f"{message} (sequence: {i+1})"
        
        log_entry = LogEntry(timestamp, level, source, full_message)
        remote_logger.logs.append(log_entry)
        
        time.sleep(0.1)  # Small delay between logs


def main():
    """Main test function"""
    print("🎲 DiceMaster Remote Logger Test")
    print("=" * 40)
    
    # Check for openssl (needed for self-signed certificates)
    try:
        subprocess.run(['openssl', 'version'], check=True, capture_output=True)
        print("✓ OpenSSL found")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("⚠️  OpenSSL not found - using dummy certificates")
    
    # Create remote logger instance (without ROS)
    class TestRemoteLogger(RemoteLogger):
        def __init__(self, port=8443, max_logs=1000):
            # Initialize without calling super().__init__ to avoid ROS
            self.port = port
            self.max_logs = max_logs
            from collections import deque
            self.logs = deque(maxlen=max_logs)
            self.running = False
            self.server = None
            self.log_thread = None
            self.log_process = None
            
            # Create a simple logger for testing BEFORE SSL setup
            import logging
            self.logger = logging.getLogger('test_remote_logger')
            self.logger.setLevel(logging.INFO)
            if not self.logger.handlers:
                handler = logging.StreamHandler()
                handler.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
                self.logger.addHandler(handler)
            
            # Now setup SSL context
            self.ssl_context = self._setup_ssl_context(None, None)
            self.start_time = time.time()
        
        def _capture_ros_logs(self):
            # Override to avoid trying to capture ROS logs in test mode
            self.logger.info("Test mode: ROS log capture disabled")
            pass
            
        def _publish_status(self):
            # Override to avoid ROS publishing
            pass
            
        def destroy_node(self):
            # Override to avoid ROS cleanup
            pass
            pass
    
    remote_logger = TestRemoteLogger(port=8443)
    
    # Start log simulation in background
    log_thread = threading.Thread(target=simulate_ros_logs, args=(remote_logger,), daemon=True)
    log_thread.start()
    
    print(f"🌐 Starting HTTPS server on port {remote_logger.port}")
    print(f"📊 Access the web interface at: https://localhost:{remote_logger.port}")
    print("⚠️  You may see a security warning due to self-signed certificate - this is normal")
    print("📝 Simulating ROS logs...")
    print("\nPress Ctrl+C to stop")
    
    try:
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Start server
        loop.run_until_complete(remote_logger.start_server())
        
    except KeyboardInterrupt:
        print("\n🛑 Shutting down...")
        remote_logger.stop_server()
    except Exception as e:
        print(f"❌ Error: {e}")
        print("\nTip: Make sure the port is not already in use")
        return 1
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
