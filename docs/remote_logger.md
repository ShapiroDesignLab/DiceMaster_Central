# DiceMaster Remote Logger

The Remote Logger is a feature that captures ROS logs and serves them via an HTTPS web interface, allowing you to view logs remotely from any web browser.

## Features

- 🌐 **Web-based Interface**: Access logs from any device with a web browser
- 🔒 **HTTPS Security**: Secure connection with SSL/TLS encryption
- 📊 **Real-time Updates**: Auto-refresh logs in real-time
- 🔍 **Filtering**: Filter logs by level (INFO, WARN, ERROR, DEBUG) and source
- 📱 **Responsive Design**: Works on desktop and mobile devices
- 🚀 **Self-contained**: No external dependencies required
- 🔐 **Self-signed Certificates**: Automatically generates SSL certificates

## Quick Start

### 1. Launch with Main DiceMaster System

The remote logger is included in the main launch file and enabled by default:

```bash
# Launch with remote logger (default port 8443)
ros2 launch dicemaster_central launch_dice.py

# Launch with custom port
ros2 launch dicemaster_central launch_dice.py remote_logger_port:=9443

# Launch without remote logger
ros2 launch dicemaster_central launch_dice.py enable_remote_logger:=false
```

### 2. Launch Remote Logger Standalone

```bash
# Launch only the remote logger
ros2 launch dicemaster_central launch_remote_logger.py

# With custom settings
ros2 launch dicemaster_central launch_remote_logger.py port:=9443 max_logs:=2000
```

### 3. Run Remote Logger Directly

```bash
# Run the remote logger node directly
ros2 run dicemaster_central remote_logger --port 8443 --max-logs 1000

# With custom SSL certificates
ros2 run dicemaster_central remote_logger --cert /path/to/cert.pem --key /path/to/key.pem
```

### 4. Test Without ROS

```bash
# Test the web interface without ROS (for development)
cd /home/dice/DiceMaster/DiceMaster_Central
python3 scripts/test_remote_logger.py
```

## Accessing the Web Interface

1. **Find your device IP address**:
   ```bash
   ip addr show | grep "inet " | grep -v 127.0.0.1
   ```

2. **Open in web browser**:
   - Local access: `https://localhost:8443`
   - Remote access: `https://YOUR_DEVICE_IP:8443`

3. **Accept security warning**: Since we use self-signed certificates, your browser will show a security warning. Click "Advanced" and "Proceed to localhost" (this is safe for local development).

## Web Interface Features

### Main Dashboard
- **Status Bar**: Shows current logger status and log count
- **Filter Controls**: 
  - Level filter: Filter by log level (ERROR, WARN, INFO, DEBUG)
  - Source filter: Filter by ROS node name
  - Refresh button: Manually refresh logs
  - Clear button: Clear all logs (not implemented yet)
  - Auto-refresh toggle: Enable/disable automatic log updates

### Log Display
- **Color-coded levels**: Different colors for each log level
- **Timestamps**: ISO format timestamps for each log entry
- **Source identification**: Shows which ROS node generated the log
- **Auto-scroll**: Automatically scrolls to newest logs
- **Responsive design**: Works on mobile devices

## API Endpoints

The remote logger provides a simple REST API:

- `GET /` - Main web interface
- `GET /api/logs` - JSON API for logs
  - Query parameters:
    - `level`: Filter by log level (ERROR, WARN, INFO, DEBUG)
    - `source`: Filter by source node name
- `GET /api/status` - JSON API for status information

### Example API Usage

```bash
# Get all logs
curl -k https://localhost:8443/api/logs

# Get only error logs
curl -k https://localhost:8443/api/logs?level=ERROR

# Get logs from specific source
curl -k https://localhost:8443/api/logs?source=imu_node

# Get status
curl -k https://localhost:8443/api/status
```

## Configuration

### Launch Parameters

- `port`: HTTPS port (default: 8443)
- `max_logs`: Maximum logs to keep in memory (default: 1000)
- `cert_file`: Custom SSL certificate file path (optional)
- `key_file`: Custom SSL private key file path (optional)
- `enable_remote_logger`: Enable/disable remote logger (default: true)

### SSL Certificates

The remote logger automatically generates self-signed certificates if none are provided:
- Certificate location: `~/.dicemaster/certs/`
- Certificate file: `server.crt`
- Private key file: `server.key`

To use custom certificates:
```bash
ros2 launch dicemaster_central launch_remote_logger.py \
  cert_file:=/path/to/your/cert.pem \
  key_file:=/path/to/your/key.pem
```

## Security Considerations

- The web interface uses HTTPS with SSL/TLS encryption
- Self-signed certificates are generated automatically for development
- For production use, consider using proper CA-signed certificates
- The server binds to all interfaces (0.0.0.0) for remote access
- No authentication is currently implemented (suitable for trusted networks)

## Troubleshooting

### Common Issues

1. **Port already in use**:
   ```bash
   # Check what's using the port
   sudo netstat -tulpn | grep :8443
   
   # Use a different port
   ros2 launch dicemaster_central launch_remote_logger.py port:=9443
   ```

2. **SSL certificate errors**:
   ```bash
   # Install OpenSSL if missing
   sudo apt install openssl
   
   # Remove old certificates to regenerate
   rm -rf ~/.dicemaster/certs/
   ```

3. **Browser security warnings**:
   - This is normal with self-signed certificates
   - Click "Advanced" → "Proceed to localhost"
   - For permanent solution, add certificate to browser trust store

4. **No logs appearing**:
   - Check if ROS nodes are running: `ros2 node list`
   - Check if rosout topic has messages: `ros2 topic echo /rosout`
   - Verify remote logger is receiving logs: Check terminal output

### Logs and Debugging

The remote logger outputs its own logs to the console. Look for:
- "Remote Logger initialized on port X"
- "HTTPS server started on port X"
- "Started ROS log capture"

## Development

### Adding Features

The remote logger is designed to be extensible:

1. **Custom log parsing**: Modify `_parse_and_store_log()` method
2. **Additional API endpoints**: Add handlers in `_handle_request()` method
3. **Enhanced web interface**: Modify the HTML template in `_generate_main_page()`
4. **Custom storage**: Replace the in-memory deque with database storage

### Testing

```bash
# Run unit tests (if available)
python3 -m pytest tests/

# Test web interface without ROS
python3 scripts/test_remote_logger.py

# Test with curl
curl -k https://localhost:8443/api/status
```

## License

This feature is part of the DiceMaster project and follows the same MIT license.
