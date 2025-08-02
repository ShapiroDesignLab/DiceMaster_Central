# Notification service request message
# Used to send notifications to screens with different logging levels

# Target screen ID
int32 screen_id

# Notification level
string level    # "info" or "error"

# Notification content
string content  # The actual notification text to display

# Optional parameters
float64 duration    # Display duration in seconds (default: 5.0)
