"""
Protocol implementation for DiceMaster SPI communication
Based on the protocol specification in docs/protocol.md
"""

import struct
from typing import Tuple, TYPE_CHECKING

from abc import ABC, abstractmethod
from dicemaster_central.constants import (
    MessageType,
    Rotation,
    ImageFormat,
    ImageResolution,
    ErrorCode
)

from dicemaster_central.config import dice_config
spi_config = dice_config.spi_config

# Forward reference for type checking
if TYPE_CHECKING:
    from dicemaster_central.media_typing.media_types import TextEntry

# Private constants for this module
_SOF = 0x7E  # Start of Frame
_SOF_RESPONSE = 0x7F  # Start of Frame for responses
_HEADER_SIZE = 5  # Header is 5 bytes (SOF + Type + ID + Length)
_DMA_PADDING = 4  # DMA buffer padding bytes
_DMA_ALIGNMENT = 4  # DMA buffer alignment requirement (multiples of 4)

def encode_text_entry(text_entry: 'TextEntry') -> bytes:
    """Encode a TextEntry object to bytes for protocol transmission"""
    encoded = bytearray()
    
    # Encode coordinates (2 bytes each)
    encoded.extend(struct.pack('>H', text_entry.x_cursor))
    encoded.extend(struct.pack('>H', text_entry.y_cursor))
    
    # Encode font_id (1 byte)
    encoded.append(text_entry.font_id)
    
    # Encode font_color (2 bytes)
    encoded.extend(struct.pack('>H', text_entry.font_color))
    
    # Encode text length and content
    text_bytes = text_entry.text.encode('utf-8')
    if len(text_bytes) > 255:
        raise ValueError(f"Text too long: {len(text_bytes)} bytes (max 255)")
    
    encoded.append(len(text_bytes))
    encoded.extend(text_bytes)
    
    return bytes(encoded)


