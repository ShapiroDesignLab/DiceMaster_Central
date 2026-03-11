# ScreenPose message
# Published by chassis node to individual screens with their rotation state

# Screen ID (1-6)
uint8 screen_id

# Rotation value (0=0°, 1=90°, 2=180°, 3=270°)
# Based on gravity direction and screen's default orientation
uint8 rotation

# Alignment with "up" direction (-1.0 to 1.0)
# 1.0 = perfectly facing up, -1.0 = perfectly facing down
float32 up_alignment

# Whether this screen is currently the primary "up" facing screen
bool is_facing_up

# Timestamp of the pose calculation
builtin_interfaces/Time stamp
