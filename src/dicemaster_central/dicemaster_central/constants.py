"""
Utility class for constants and macros
"""
from enum import IntEnum, Enum

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

class FontName(Enum):
    """Font names for text entries"""
    NOTEXT = "no_text"
    TF = "tf"
    ARABIC = "arabic"
    CHINESE = "chinese"
    CYRILLIC = "cyrillic"
    DEVANAGARI = "devanagari"

# Font name to ID mapping
FONT_NAME_TO_ID = {
    "no_text": FontID.NOTEXT,
    "tf": FontID.TF,
    "arabic": FontID.ARABIC,
    "chinese": FontID.CHINESE,
    "cyrillic": FontID.CYRILLIC,
    "devanagari": FontID.DEVANAGARI,
}

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

class ErrorCode(IntEnum):
    # General Errors
    SUCCESS = 0x00
    UNKNOWN_MSG_TYPE = 0x01
    INVALID_FORMAT = 0x02
    IMAGE_ID_MISMATCH = 0x04
    PAYLOAD_LENGTH_MISMATCH = 0x05
    UNSUPPORTED_IMAGE_FORMAT = 0x06
    OUT_OF_MEMORY = 0x07
    INTERNAL_ERROR = 0x08
    INVALID_OPTION_INDEX = 0x09
    UNSUPPORTED_MESSAGE = 0x0A
    
    # Header decoding errors
    HEADER_TOO_SHORT = 0x10
    INVALID_SOF_MARKER = 0x11
    INVALID_MESSAGE_TYPE = 0x12
    INVALID_LENGTH_FIELD = 0x13
    HEADER_LENGTH_MISMATCH = 0x14
    
    # TextBatch specific errors
    TEXT_PAYLOAD_TOO_SHORT = 0x20
    TEXT_TOO_MANY_ITEMS = 0x21
    TEXT_INVALID_ROTATION = 0x22
    TEXT_ITEM_HEADER_TOO_SHORT = 0x23
    TEXT_ITEM_LENGTH_MISMATCH = 0x24
    TEXT_PAYLOAD_TRUNCATED = 0x25
    TEXT_LENGTH_CALCULATION_ERROR = 0x26
    
    # ImageStart specific errors
    IMAGE_START_TOO_SHORT = 0x30
    IMAGE_START_INVALID_ROTATION = 0x31
    IMAGE_START_INVALID_FORMAT = 0x32
    IMAGE_START_INVALID_RESOLUTION = 0x33
    
    # ImageChunk specific errors
    IMAGE_CHUNK_TOO_SHORT = 0x40
    IMAGE_CHUNK_DATA_TRUNCATED = 0x41
    IMAGE_CHUNK_INVALID_LENGTH = 0x42
    
    # Ping specific errors
    PING_REQUEST_NOT_EMPTY = 0x80
    PING_RESPONSE_TOO_SHORT = 0x81
    PING_RESPONSE_TEXT_TRUNCATED = 0x82
    
    # Ack/Error specific errors
    ACK_TOO_SHORT = 0x90
    ERROR_TOO_SHORT = 0x91
    ERROR_TEXT_TRUNCATED = 0x92

# Media Types
ContentTypeExts = {
    ContentType.TEXT: ['json'],
    ContentType.IMAGE: ['jpg', 'jpeg'],
    ContentType.GIF: ['gif.d'],
}

README_REGEX_PATTERN = r'^(?i:readme).*'
MAX_TEXT_NUM_BYTES = 255

ImageRes = {
    "full": 480,
    "half": 240,
}

GIF_FRAME_TIME = 1.0/12

class CommandType(IntEnum):
    # Protocols
    PING_CMD = 1
    IMG_CMD = 3
    TXT_CMD = 31
    OPT_CMD = 63
    OPT_END = 64
    RES_CMD = 253
    HYB_CMD = 254