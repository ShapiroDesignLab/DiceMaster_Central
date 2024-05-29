"""
Utility class for constants and macros
"""

TYPE_TXT = 1
TYPE_IMG = 2
TYPE_VID = 3
TYPE_UNKNOWN = 0

TXT_EXTS = ['txt', 'md', 'rtf']
IMG_EXTS = ['jpg', 'png', 'jpeg', 'bmp', 'heic', 'heif']
VID_EXTS = ['mpeg', 'mp4', 'mov', 'avi']

IMG_WIDTH_FULL = 480
IMG_HEIGHT_FULL = 480
IMG_WIDTH_HALF = 240
IMG_HEIGHT_HALF = 240

ERR_NOT_LOADED = -1


# Macros for Communication
# Image Macros
IMG_RES_240SQ = 1
IMG_RES_480SQ = 0

# SPI Configuration
BYTE_SIZE = 2**8
DUMMY_BUFFER_SIZE = 4
TOTAL_SPI_SEND_SIZE = 1024 + DUMMY_BUFFER_SIZE
CHUNK_SIZE = 1016       # Maimum 1016 bytes (excluding 8 byte header for image)
PING_INTERVAL = 5       # Interval for pinging screens, in seconds, default every 5 seconds
RECV_BYTES = 32         # Return messages are 32 bytes long.
WORK_SLEEP_TIME = 0.002  # 500Hz update frequency when running
HYB_SLEEP_TIME = 0.2    # 5 Hz update frequency when in hybernation

# Protocl Macros
PING_CMD = 1
IMG_CMD = 3
TXT_CMD = 7
OPT_CMD = 15
RES_CMD = 254
HYB_CMD = 255

ZERO_MSG = [0] * TOTAL_SPI_SEND_SIZE