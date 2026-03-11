# ChassisOrientation message
# Published by chassis node to indicate which screens are facing up/down

# Screen ID of the screen currently facing up (1-6)
uint8 top_screen_id

# Screen ID of the screen currently facing down (1-6)  
uint8 bottom_screen_id

# Timestamp of the orientation detection
builtin_interfaces/Time stamp
