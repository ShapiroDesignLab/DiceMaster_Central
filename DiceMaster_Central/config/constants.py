"""
Utility class for constants and macros
"""
import shutil
import os
from enum import IntEnum

##########################
# 
# Protocol Configurations
# 
##########################

class MessageType(IntEnum):
    """Message types as defined in protocol"""
    TEXT_BATCH = 0x01
    IMAGE_TRANSFER_START = 0x02
    IMAGE_CHUNK = 0x03
    IMAGE_TRANSFER_END = 0x04
    BACKLIGHT_ON = 0x05
    BACKLIGHT_OFF = 0x06
    PING_REQUEST = 0x07
    PING_RESPONSE = 0x08
    ACKNOWLEDGMENT = 0x09
    ERROR_MESSAGE = 0x0A

# Service message types
class ContentType(IntEnum):
    TEXT = 0
    IMAGE = 1
    GIF = 2
    OPTION = 3

class Rotation(IntEnum):
    """Rotation values for text groups and images"""
    ROTATION_0 = 0
    ROTATION_90 = 1
    ROTATION_180 = 2
    ROTATION_270 = 3

class ImageFormat(IntEnum):
    """Image format values (4-bit)"""
    JPEG = 1
    RGB565 = 2

class ImageResolution(IntEnum):
    """Image resolution values (4-bit)"""
    SQ480 = 1
    SQ240 = 2

class FontID(IntEnum):
    NOTEXT=0
    TF = 1
    ARABIC=2
    CHINESE=3
    CYRILLIC=4
    DEVANAGARI=5

class MessagePriority(IntEnum):
    """Message priority constants"""
    CRITICAL = 1    # Ping, errors
    HIGH = 2        # Text, single images
    NORMAL = 5      # GIF frames
    LOW = 8         # Background tasks

class RequestStatus(IntEnum):
    PENDING = 0
    PROCESSING = 1
    COMPLETED = 2
    FAILED = 3

##########################
# 
# BUS Macros
# 
##########################
NOBUS = False
if shutil.which("raspi-config"):
  NOBUS = True

# Determine number of SPI controllers
NUM_SPI_CTRL = 6 if 'Raspberry Pi 4' in open('/proc/device-tree/model').read() \
                  else (2 if 'Raspberry Pi 3' in open('/proc/device-tree/model').read() \
                  else 0)
NUM_DEV_PER_SPI_CTRL = 2

IMU_POLLING_RATE = 200
IMU_HIST_SIZE = IMU_POLLING_RATE

##########################
# File System Configs
##########################

# Configure SD card path
if NOBUS:
    SD_ROOT_PATH = os.path.join(os.path.expanduser("~"), ".dicedata")
else:
    SD_ROOT_PATH = "/media/pi"  # Default SD card mount point on Raspberry Pi
if not os.path.isdir(SD_ROOT_PATH): os.makedirs(SD_ROOT_PATH)

# Configure cache path
CACHE_PATH = os.path.join(os.path.expanduser("~"), ".dicemaster/cache")
if not os.path.isdir(CACHE_PATH):
    os.makedirs(CACHE_PATH)

# Dataset management constants
DATASETS_PATH = os.path.join(SD_ROOT_PATH, "datasets")
DATASET_CACHE_PATH = os.path.join(CACHE_PATH, "datasets")
DATASET_METADATA_PATH = os.path.join(CACHE_PATH, "dataset_metadata.json")
DYNAMIC_LOADING = True

# Cache size limits (in bytes)
CACHE_SIZE_LIMIT = 1024 * 1024 * 1024  # 1GB
CACHE_SIZE_TARGET = 300 * 1024 * 1024   # 300MB

# Configure DB Path
# Path should have been created from previous step
DB_PATH = os.path.join(os.path.expanduser("~"), ".dicemaster/fdb.sqlite")


##########################
# 
# Screen Configs
# 
##########################
NUM_SCREEN = 6

USING_ORIENTED_SCREENS = False

SCREEN_WIDTH = 480
SCREEN_BOOT_DELAY = 3
SCREEN_PING_INTERNVAL = 10

# Media Types
ContentTypeExts = {
    ContentType.TEXT: ['txt', 'md', 'rtf'],
    ContentType.IMAGE: ['jpg', 'png', 'jpeg', 'bmp', 'heic', 'heif'],
    ContentType.GIF: [''],
}
README_REGEX_PATTERN = r'^(?i:readme).*'

# Image Metadata
IMG_WIDTH_FULL = 480
IMG_HEIGHT_FULL = 480
IMG_WIDTH_HALF = 240
IMG_HEIGHT_HALF = 240

GIF_FRAME_TIME = 1.0/12

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
SPI_CHUNK_SIZE = 1024       # Maimum 1016 bytes (excluding 8 byte header for image)
PING_INTERVAL = 5       # Interval for pinging screens, in seconds, default every 5 seconds
WORK_SLEEP_TIME = 0.002  # 500Hz update frequency when running
HYB_SLEEP_TIME = 0.2    # 5 Hz update frequency when in hybernation

class CommandType(IntEnum):
    # Protocols
    PING_CMD = 1
    IMG_CMD = 3
    TXT_CMD = 31
    OPT_CMD = 63
    OPT_END = 64
    RES_CMD = 253
    HYB_CMD = 254

COLOR_BABY_BLUE = (137, 207, 240)
