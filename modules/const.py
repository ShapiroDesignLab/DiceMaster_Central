"""
Utility class for constants and macros
"""
import shutil
import os

NUM_SCREEN = 1
NOBUS = True
if shutil.which("raspi-config"):
  NOBUS = False

# Determine number of SPI controllers
NUM_SPI_CTRL = 6 if 'Raspberry Pi 4' in open('/proc/device-tree/model').read() \
                  else (2 if 'Raspberry Pi 3' in open('/proc/device-tree/model').read() \
                  else 0)
NUM_DEV_PER_SPI_CTRL = 2

# Configure SD card path
SD_ROOT_PATH = f"/media/{os.path.basename(os.path.expanduser("~"))}/"
if NOBUS:
    SD_ROOT_PATH = os.path.join(os.path.expanduser("~"), ".dicedata")
if not os.path.isdir(SD_ROOT_PATH): os.makedirs(SD_ROOT_PATH)

# Configure cache path
CACHE_PATH = os.path.join(os.path.expanduser("~"), ".dicemaster/cache")
if not os.path.isdir(CACHE_PATH):
    os.makedirs(CACHE_PATH)

# Configure DB Path
# Path should have been created from previous step
DB_PATH = os.path.join(os.path.expanduser("~"), ".dicemaster/fdb.sqlite")


# Screen Config
SCREEN_WIDTH = 480
SCREEN_BOOT_DELAY = 3
SCREEN_PING_INTERNVAL = 10

# FS Config
DYNAMIC_LOADING = True

# Media Types
TYPE_TXT = 1
TYPE_IMG = 2
TYPE_VID = 3
TYPE_UNKNOWN = 0

TXT_EXTS = ['txt', 'md', 'rtf']
IMG_EXTS = ['jpg', 'png', 'jpeg', 'bmp', 'heic', 'heif']
VID_EXTS = ['mpeg']

README_REGEX_PATTERN = r'^(?i:readme).*'

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