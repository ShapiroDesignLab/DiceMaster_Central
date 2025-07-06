# Notification service response message
# Indicates success or failure of notification display

bool success        # True if notification was successfully queued
string message      # Error message if success is false
int32 request_id    # Unique ID for tracking the notification request
