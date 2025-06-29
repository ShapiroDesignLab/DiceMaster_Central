"""
Protocol implementation for DiceMaster SPI communication
Based on the protocol specification in docs/protocol.md
"""

import struct
from typing import List, Tuple, Optional
from enum import IntEnum


class MessageType(IntEnum):
    """Message types as defined in protocol"""
    TEXT_BATCH = 0x01
    IMAGE_TRANSFER_START = 0x02
    IMAGE_CHUNK = 0x03
    IMAGE_TRANSFER_END = 0x04
    OPTION_LIST = 0x05
    OPTION_SELECTION_UPDATE = 0x06
    GIF_TRANSFER_START = 0x07
    GIF_FRAME = 0x08
    GIF_TRANSFER_END = 0x09
    BACKLIGHT_CONTROL = 0x0A
    ACKNOWLEDGMENT = 0x0B
    ERROR_MESSAGE = 0x0C


class ImageFormat(IntEnum):
    """Image format types"""
    JPEG = 0x0
    PNG = 0x1
    BMP = 0x2
    RAW = 0x3


class ImageResolution(IntEnum):
    """Image resolution types"""
    RES_240x240 = 0x0
    RES_480x480 = 0x1


class Rotation(IntEnum):
    """Rotation values for images and text"""
    ROTATION_0 = 0x0
    ROTATION_90 = 0x1
    ROTATION_180 = 0x2
    ROTATION_270 = 0x3


class ProtocolMessage:
    """Base class for protocol messages"""
    SOF = 0x7E  # Start of Frame
    
    def __init__(self, msg_type: MessageType, msg_id: int = 0):
        self.msg_type = msg_type
        self.msg_id = msg_id
        self.payload = bytearray()
    
    def build_header(self) -> bytearray:
        """Build the 6-byte message header"""
        header = bytearray()
        header.append(self.SOF)  # BYTE 0: Start of Frame
        header.append(self.msg_type)  # BYTE 1: Message Type
        header.append(self.msg_id)  # BYTE 2: Message ID
        
        # BYTE 3-4: Payload length (BIG_ENDIAN)
        payload_len = len(self.payload)
        header.append((payload_len >> 8) & 0xFF)  # High byte
        header.append(payload_len & 0xFF)  # Low byte
        
        return header
    
    def build_message(self) -> bytearray:
        """Build complete message with header and payload"""
        message = self.build_header()
        message.extend(self.payload)
        return message


class TextMessage(ProtocolMessage):
    """Text batch message with rotation support"""
    
    def __init__(self, msg_id: int = 0):
        super().__init__(MessageType.TEXT_BATCH, msg_id)
    
    def add_text_group(self, bg_color: int, font_color: int, texts: List[Tuple[int, int, int, str]], rotation: Rotation = Rotation.ROTATION_0):
        """
        Add a text group with rotation support
        
        Args:
            bg_color: Background color (16-bit)
            font_color: Font color (16-bit)
            texts: List of (x_cursor, y_cursor, font_id, text_string) tuples
            rotation: Rotation value for the text group
        """
        # Text Group header
        self.payload.extend(struct.pack('>H', bg_color))  # BYTE 0-1: BG Color
        self.payload.extend(struct.pack('>H', font_color))  # BYTE 2-3: Font Color
        self.payload.append(len(texts))  # BYTE 4: number of lines
        self.payload.append(rotation)  # BYTE 5: rotation (NEW)
        
        # Individual text chunks
        for x_cursor, y_cursor, font_id, text_string in texts:
            text_bytes = text_string.encode('utf-8')
            if len(text_bytes) > 255:
                raise ValueError("Text string too long (max 255 bytes)")
            
            self.payload.extend(struct.pack('>H', x_cursor))  # BYTE 0-1: x cursor
            self.payload.extend(struct.pack('>H', y_cursor))  # BYTE 2-3: y cursor
            self.payload.append(font_id)  # BYTE 4: font id
            self.payload.append(len(text_bytes))  # BYTE 5: text length
            self.payload.extend(text_bytes)  # PAYLOAD STRING


class ImageStartMessage(ProtocolMessage):
    """Image transfer start message with rotation support"""
    
    def __init__(self, image_id: int, image_format: ImageFormat, resolution: ImageResolution, 
                 delay_time: int, total_size: int, num_chunks: int, rotation: Rotation = Rotation.ROTATION_0, msg_id: int = 0):
        super().__init__(MessageType.IMAGE_TRANSFER_START, msg_id)
        
        self.payload.append(image_id)  # BYTE 0: image ID
        
        # BYTE 1: 4-bit Format, 4-bit Resolution
        format_res_byte = (image_format << 4) | resolution
        self.payload.append(format_res_byte)
        
        self.payload.append(delay_time)  # BYTE 2: Delay Time (0-255 ms)
        
        # BYTE 3-5: total image size (24-bit big endian)
        self.payload.append((total_size >> 16) & 0xFF)
        self.payload.append((total_size >> 8) & 0xFF)
        self.payload.append(total_size & 0xFF)
        
        self.payload.append(num_chunks)  # BYTE 6: num chunks
        self.payload.append(rotation)  # BYTE 7: rotation (NEW)


