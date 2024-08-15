"""
Utility class for constants and macros
"""
import shutil 
NOBUS = shutil.which("raspi-config")

# Screen Config
SCREEN_WIDTH = 480
SCREEN_BOOT_DELAY = 3
SCREEN_PING_INTERNVAL = 10

# Media Types
TYPE_TXT = 1
TYPE_IMG = 2
TYPE_VID = 3
TYPE_UNKNOWN = 0

TXT_EXTS = ['txt', 'md', 'rtf']
IMG_EXTS = ['jpg', 'png', 'jpeg', 'bmp', 'heic', 'heif']
VID_EXTS = ['mpeg', 'mp4', 'mov', 'avi']


# Image Metadata
IMG_WIDTH_FULL = 480
IMG_HEIGHT_FULL = 480
IMG_WIDTH_HALF = 240
IMG_HEIGHT_HALF = 240
IMG_RES_240SQ = 1
IMG_RES_480SQ = 0

# Draw Text Options
ALIGN_LEFT = 0
ALIGN_RIGHT = 1
ALIGN_TOP = 2
ALIGN_BOTTOM = 3
ALIGN_CENTER = 4

TEXT_WIDTH = 12
TEXT_HEIGHT = 16
TEXT_PADDING = 4

MAX_TEXT_LEN = 256
FONT_SIZE = 10

# Error Codes
ERR_NOT_LOADED = -1

# SPI Configuration
BYTE_SIZE = 2**8
# DUMMY_BUFFER_SIZE = 4
# TOTAL_SPI_SEND_SIZE = 1024 + DUMMY_BUFFER_SIZE
CHUNK_SIZE = 1020       # Maimum 1016 bytes (excluding 8 byte header for image)
PING_INTERVAL = 5       # Interval for pinging screens, in seconds, default every 5 seconds
WORK_SLEEP_TIME = 0.002  # 500Hz update frequency when running
HYB_SLEEP_TIME = 0.2    # 5 Hz update frequency when in hybernation

# Protocols
PING_CMD = 1
IMG_CMD = 3
TXT_CMD = 31
OPT_CMD = 63
OPT_END = 64
RES_CMD = 253
HYB_CMD = 254

COLOR_BABY_BLUE = (137, 207, 240)