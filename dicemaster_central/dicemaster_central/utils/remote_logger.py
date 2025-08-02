"""
Remote Logger for DiceMaster Central
Captures ROS logs and serves them via HTTPS web interface
"""

import asyncio
import ssl
import json
import logging
import os
import re
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
from collections import deque
from urllib.parse import parse_qs, urlparse

# Try to import ROS, but make it optional for testing
try:
    import rclpy
    from rclpy.node import Node
    from rclpy.logging import get_logger
    from std_msgs.msg import String
    ROS_AVAILABLE = True
except ImportError:
    ROS_AVAILABLE = False
    # Mock ROS classes for testing
    class Node:
        def __init__(self, name):
            self.name = name
        def create_publisher(self, *args, **kwargs):
            return None
        def create_timer(self, *args, **kwargs):
            return None
        def destroy_node(self):
            pass
    
    def get_logger(name):
        import logging
        return logging.getLogger(name)


class LogEntry:
    """Represents a single log entry"""
    
    def __init__(self, timestamp: str, level: str, source: str, message: str):
        self.timestamp = timestamp
        self.level = level
        self.source = source
        self.message = message
        
    def to_dict(self) -> Dict:
        return {
            'timestamp': self.timestamp,
            'level': self.level,
            'source': self.source,
            'message': self.message
        }