def calculate_effective_chunk_size(spi_chunk_size: int) -> int:
    """
    Calculate the effective chunk size for image data considering SPI DMA restrictions.
    
    Args:
        spi_chunk_size: The configured SPI chunk size (e.g., 8192 bytes)
        
    Returns:
        The effective chunk size for image data payload
        
    The total message structure is:
    - Header: 5 bytes (SOF + Type + ID + Length)
    - Image chunk payload header: 7 bytes (image_id + chunk_id + start_location + chunk_len)
    - Image data: variable
    - DMA padding: 4 bytes
    
    For ImageStart messages with embedded chunk 0:
    - Header: 5 bytes
    - ImageStart header: 9 bytes (image_id + format/res + delay + size + chunks + rotation)
    - Embedded chunk 0 data: variable
    - DMA padding: 4 bytes
    
    Total message must be aligned to 4 bytes for DMA compatibility.
    """
    # Calculate overhead: header + chunk payload header + DMA padding
    overhead = _HEADER_SIZE + 7 + _DMA_PADDING  # 5 + 7 + 4 = 16 bytes
    
    # Ensure the total message length is aligned to 4 bytes
    # Since overhead is already 16 bytes (multiple of 4), we need to ensure
    # the image data size keeps the total aligned
    effective_chunk_size = ((spi_chunk_size - overhead) // _DMA_ALIGNMENT) * _DMA_ALIGNMENT
    
    # Ensure we have at least some space for data
    if effective_chunk_size <= 0:
        raise ValueError(f"SPI chunk size ({spi_chunk_size}) too small for headers and alignment")
    
    return effective_chunk_size


def calculate_effective_chunk_size_for_image_start(spi_chunk_size: int) -> int:
    """
    Calculate the effective chunk size for embedded chunk 0 in ImageStart messages.
    
    Args:
        spi_chunk_size: The configured SPI chunk size (e.g., 8192 bytes)
        
    Returns:
        The effective chunk size for embedded chunk 0 data in ImageStart message
    """
    # Calculate overhead: header + ImageStart header + DMA padding
    overhead = _HEADER_SIZE + 9 + _DMA_PADDING  # 5 + 9 + 4 = 18 bytes
    
    # Ensure the total message length is aligned to 4 bytes
    # Since overhead is 18 bytes, we need 2 bytes padding to align to 4 bytes
    # Then ensure the chunk data size keeps the total aligned
    aligned_overhead = ((overhead + _DMA_ALIGNMENT - 1) // _DMA_ALIGNMENT) * _DMA_ALIGNMENT
    effective_chunk_size = ((spi_chunk_size - aligned_overhead) // _DMA_ALIGNMENT) * _DMA_ALIGNMENT
    
    # Ensure we have at least some space for data
    if effective_chunk_size <= 0:
        raise ValueError(f"SPI chunk size ({spi_chunk_size}) too small for ImageStart headers and alignment")
    
    return effective_chunk_size


def pad_to_alignment(data: bytearray, alignment: int = _DMA_ALIGNMENT) -> bytearray:
    """Pad data to the specified alignment boundary"""
    padding_needed = (alignment - (len(data) % alignment)) % alignment
    if padding_needed > 0:
        data.extend(b'\x00' * padding_needed)
    return data


def create_ack_response(msg_id: int) -> 'ScreenResponse':
    """Create an acknowledgment response using ScreenResponse format"""
    return ScreenResponse(status_code=ErrorCode.SUCCESS, msg_id=msg_id)


def create_error_response(msg_id: int, error_code: ErrorCode) -> 'ScreenResponse':
    """Create an error response using ScreenResponse format"""
    return ScreenResponse(status_code=error_code, msg_id=msg_id)


class ProtocolMessage(ABC):
    """Base class for all protocol messages"""
    
    def __init__(self, msg_type: MessageType, msg_id: int = 0):
        self.msg_type = msg_type
        self.msg_id = msg_id
        self.payload = bytearray()
    
    def _encode_header(self, payload) -> None:
        """Build complete message with header and payload"""
        message = bytearray()
        message.append(_SOF)  # BYTE 0: Start of Frame
        message.append(self.msg_type)  # BYTE 1: Message Type
        message.append(self.msg_id)  # BYTE 2: Message ID
        
        # BYTE 3-4: Payload length (BIG_ENDIAN)
        payload_len = len(payload)
        message.append((payload_len >> 8) & 0xFF)  # High byte
        message.append(payload_len & 0xFF)  # Low byte
        
        # Payload starts at BYTE 5 onwards
        message.extend(payload)
        
        # Pad to DMA alignment before adding DMA padding
        pad_to_alignment(message, _DMA_ALIGNMENT)
        
        # Finally, add 4 bytes at the end to deal with DMA buffer error
        message.extend(b'\x00\x00\x00\x00')
        self.payload = message  # Store complete message in payload

    @abstractmethod
    def _encode_payload(self) -> bytearray:
        """Encode the payload and return a bytearray"""
        return bytearray()

    def encode(self) -> None:
        """Encode the message with header and payload"""
        payload = self._encode_payload()
        self._encode_header(payload)

    @classmethod
    def decode_header(cls, data: bytearray) -> Tuple[int, int, int, int]:
        """Decode message header and return (msg_type, msg_id, payload_len, payload_start)"""
        if len(data) < _HEADER_SIZE:
            raise ValueError("Insufficient data for header")
        if data[0] != _SOF:
            raise ValueError(f"Invalid SOF: expected {_SOF:02x}, got {data[0]:02x}")
        msg_type = data[1]
        msg_id = data[2]
        payload_len = (data[3] << 8) | data[4]
        
        return msg_type, msg_id, payload_len, _HEADER_SIZE
    
    @classmethod
    @abstractmethod
    def _decode_payload(cls, payload: bytearray) -> 'ProtocolMessage':
        """Decode the payload and return a new message instance"""
        raise NotImplementedError("Subclasses must implement _decode_payload")

    @classmethod
    def decode(cls, payload: bytearray) -> 'ProtocolMessage':
        """Decode API"""
        if len(payload) < _HEADER_SIZE:
            raise ValueError("Insufficient payload for decoding")
        
        # Extract header information
        _, msg_id, _, _ = cls.decode_header(payload)
        # Extract content payload
        content_payload = payload[_HEADER_SIZE:]
        # Create instance using class method
        instance = cls._decode_payload(content_payload)
        # Set the correct message ID from the header
        instance.msg_id = msg_id
        # Re-encode with the correct message ID
        instance.encode()
        return instance

    def __eq__(self, other):
        """Check equality based on message type and ID"""
        if not isinstance(other, ProtocolMessage):
            return False
        return (self.msg_type == other.msg_type and
                self.payload == other.payload)

class TextBatchMessage(ProtocolMessage):
    """Text batch message with rotation support and per-line font colors"""
    
    def __init__(self, bg_color: int = 0, 
                 texts = None,  # Can be TextEntry objects or tuples
                 rotation: Rotation = Rotation.ROTATION_0, msg_id: int = 0):
        super().__init__(MessageType.TEXT_BATCH, msg_id)
        self.bg_color = bg_color
        self.rotation = rotation
        
        # Handle both TextEntry objects and tuples for backward compatibility
        if texts and hasattr(texts[0], 'to_tuple'):
            # TextEntry objects - keep reference for direct encoding
            self._text_entries = texts
            self.texts = [entry.to_tuple() for entry in texts]  # For compatibility
        else:
            # Legacy tuple format
            self._text_entries = None
            self.texts = texts or []  # Format: (x, y, font_id, font_color, text)
        
        self.encode()
    
    def _encode_payload(self):
        """Encode the text batch payload with per-line font colors"""
        payload = bytearray()
        
        # Text Group header
        payload.extend(struct.pack('>H', self.bg_color))  # BYTE 0-1: BG Color
        # Skip BYTE 2-3 as they're no longer used for global font color
        payload.append(0)  # BYTE 2: Reserved
        payload.append(0)  # BYTE 3: Reserved
        payload.append(len(self.texts))  # BYTE 4: number of lines
        payload.append(self.rotation)  # BYTE 5: rotation
        
        # Use TextEntry encoding if available, otherwise use tuple encoding
        if self._text_entries:
            for entry in self._text_entries:
                payload.extend(encode_text_entry(entry))
        else:
            # Legacy tuple encoding
            for x_cursor, y_cursor, font_id, font_color, text_string in self.texts:
                text_bytes = text_string.encode('utf-8')
                if len(text_bytes) > 255:
                    raise ValueError(f"Text string too long (max 255 bytes): '{text_string[:50]}...'")
                
                # BYTE 0-1: x cursor (16-bit big endian)
                payload.extend(struct.pack('>H', x_cursor))
                # BYTE 2-3: y cursor (16-bit big endian)  
                payload.extend(struct.pack('>H', y_cursor))
                # BYTE 4: font id
                payload.append(font_id)
                # BYTE 5-6: font color (16-bit big endian)
                payload.extend(struct.pack('>H', font_color))
                # BYTE 7: text length
                payload.append(len(text_bytes))
                # PAYLOAD STRING
                payload.extend(text_bytes)
            
        return payload
    
    @classmethod
    def _decode_payload(cls, payload: bytearray) -> "TextBatchMessage":
        """Decode the text batch payload with per-line font colors"""
        if len(payload) < 6:
            raise ValueError("Payload too short for text batch message")
        
        # Parse header
        bg_color = struct.unpack('>H', payload[0:2])[0]
        # Skip bytes 2-3 (reserved)
        num_lines = payload[4]
        rotation = Rotation(payload[5])
        
        # Parse individual text chunks
        texts = []
        offset = 6
        
        for _ in range(num_lines):
            if offset + 8 > len(payload):
                raise ValueError("Payload too short for text chunk header")
            
            # Parse text chunk header
            x_cursor = struct.unpack('>H', payload[offset:offset+2])[0]
            y_cursor = struct.unpack('>H', payload[offset+2:offset+4])[0]
            font_id = payload[offset+4]
            font_color = struct.unpack('>H', payload[offset+5:offset+7])[0]
            text_length = payload[offset+7]
            
            offset += 8
            
            if offset + text_length > len(payload):
                raise ValueError("Payload too short for text string")
            
            # Parse text string
            text_string = payload[offset:offset+text_length].decode('utf-8')
            offset += text_length
            
            texts.append((x_cursor, y_cursor, font_id, font_color, text_string))
        
        return cls(bg_color=bg_color, texts=texts, rotation=rotation)

    def __eq__(self, other) -> bool:
        """Check equality based on content"""
        if not isinstance(other, TextBatchMessage):
            return False
        return (
            super().__eq__(other) and 
            self.bg_color == other.bg_color and
            self.texts == other.texts and
            self.rotation == other.rotation
        )

class ImageStartMessage(ProtocolMessage):
    """Image transfer start message with rotation support and embedded chunk 0"""
    
    def __init__(self, image_id: int, image_format: ImageFormat, resolution: ImageResolution, 
                 delay_time: int, total_size: int, num_chunks: int, chunk_0_data: bytes = b'',
                 rotation: Rotation = Rotation.ROTATION_0, msg_id: int = 0):
        super().__init__(MessageType.IMAGE_TRANSFER_START, msg_id)
        self.image_id = image_id
        self.image_format = image_format
        self.resolution = resolution
        self.delay_time = delay_time
        self.total_size = total_size
        self.num_chunks = num_chunks
        self.chunk_0_data = chunk_0_data
        self.rotation = rotation
        self.encode()
    
    def _encode_payload(self):
        """Encode the image start payload with embedded chunk 0"""
        payload = bytearray()
        
        payload.append(self.image_id)  # BYTE 0: image ID
        
        # BYTE 1: 4-bit Format, 4-bit Resolution
        format_res_byte = (self.image_format << 4) | self.resolution
        payload.append(format_res_byte)
        
        # BYTE 2-3: Delay Time (0-65535 ms) - 16-bit big endian
        payload.extend(struct.pack('>H', self.delay_time))
        
        # BYTE 4-6: total image size (24-bit big endian)
        payload.append((self.total_size >> 16) & 0xFF)
        payload.append((self.total_size >> 8) & 0xFF)
        payload.append(self.total_size & 0xFF)
        
        payload.append(self.num_chunks)  # BYTE 7: num chunks
        payload.append(self.rotation)  # BYTE 8: rotation
        
        # BYTE 9 onward: Image chunk 0 data (embedded)
        payload.extend(self.chunk_0_data)
        
        return payload
    
    @classmethod
    def _decode_payload(cls, payload: bytearray) -> "ImageStartMessage":
        """Decode image start payload with embedded chunk 0"""
        if len(payload) < 9:  # Minimum length for header
            raise ValueError("Insufficient payload for image start")
        
        image_id = payload[0]
        
        format_res_byte = payload[1]
        image_format = ImageFormat((format_res_byte >> 4) & 0x0F)
        resolution = ImageResolution(format_res_byte & 0x0F)
        
        # BYTE 2-3: Delay Time (16-bit big endian)
        delay_time = struct.unpack('>H', payload[2:4])[0]
        
        # BYTE 4-6: Decode 24-bit total size 
        total_size = (payload[4] << 16) | (payload[5] << 8) | payload[6]
        
        num_chunks = payload[7]  # BYTE 7: num chunks
        rotation = Rotation(payload[8])  # BYTE 8: rotation
        
        # BYTE 9 onward: Embedded chunk 0 data
        chunk_0_data = bytes(payload[9:]) if len(payload) > 9 else b''
        
        return cls(
            image_id=image_id,
            image_format=image_format,
            resolution=resolution,
            delay_time=delay_time,
            total_size=total_size,
            num_chunks=num_chunks,
            chunk_0_data=chunk_0_data,
            rotation=rotation
        )

    def __eq__(self, other) -> bool:
        """Check equality based on content"""
        if not isinstance(other, ImageStartMessage):
            return False
        return (
            super().__eq__(other) and 
            self.image_id == other.image_id and
            self.image_format == other.image_format and
            self.resolution == other.resolution and
            self.delay_time == other.delay_time and
            self.total_size == other.total_size and
            self.num_chunks == other.num_chunks and
            self.chunk_0_data == other.chunk_0_data and
            self.rotation == other.rotation
        )


class ImageChunkMessage(ProtocolMessage):
    """Image chunk message with DMA-aware chunk sizing"""
    
    def __init__(self, image_id: int, chunk_id: int, start_location: int, 
                 chunk_data: bytes, msg_id: int = 0):
        super().__init__(MessageType.IMAGE_CHUNK, msg_id)
        self.image_id = image_id
        self.chunk_id = chunk_id
        self.start_location = start_location
        self.chunk_data = chunk_data
        
        # Validate chunk size against effective limits
        max_chunk_size = spi_config.max_buffer_size
        if len(chunk_data) > max_chunk_size:
            raise ValueError(f"Chunk data too large: {len(chunk_data)} bytes (max {max_chunk_size} bytes)")
        
        self.encode()
    
    def _encode_payload(self):
        """Encode the image chunk payload"""
        payload = bytearray()
        
        payload.append(self.image_id)  # BYTE 0: image ID
        payload.append(self.chunk_id)  # BYTE 1: chunk ID
        
        # BYTE 2-4: starting location (24-bit big endian)
        payload.append((self.start_location >> 16) & 0xFF)
        payload.append((self.start_location >> 8) & 0xFF)
        payload.append(self.start_location & 0xFF)
        
        # BYTE 5-6: length of chunk
        chunk_len = len(self.chunk_data)
        payload.extend(struct.pack('>H', chunk_len))
        
        # PAYLOAD: chunk data
        payload.extend(self.chunk_data)
        return payload
    
    @classmethod
    def _decode_payload(cls, payload: bytearray) -> "ImageChunkMessage":
        """Decode image chunk payload"""
        if len(payload) < 7:
            raise ValueError("Insufficient payload for image chunk")
        
        image_id = payload[0]
        chunk_id = payload[1]
        
        # Decode 24-bit start location
        start_location = (payload[2] << 16) | (payload[3] << 8) | payload[4]
        
        # Decode chunk length
        chunk_len = struct.unpack('>H', payload[5:7])[0]
        
        if len(payload) < 7 + chunk_len:
            raise ValueError("Insufficient payload for chunk data")
        
        chunk_data = bytes(payload[7:7+chunk_len])
        
        return cls(
            image_id=image_id,
            chunk_id=chunk_id,
            start_location=start_location,
            chunk_data=chunk_data
        )

    def __eq__(self, other) -> bool:
        """Check equality based on content"""
        if not isinstance(other, ImageChunkMessage):
            return False
        return (
            super().__eq__(other) and 
            self.image_id == other.image_id and
            self.chunk_id == other.chunk_id and
            self.start_location == other.start_location and
            self.chunk_data == other.chunk_data
        )


class ImageEndMessage(ProtocolMessage):
    """Image transfer end message"""
    
    def __init__(self, image_id: int, msg_id: int = 0):
        super().__init__(MessageType.IMAGE_TRANSFER_END, msg_id)
        self.image_id = image_id
        self.encode()
    
    def _encode_payload(self):
        """Encode the image end payload"""
        payload = bytearray()
        payload.append(self.image_id)  # BYTE 0: Image ID
        return payload
    
    @classmethod
    def _decode_payload(cls, payload: bytearray) -> "ImageEndMessage":
        """Decode image end payload"""
        if len(payload) < 1:
            raise ValueError("Insufficient payload for image end")
        
        image_id = payload[0]
        
        return cls(image_id=image_id)

    def __eq__(self, other) -> bool:
        """Check equality based on content"""
        if not isinstance(other, ImageEndMessage):
            return False
        return (
            super().__eq__(other) and 
            self.image_id == other.image_id
        )


class BacklightOnMessage(ProtocolMessage):
    """Backlight on message"""
    
    def __init__(self, msg_id: int = 0):
        super().__init__(MessageType.BACKLIGHT_ON, msg_id)
        self.encode()
    
    def _encode_payload(self):
        """Encode backlight on payload (no payload)"""
        return bytearray()  # Empty payload
    
    @classmethod
    def _decode_payload(cls, payload: bytearray) -> "BacklightOnMessage":
        """Decode backlight on payload (no payload expected)"""
        if len(payload) != 0:
            raise ValueError("Backlight on message should have no payload")
        
        return cls()

    def __eq__(self, other) -> bool:
        """Check equality based on content"""
        if not isinstance(other, BacklightOnMessage):
            return False
        return super().__eq__(other)


class BacklightOffMessage(ProtocolMessage):
    """Backlight off message"""
    
    def __init__(self, msg_id: int = 0):
        super().__init__(MessageType.BACKLIGHT_OFF, msg_id)
        self.encode()
    
    def _encode_payload(self):
        """Encode backlight off payload (no payload)"""
        return bytearray()  # Empty payload
    
    @classmethod
    def _decode_payload(cls, payload: bytearray) -> "BacklightOffMessage":
        """Decode backlight off payload (no payload expected)"""
        if len(payload) != 0:
            raise ValueError("Backlight off message should have no payload")
        
        return cls()

    def __eq__(self, other) -> bool:
        """Check equality based on content"""
        if not isinstance(other, BacklightOffMessage):
            return False
        return super().__eq__(other)


class PingRequestMessage(ProtocolMessage):
    """Ping request message"""
    
    def __init__(self, msg_id: int = 0):
        super().__init__(MessageType.PING_REQUEST, msg_id)
        self.encode()
    
    def _encode_payload(self):
        """Encode ping request payload (no payload)"""
        return bytearray()  # Empty payload
    
    @classmethod
    def _decode_payload(cls, payload: bytearray) -> "PingRequestMessage":
        """Decode ping request payload (no payload expected)"""
        if len(payload) != 0:
            raise ValueError("Ping request message should have no payload")
        
        return cls()

    def __eq__(self, other) -> bool:
        """Check equality based on content"""
        if not isinstance(other, PingRequestMessage):
            return False
        return super().__eq__(other)


class ScreenResponse(ProtocolMessage):
    """Screen response message - unified response format for all responses"""
    
    def __init__(self, status_code: ErrorCode = ErrorCode.SUCCESS, msg_id: int = 0):
        # ScreenResponse doesn't use the standard message type system
        # It has its own format starting with SOF_RESPONSE
        super().__init__(MessageType.PING_RESPONSE, msg_id)  # Keep for compatibility but not used in encoding
        self.status_code = status_code
        self.encode()
    
    def _encode_payload(self):
        """Encode the screen response payload"""
        payload = bytearray()
        
        payload.append(_SOF_RESPONSE)  # BYTE 0: SOF marker for response (0x7F)
        payload.append(self.msg_id)    # BYTE 1: message ID
        
        # BYTE 2-5: status code (4 bytes, big endian)
        status_value = int(self.status_code)
        payload.extend(struct.pack('>I', status_value))
        
        # BYTE 6-7: padding (0)
        payload.extend(b'\x00\x00')
        
        return payload
    
    def _encode_header(self, payload) -> None:
        """Override header encoding for screen response - payload IS the complete message"""
        # For screen response, the payload already contains the complete message format
        # No additional header wrapping needed
        self.payload = payload
    
    @classmethod
    def _decode_payload(cls, payload: bytearray) -> "ScreenResponse":
        """Decode screen response payload"""
        if len(payload) < 8:
            raise ValueError("Insufficient payload for screen response (expected 8 bytes)")
        
        # BYTE 0: Validate SOF marker for response
        if payload[0] != _SOF_RESPONSE:
            raise ValueError(f"Invalid response SOF marker: expected {_SOF_RESPONSE:02x}, got {payload[0]:02x}")
        
        # BYTE 1: message ID
        msg_id = payload[1]
        
        # BYTE 2-5: status code (4 bytes, big endian)
        status_value = struct.unpack('>I', payload[2:6])[0]
        
        try:
            status_code = ErrorCode(status_value)
        except ValueError:
            raise ValueError(f"Invalid status code: {status_value}")
        
        # BYTE 6-7: padding (ignored)
        
        instance = cls(status_code=status_code, msg_id=msg_id)
        return instance
    
    @classmethod
    def decode(cls, payload: bytearray) -> 'ScreenResponse':
        """Override decode for screen response - payload is the complete message"""
        return cls._decode_payload(payload)

    def __eq__(self, other) -> bool:
        """Check equality based on content"""
        if not isinstance(other, ScreenResponse):
            return False
        return (
            self.msg_id == other.msg_id and 
            self.status_code == other.status_code
        )

# Note: AckMessage and ErrorMessage have been unified into ScreenResponse
# All responses from the screen now use the ScreenResponse format:
# - BYTE 0: SOF marker for response (0x7F) 
# - BYTE 1: message ID
# - BYTE 2-5: status code (ErrorCode enum value, 4 bytes big endian)
# - BYTE 6-7: padding (0)
#
# For acknowledgments: status_code = ErrorCode.SUCCESS
# For errors: status_code = appropriate ErrorCode value


# Message factory for decoding
MESSAGE_CLASSES = {
    MessageType.TEXT_BATCH: TextBatchMessage,
    MessageType.IMAGE_TRANSFER_START: ImageStartMessage,
    MessageType.IMAGE_CHUNK: ImageChunkMessage,
    MessageType.IMAGE_TRANSFER_END: ImageEndMessage,
    MessageType.BACKLIGHT_ON: BacklightOnMessage,
    MessageType.BACKLIGHT_OFF: BacklightOffMessage,
    MessageType.PING_REQUEST: PingRequestMessage,
    # Note: PING_RESPONSE, ACKNOWLEDGMENT, and ERROR_MESSAGE all use ScreenResponse format
    # They don't have individual message classes since they all follow the same response format
}

# Export utility functions
__all__ = [
    'ProtocolMessage',
    'TextBatchMessage', 
    'ImageStartMessage',
    'ImageChunkMessage',
    'ImageEndMessage',
    'BacklightOnMessage',
    'BacklightOffMessage', 
    'PingRequestMessage',
    'ScreenResponse',
    'MESSAGE_CLASSES',
    'encode_text_entry',
    'calculate_effective_chunk_size',
    'calculate_effective_chunk_size_for_image_start',
    'pad_to_alignment',
    'create_ack_response',
    'create_error_response'
]