class ImageChunkMessage(ProtocolMessage):
    """Image chunk message"""
    
    def __init__(self, image_id: int, chunk_id: int, start_location: int, chunk_data: bytes, msg_id: int = 0):
        super().__init__(MessageType.IMAGE_CHUNK, msg_id)
        
        if len(chunk_data) > 65535:
            raise ValueError("Chunk data too large (max 65535 bytes)")
        
        self.payload.append(image_id)  # BYTE 0: image ID
        self.payload.append(chunk_id)  # BYTE 1: chunk ID
        
        # BYTE 2-4: starting location (24-bit big endian)
        self.payload.append((start_location >> 16) & 0xFF)
        self.payload.append((start_location >> 8) & 0xFF)
        self.payload.append(start_location & 0xFF)
        
        # BYTE 5-6: length of chunk
        chunk_len = len(chunk_data)
        self.payload.extend(struct.pack('>H', chunk_len))
        
        # PAYLOAD: chunk data
        self.payload.extend(chunk_data)


class ImageEndMessage(ProtocolMessage):
    """Image transfer end message"""
    
    def __init__(self, image_id: int, msg_id: int = 0):
        super().__init__(MessageType.IMAGE_TRANSFER_END, msg_id)
        self.payload.append(image_id)  # BYTE 0: Image ID


class GIFStartMessage(ProtocolMessage):
    """GIF transfer start message with rotation support"""
    
    def __init__(self, image_id: int, image_format: ImageFormat, resolution: ImageResolution,
                 delay_time: int, total_size: int, num_chunks: int, rotation: Rotation = Rotation.ROTATION_0, msg_id: int = 0):
        super().__init__(MessageType.GIF_TRANSFER_START, msg_id)
        
        self.payload.append(image_id)  # BYTE 0: image ID
        
        # BYTE 1: 4-bit Format, 4-bit Resolution
        format_res_byte = (image_format << 4) | resolution
        self.payload.append(format_res_byte)
        
        self.payload.append(delay_time)  # BYTE 2: Delay Time (0-255 ms)
        
        # BYTE 3-5: total image size (24-bit big endian)
        self.payload.append((total_size >> 16) & 0xFF)
        self.payload.append((total_size >> 8) & 0xFF)
        self.payload.append(total_size & 0xFF)
        
        self.payload.append(num_chunks)  # BYTE 6: num chunks
        self.payload.append(rotation)  # BYTE 7: rotation (NEW)


class GIFFrameMessage(ProtocolMessage):
    """GIF frame message"""
    
    def __init__(self, image_id: int, chunk_id: int, start_location: int, chunk_data: bytes, msg_id: int = 0):
        super().__init__(MessageType.GIF_FRAME, msg_id)
        
        if len(chunk_data) > 65535:
            raise ValueError("Chunk data too large (max 65535 bytes)")
        
        self.payload.append(image_id)  # BYTE 0: image ID
        self.payload.append(chunk_id)  # BYTE 1: chunk ID
        
        # BYTE 2-5: starting location (32-bit big endian)
        self.payload.extend(struct.pack('>I', start_location))
        
        # BYTE 6-7: length of chunk
        chunk_len = len(chunk_data)
        self.payload.extend(struct.pack('>H', chunk_len))
        
        # PAYLOAD: chunk data
        self.payload.extend(chunk_data)


class GIFEndMessage(ProtocolMessage):
    """GIF transfer end message"""
    
    def __init__(self, image_id: int, msg_id: int = 0):
        super().__init__(MessageType.GIF_TRANSFER_END, msg_id)
        self.payload.append(image_id)  # BYTE 0: Image ID


class BacklightMessage(ProtocolMessage):
    """Backlight control message"""
    
    def __init__(self, brightness: int, msg_id: int = 0):
        super().__init__(MessageType.BACKLIGHT_CONTROL, msg_id)
        self.payload.append(brightness)  # BYTE 0: brightness (0-255)


class AckMessage(ProtocolMessage):
    """Acknowledgment message"""
    
    def __init__(self, ack_msg_id: int, msg_id: int = 0):
        super().__init__(MessageType.ACKNOWLEDGMENT, msg_id)
        self.payload.append(ack_msg_id)  # BYTE 0: Message ID being acknowledged


class ErrorMessage(ProtocolMessage):
    """Error message (NACK)"""
    
    def __init__(self, error_msg_id: int, error_code: int, msg_id: int = 0):
        super().__init__(MessageType.ERROR_MESSAGE, msg_id)
        self.payload.append(error_msg_id)  # BYTE 0: Message ID that caused error
        self.payload.append(error_code)  # BYTE 1: Error code


def split_image_into_chunks(image_data: bytes, max_chunk_size: int = 2040) -> List[Tuple[int, int, bytes]]:
    """
    Split image data into chunks for transmission
    
    Args:
        image_data: Complete image data
        max_chunk_size: Maximum size per chunk (default 2040 to leave room for headers)
    
    Returns:
        List of (chunk_id, start_location, chunk_data) tuples
    """
    chunks = []
    chunk_id = 0
    start_location = 0
    
    while start_location < len(image_data):
        end_location = min(start_location + max_chunk_size, len(image_data))
        chunk_data = image_data[start_location:end_location]
        chunks.append((chunk_id, start_location, chunk_data))
        
        chunk_id += 1
        start_location = end_location
    
    return chunks