class RemoteLogger(Node):
    """
    Remote logger node that captures ROS logs and serves them via HTTPS
    """
    
    def __init__(self, port: int = 8443, max_logs: int = 1000, 
                 cert_file: Optional[str] = None, key_file: Optional[str] = None):
        if ROS_AVAILABLE:
            super().__init__('remote_logger')
        else:
            # Mock Node initialization for testing
            self.name = 'remote_logger'
        
        self.port = port
        self.max_logs = max_logs
        self.logs = deque(maxlen=max_logs)
        self.running = False
        self.server = None
        
        # Setup SSL context
        self.ssl_context = self._setup_ssl_context(cert_file, key_file)
        
        # Log capture thread
        self.log_thread = None
        self.log_process = None
        
        # ROS logger
        self.logger = get_logger('remote_logger')
        
        if ROS_AVAILABLE:
            # Publishers for status
            self.status_pub = self.create_publisher(String, '/remote_logger/status', 10)
            
            # Timer for periodic status updates
            self.status_timer = self.create_timer(5.0, self._publish_status)
        else:
            self.status_pub = None
            self.status_timer = None
        
        self.logger.info(f"Remote Logger initialized on port {port}")
    
    def _setup_ssl_context(self, cert_file: Optional[str], key_file: Optional[str]) -> ssl.SSLContext:
        """Setup SSL context for HTTPS"""
        context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        
        # Use provided certificates or generate self-signed
        if cert_file and key_file and os.path.exists(cert_file) and os.path.exists(key_file):
            context.load_cert_chain(cert_file, key_file)
            self.logger.info(f"Using provided SSL certificates: {cert_file}, {key_file}")
        else:
            # Generate self-signed certificate
            cert_path, key_path = self._generate_self_signed_cert()
            context.load_cert_chain(cert_path, key_path)
            self.logger.info(f"Generated self-signed SSL certificates: {cert_path}, {key_path}")
        
        return context
    
    def _generate_self_signed_cert(self) -> tuple:
        """Generate a self-signed certificate for HTTPS"""
        cert_dir = Path.home() / '.dicemaster' / 'certs'
        cert_dir.mkdir(parents=True, exist_ok=True)
        
        cert_file = cert_dir / 'server.crt'
        key_file = cert_dir / 'server.key'
        
        # Only generate if files don't exist
        if not cert_file.exists() or not key_file.exists():
            cmd = [
                'openssl', 'req', '-x509', '-newkey', 'rsa:4096', '-keyout', str(key_file),
                '-out', str(cert_file), '-days', '365', '-nodes',
                '-subj', '/C=US/ST=State/L=City/O=DiceMaster/CN=localhost'
            ]
            
            try:
                subprocess.run(cmd, check=True, capture_output=True)
                self.logger.info("Generated self-signed certificate")
            except subprocess.CalledProcessError as e:
                self.logger.error(f"Failed to generate certificate: {e}")
                # Fallback to simple files
                cert_file.write_text("DUMMY_CERT")
                key_file.write_text("DUMMY_KEY")
        
        return str(cert_file), str(key_file)
    
    def _capture_ros_logs(self):
        """Capture ROS logs using ros2 topic echo"""
        try:
            # Start ros2 topic echo for rosout
            self.log_process = subprocess.Popen(
                ['ros2', 'topic', 'echo', '/rosout', '--no-arr'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )
            
            self.logger.info("Started ROS log capture")
            
            for line in iter(self.log_process.stdout.readline, ''):
                if not self.running:
                    break
                    
                line = line.strip()
                if line:
                    self._parse_and_store_log(line)
                    
        except Exception as e:
            self.logger.error(f"Error capturing ROS logs: {e}")
        finally:
            if self.log_process:
                self.log_process.terminate()
                self.log_process.wait()
    
    def _parse_and_store_log(self, log_line: str):
        """Parse and store a ROS log line"""
        try:
            # Simple parsing - in real implementation, you might want more sophisticated parsing
            timestamp = datetime.now().isoformat()
            
            # Extract level and message using regex
            level_match = re.search(r'\[(INFO|WARN|ERROR|DEBUG|FATAL)\]', log_line)
            level = level_match.group(1) if level_match else "INFO"
            
            # Extract source node name
            source_match = re.search(r'\[(\w+)\]', log_line)
            source = source_match.group(1) if source_match else "unknown"
            
            # Clean up the message
            message = re.sub(r'\[.*?\]', '', log_line).strip()
            
            log_entry = LogEntry(timestamp, level, source, message)
            self.logs.append(log_entry)
            
        except Exception as e:
            self.logger.error(f"Error parsing log line: {e}")
    
    async def _handle_request(self, reader, writer):
        """Handle incoming HTTP requests"""
        try:
            # Read request
            request_data = await reader.read(1024)
            request_str = request_data.decode('utf-8')
            
            # Parse request
            lines = request_str.split('\n')
            if not lines:
                return
                
            request_line = lines[0]
            method, path, _ = request_line.split(' ', 2)
            
            # Parse URL and query parameters
            parsed_url = urlparse(path)
            query_params = parse_qs(parsed_url.query)
            
            # Route requests
            if parsed_url.path == '/':
                response = self._generate_main_page()
            elif parsed_url.path == '/api/logs':
                response = self._generate_logs_api(query_params)
            elif parsed_url.path == '/api/status':
                response = self._generate_status_api()
            else:
                response = self._generate_404_page()
            
            # Send response
            writer.write(response.encode('utf-8'))
            await writer.drain()
            
        except Exception as e:
            self.logger.error(f"Error handling request: {e}")
            error_response = self._generate_error_page(str(e))
            writer.write(error_response.encode('utf-8'))
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()
    
    def _generate_main_page(self) -> str:
        """Generate the main HTML page"""
        html_content = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>DiceMaster Remote Logger</title>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }
                .container { max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
                h1 { color: #333; text-align: center; margin-bottom: 30px; }
                .controls { margin-bottom: 20px; display: flex; gap: 10px; flex-wrap: wrap; }
                .controls select, .controls button { padding: 8px 15px; border: 1px solid #ddd; border-radius: 5px; }
                .controls button { background-color: #007bff; color: white; cursor: pointer; }
                .controls button:hover { background-color: #0056b3; }
                .log-container { border: 1px solid #ddd; border-radius: 5px; max-height: 600px; overflow-y: auto; background-color: #f8f9fa; }
                .log-entry { padding: 10px; border-bottom: 1px solid #eee; font-family: monospace; font-size: 14px; }
                .log-entry:last-child { border-bottom: none; }
                .log-entry.ERROR { background-color: #ffebee; border-left: 4px solid #f44336; }
                .log-entry.WARN { background-color: #fff3e0; border-left: 4px solid #ff9800; }
                .log-entry.INFO { background-color: #e8f5e8; border-left: 4px solid #4caf50; }
                .log-entry.DEBUG { background-color: #f3e5f5; border-left: 4px solid #9c27b0; }
                .timestamp { color: #666; font-size: 12px; }
                .level { font-weight: bold; padding: 2px 6px; border-radius: 3px; color: white; font-size: 12px; }
                .level.ERROR { background-color: #f44336; }
                .level.WARN { background-color: #ff9800; }
                .level.INFO { background-color: #4caf50; }
                .level.DEBUG { background-color: #9c27b0; }
                .source { color: #2196f3; font-weight: bold; }
                .message { margin-top: 5px; }
                .status { margin-bottom: 20px; padding: 10px; border-radius: 5px; background-color: #e8f5e8; border: 1px solid #4caf50; }
                .loading { text-align: center; padding: 20px; color: #666; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🎲 DiceMaster Remote Logger</h1>
                
                <div class="status" id="status">
                    <strong>Status:</strong> <span id="status-text">Loading...</span>
                </div>
                
                <div class="controls">
                    <select id="levelFilter">
                        <option value="">All Levels</option>
                        <option value="ERROR">Error</option>
                        <option value="WARN">Warning</option>
                        <option value="INFO">Info</option>
                        <option value="DEBUG">Debug</option>
                    </select>
                    <select id="sourceFilter">
                        <option value="">All Sources</option>
                    </select>
                    <button onclick="refreshLogs()">Refresh</button>
                    <button onclick="clearLogs()">Clear</button>
                    <button onclick="toggleAutoRefresh()">Auto-refresh: <span id="autoRefreshStatus">OFF</span></button>
                </div>
                
                <div class="log-container" id="logContainer">
                    <div class="loading">Loading logs...</div>
                </div>
            </div>
            
            <script>
                let autoRefreshInterval;
                let autoRefreshEnabled = false;
                
                function refreshLogs() {
                    const levelFilter = document.getElementById('levelFilter').value;
                    const sourceFilter = document.getElementById('sourceFilter').value;
                    
                    let url = '/api/logs?';
                    if (levelFilter) url += 'level=' + levelFilter + '&';
                    if (sourceFilter) url += 'source=' + sourceFilter + '&';
                    
                    fetch(url)
                        .then(response => response.json())
                        .then(data => {
                            displayLogs(data.logs);
                            updateSourceFilter(data.sources);
                        })
                        .catch(error => {
                            console.error('Error fetching logs:', error);
                            document.getElementById('logContainer').innerHTML = '<div class="loading">Error loading logs: ' + error + '</div>';
                        });
                }
                
                function displayLogs(logs) {
                    const container = document.getElementById('logContainer');
                    if (logs.length === 0) {
                        container.innerHTML = '<div class="loading">No logs available</div>';
                        return;
                    }
                    
                    container.innerHTML = logs.map(log => `
                        <div class="log-entry ${log.level}">
                            <div>
                                <span class="timestamp">${log.timestamp}</span>
                                <span class="level ${log.level}">${log.level}</span>
                                <span class="source">[${log.source}]</span>
                            </div>
                            <div class="message">${log.message}</div>
                        </div>
                    `).join('');
                    
                    // Auto-scroll to bottom
                    container.scrollTop = container.scrollHeight;
                }
                
                function updateSourceFilter(sources) {
                    const sourceFilter = document.getElementById('sourceFilter');
                    const currentValue = sourceFilter.value;
                    
                    // Keep current options, add new ones
                    const existingOptions = new Set(Array.from(sourceFilter.options).map(opt => opt.value));
                    
                    sources.forEach(source => {
                        if (!existingOptions.has(source)) {
                            const option = document.createElement('option');
                            option.value = source;
                            option.textContent = source;
                            sourceFilter.appendChild(option);
                        }
                    });
                    
                    sourceFilter.value = currentValue;
                }
                
                function clearLogs() {
                    if (confirm('Are you sure you want to clear all logs?')) {
                        // This would need backend implementation
                        alert('Clear logs functionality not implemented yet');
                    }
                }
                
                function toggleAutoRefresh() {
                    autoRefreshEnabled = !autoRefreshEnabled;
                    const statusSpan = document.getElementById('autoRefreshStatus');
                    
                    if (autoRefreshEnabled) {
                        statusSpan.textContent = 'ON';
                        autoRefreshInterval = setInterval(refreshLogs, 2000);
                    } else {
                        statusSpan.textContent = 'OFF';
                        clearInterval(autoRefreshInterval);
                    }
                }
                
                function updateStatus() {
                    fetch('/api/status')
                        .then(response => response.json())
                        .then(data => {
                            document.getElementById('status-text').textContent = data.status;
                        })
                        .catch(error => {
                            document.getElementById('status-text').textContent = 'Error: ' + error;
                        });
                }
                
                // Initialize
                document.addEventListener('DOMContentLoaded', function() {
                    refreshLogs();
                    updateStatus();
                    setInterval(updateStatus, 5000);
                });
            </script>
        </body>
        </html>
        """
        
        return f"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nContent-Length: {len(html_content)}\r\n\r\n{html_content}"
    
    def _generate_logs_api(self, query_params: Dict) -> str:
        """Generate logs API response"""
        level_filter = query_params.get('level', [None])[0]
        source_filter = query_params.get('source', [None])[0]
        
        # Filter logs
        filtered_logs = []
        sources = set()
        
        for log in self.logs:
            sources.add(log.source)
            
            if level_filter and log.level != level_filter:
                continue
            if source_filter and log.source != source_filter:
                continue
                
            filtered_logs.append(log.to_dict())
        
        response_data = {
            'logs': list(reversed(filtered_logs)),  # Most recent first
            'sources': sorted(list(sources)),
            'total_count': len(self.logs),
            'filtered_count': len(filtered_logs)
        }
        
        json_content = json.dumps(response_data, indent=2)
        return f"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {len(json_content)}\r\n\r\n{json_content}"
    
    def _generate_status_api(self) -> str:
        """Generate status API response"""
        status_data = {
            'status': f'Running - {len(self.logs)} logs captured',
            'port': self.port,
            'max_logs': self.max_logs,
            'current_logs': len(self.logs),
            'uptime': time.time() - self.start_time if hasattr(self, 'start_time') else 0
        }
        
        json_content = json.dumps(status_data)
        return f"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {len(json_content)}\r\n\r\n{json_content}"
    
    def _generate_404_page(self) -> str:
        """Generate 404 error page"""
        html_content = """
        <!DOCTYPE html>
        <html>
        <head><title>404 Not Found</title></head>
        <body>
            <h1>404 Not Found</h1>
            <p>The requested resource was not found.</p>
            <a href="/">Return to main page</a>
        </body>
        </html>
        """
        return f"HTTP/1.1 404 Not Found\r\nContent-Type: text/html\r\nContent-Length: {len(html_content)}\r\n\r\n{html_content}"
    
    def _generate_error_page(self, error_msg: str) -> str:
        """Generate error page"""
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head><title>Error</title></head>
        <body>
            <h1>Error</h1>
            <p>{error_msg}</p>
            <a href="/">Return to main page</a>
        </body>
        </html>
        """
        return f"HTTP/1.1 500 Internal Server Error\r\nContent-Type: text/html\r\nContent-Length: {len(html_content)}\r\n\r\n{html_content}"
    
    def _publish_status(self):
        """Publish status message"""
        if ROS_AVAILABLE and hasattr(self, 'status_pub') and self.status_pub:
            from std_msgs.msg import String
            status_msg = String()
            status_msg.data = f"Remote Logger: {len(self.logs)} logs captured, serving on port {self.port}"
            self.status_pub.publish(status_msg)
    
    async def start_server(self):
        """Start the HTTPS server"""
        self.running = True
        self.start_time = time.time()
        
        # Start log capture thread
        self.log_thread = threading.Thread(target=self._capture_ros_logs, daemon=True)
        self.log_thread.start()
        
        # Start HTTPS server
        self.server = await asyncio.start_server(
            self._handle_request,
            '0.0.0.0',
            self.port,
            ssl=self.ssl_context
        )
        
        self.logger.info(f"HTTPS server started on port {self.port}")
        
        # Add some initial logs
        initial_log = LogEntry(
            datetime.now().isoformat(),
            "INFO",
            "remote_logger",
            "Remote Logger started successfully"
        )
        self.logs.append(initial_log)
        
        await self.server.serve_forever()
    
    def stop_server(self):
        """Stop the server"""
        self.running = False
        if self.server:
            self.server.close()
        if self.log_process:
            self.log_process.terminate()


def main():
    """Main function for running the remote logger"""
    if ROS_AVAILABLE:
        rclpy.init()
    
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description='DiceMaster Remote Logger')
    parser.add_argument('--port', type=int, default=8443, help='HTTPS port (default: 8443)')
    parser.add_argument('--max-logs', type=int, default=1000, help='Maximum logs to keep (default: 1000)')
    parser.add_argument('--cert', type=str, help='SSL certificate file path')
    parser.add_argument('--key', type=str, help='SSL private key file path')
    
    args = parser.parse_args()
    
    # Create and run the remote logger
    remote_logger = RemoteLogger(
        port=args.port,
        max_logs=args.max_logs,
        cert_file=args.cert,
        key_file=args.key
    )
    
    try:
        # Run both ROS and asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Start server in background
        server_task = loop.create_task(remote_logger.start_server())
        
        if ROS_AVAILABLE:
            # Run ROS in main thread
            def ros_spin():
                rclpy.spin(remote_logger)
            
            ros_thread = threading.Thread(target=ros_spin, daemon=True)
            ros_thread.start()
        
        # Run asyncio loop
        loop.run_until_complete(server_task)
        
    except KeyboardInterrupt:
        print("Shutting down...")
    finally:
        remote_logger.stop_server()
        remote_logger.destroy_node()
        if ROS_AVAILABLE:
            rclpy.shutdown()


if __name__ == '__main__':
    main()