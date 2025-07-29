"""
Protocol implementation for DiceMaster SPI communication
Based on the protocol specification in docs/protocol.md
"""

import struct
from typing import List, Tuple, Optional

from abc import ABC, abstractmethod
from DiceMaster_Central.config.constants import (
    MessageType,
    Rotation,
    ImageFormat,
    ImageResolution
)

# Private constants for this module
_SOF = 0x7E  # Start of Frame
_HEADER_SIZE = 5  # Header is 5 bytes (SOF + Type + ID + Length)


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
        self.payload = message  # Store complete message in payload

    @abstractmethod
    def _encode_payload(self) -> bytearray:
        pass

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
    def _decode_payload(cls, payload: bytearray):
        """Decode the payload and return a new message instance"""
        pass

    @classmethod
    def decode(cls, payload: bytearray):
        """Decode API"""
        if len(payload) < _HEADER_SIZE:
            raise ValueError("Insufficient payload for decoding")
        
        # Extract header information
        msg_type, msg_id, payload_len, payload_start = cls.decode_header(payload)
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
    """Text batch message with rotation support"""
    
    def __init__(self, bg_color: int = 0, font_color: int = 0xFFFF, 
                 texts: Optional[List[Tuple[int, int, int, str]]] = None, 
                 rotation: Rotation = Rotation.ROTATION_0, msg_id: int = 0):
        super().__init__(MessageType.TEXT_BATCH, msg_id)
        self.bg_color = bg_color
        self.font_color = font_color
        self.texts = texts or []
        self.rotation = rotation
        self.encode()
    
    def _encode_payload(self):
        """Encode the text batch payload"""
        payload = bytearray()
        
        # Text Group header
        payload.extend(struct.pack('>H', self.bg_color))  # BYTE 0-1: BG Color
        payload.extend(struct.pack('>H', self.font_color))  # BYTE 2-3: Font Color
        payload.append(len(self.texts))  # BYTE 4: number of lines
        payload.append(self.rotation)  # BYTE 5: rotation
        
        # Individual text chunks
        for x_cursor, y_cursor, font_id, text_string in self.texts:
            text_bytes = text_string.encode('utf-8')
            if len(text_bytes) > 255:
                raise ValueError("Text string too long (max 255 bytes)")
            
            payload.extend(struct.pack('>H', x_cursor))  # BYTE 0-1: x cursor
            payload.extend(struct.pack('>H', y_cursor))  # BYTE 2-3: y cursor
            payload.append(font_id)  # BYTE 4: font id
            payload.append(len(text_bytes))  # BYTE 5: text length
            payload.extend(text_bytes)  # PAYLOAD STRING
        return payload
    
    @classmethod
    def _decode_payload(cls, payload: bytearray) -> "TextBatchMessage":
        """Decode text batch payload"""
        if len(payload) < 6:
            raise ValueError("Insufficient payload for text batch")
        
        # Decode text group header
        bg_color = struct.unpack('>H', payload[0:2])[0]
        font_color = struct.unpack('>H', payload[2:4])[0]
        num_texts = payload[4]
        rotation = Rotation(payload[5])
        
        # Decode individual text chunks
        texts = []
        offset = 6
        
        for _ in range(num_texts):
            if offset + 6 > len(payload):
                raise ValueError("Insufficient payload for text chunk")
            
            x_cursor = struct.unpack('>H', payload[offset:offset+2])[0]
            y_cursor = struct.unpack('>H', payload[offset+2:offset+4])[0]
            font_id = payload[offset+4]
            text_len = payload[offset+5]
            offset += 6
            
            if offset + text_len > len(payload):
                raise ValueError("Insufficient payload for text string")
            
            text_string = payload[offset:offset+text_len].decode('utf-8')
            offset += text_len
            
            texts.append((x_cursor, y_cursor, font_id, text_string))

        return cls(
            bg_color=bg_color,
            font_color=font_color,
            texts=texts,
            rotation=rotation
        )

    def __eq__(self, other) -> bool:
        """Check equality based on content"""
        if not isinstance(other, TextBatchMessage):
            return False
        return (
            super().__eq__(other) and 
            self.bg_color == other.bg_color and
            self.font_color == other.font_color and
            self.texts == other.texts and
            self.rotation == other.rotation
        )

class ImageStartMessage(ProtocolMessage):
    """Image transfer start message with rotation support"""
    
    def __init__(self, image_id: int, image_format: ImageFormat, resolution: ImageResolution, 
                 delay_time: int, total_size: int, num_chunks: int, 
                 rotation: Rotation = Rotation.ROTATION_0, msg_id: int = 0):
        super().__init__(MessageType.IMAGE_TRANSFER_START, msg_id)
        self.image_id = image_id
        self.image_format = image_format
        self.resolution = resolution
        self.delay_time = delay_time
        self.total_size = total_size
        self.num_chunks = num_chunks
        self.rotation = rotation
        self.encode()
    
    def _encode_payload(self):
        """Encode the image start payload"""
        payload = bytearray()
        
        payload.append(self.image_id)  # BYTE 0: image ID
        
        # BYTE 1: 4-bit Format, 4-bit Resolution
        format_res_byte = (self.image_format << 4) | self.resolution
        payload.append(format_res_byte)
        
        payload.append(self.delay_time)  # BYTE 2: Delay Time (0-255 ms)
        
        # BYTE 3-5: total image size (24-bit big endian)
        payload.append((self.total_size >> 16) & 0xFF)
        payload.append((self.total_size >> 8) & 0xFF)
        payload.append(self.total_size & 0xFF)
        
        payload.append(self.num_chunks)  # BYTE 6: num chunks
        payload.append(self.rotation)  # BYTE 7: rotation
        return payload
    
    @classmethod
    def _decode_payload(cls, payload: bytearray):
        """Decode image start payload"""
        if len(payload) < 8:
            raise ValueError("Insufficient payload for image start")
        
        image_id = payload[0]
        
        format_res_byte = payload[1]
        image_format = ImageFormat((format_res_byte >> 4) & 0x0F)
        resolution = ImageResolution(format_res_byte & 0x0F)
        
        delay_time = payload[2]
        
        # Decode 24-bit total size
        total_size = (payload[3] << 16) | (payload[4] << 8) | payload[5]
        
        num_chunks = payload[6]
        rotation = Rotation(payload[7])
        
        return cls(
            image_id=image_id,
            image_format=image_format,
            resolution=resolution,
            delay_time=delay_time,
            total_size=total_size,
            num_chunks=num_chunks,
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
            self.rotation == other.rotation
        )


class ImageChunkMessage(ProtocolMessage):
    """Image chunk message"""
    
    def __init__(self, image_id: int, chunk_id: int, start_location: int, 
                 chunk_data: bytes, msg_id: int = 0):
        super().__init__(MessageType.IMAGE_CHUNK, msg_id)
        self.image_id = image_id
        self.chunk_id = chunk_id
        self.start_location = start_location
        self.chunk_data = chunk_data
        self.encode()
    
    def _encode_payload(self):
        """Encode the image chunk payload"""
        if len(self.chunk_data) > 65535:
            raise ValueError("Chunk data too large (max 65535 bytes)")
        
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
    def _decode_payload(cls, payload: bytearray):
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
    def _decode_payload(cls, payload: bytearray):
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
    def _decode_payload(cls, payload: bytearray):
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
    def _decode_payload(cls, payload: bytearray):
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
    def _decode_payload(cls, payload: bytearray):
        """Decode ping request payload (no payload expected)"""
        if len(payload) != 0:
            raise ValueError("Ping request message should have no payload")
        
        return cls()

    def __eq__(self, other) -> bool:
        """Check equality based on content"""
        if not isinstance(other, PingRequestMessage):
            return False
        return super().__eq__(other)


class PingResponseMessage(ProtocolMessage):
    """Ping response message"""
    
    def __init__(self, status_code: int = 0, status_string: str = "OK", msg_id: int = 0):
        super().__init__(MessageType.PING_RESPONSE, msg_id)
        self.status_code = status_code
        self.status_string = status_string
        self.encode()
    
    def _encode_payload(self):
        """Encode the ping response payload"""
        payload = bytearray()
        
        status_bytes = self.status_string.encode('utf-8')
        if len(status_bytes) > 255:
            raise ValueError("Status string too long (max 255 bytes)")
        
        payload.append(self.status_code)  # BYTE 0: status code
        payload.append(len(status_bytes))  # BYTE 1: text length
        payload.extend(status_bytes)  # BYTE 2 onwards: status string
        return payload
    
    @classmethod
    def _decode_payload(cls, payload: bytearray):
        """Decode ping response payload"""
        if len(payload) < 2:
            raise ValueError("Insufficient payload for ping response")
        
        status_code = payload[0]
        text_len = payload[1]
        
        if len(payload) < 2 + text_len:
            raise ValueError("Insufficient payload for status string")
        
        status_string = payload[2:2+text_len].decode('utf-8')
        
        return cls(status_code=status_code, status_string=status_string)

    def __eq__(self, other) -> bool:
        """Check equality based on content"""
        if not isinstance(other, PingResponseMessage):
            return False
        return (
            super().__eq__(other) and 
            self.status_code == other.status_code and
            self.status_string == other.status_string
        )


class AckMessage(ProtocolMessage):
    """Acknowledgment message"""
    
    def __init__(self, ack_msg_id: int = 0, msg_id: int = 0):
        super().__init__(MessageType.ACKNOWLEDGMENT, msg_id)
        self.ack_msg_id = ack_msg_id
        self.encode()
    
    def _encode_payload(self):
        """Encode the acknowledgment payload"""
        payload = bytearray()
        payload.append(self.ack_msg_id)  # BYTE 0: Message ID being acknowledged
        return payload
    
    @classmethod
    def _decode_payload(cls, payload: bytearray):
        """Decode acknowledgment payload"""
        if len(payload) < 1:
            raise ValueError("Insufficient payload for acknowledgment")
        
        ack_msg_id = payload[0]
        
        return cls(ack_msg_id=ack_msg_id)

    def __eq__(self, other) -> bool:
        """Check equality based on content"""
        if not isinstance(other, AckMessage):
            return False
        return (
            super().__eq__(other) and 
            self.ack_msg_id == other.ack_msg_id
        )


class ErrorMessage(ProtocolMessage):
    """Error message (NACK)"""
    
    def __init__(self, error_msg_id: int = 0, error_code: int = 0, msg_id: int = 0):
        super().__init__(MessageType.ERROR_MESSAGE, msg_id)
        self.error_msg_id = error_msg_id
        self.error_code = error_code
        self.encode()
    
    def _encode_payload(self):
        """Encode the error message payload"""
        payload = bytearray()
        payload.append(self.error_msg_id)  # BYTE 0: Message ID that caused error
        payload.append(self.error_code)  # BYTE 1: Error code
        return payload
    
    @classmethod
    def _decode_payload(cls, payload: bytearray):
        """Decode error message payload"""
        if len(payload) < 2:
            raise ValueError("Insufficient payload for error message")
        
        error_msg_id = payload[0]
        error_code = payload[1]
        
        return cls(error_msg_id=error_msg_id, error_code=error_code)

    def __eq__(self, other) -> bool:
        """Check equality based on content"""
        if not isinstance(other, ErrorMessage):
            return False
        return (
            super().__eq__(other) and 
            self.error_msg_id == other.error_msg_id and
            self.error_code == other.error_code
        )


# Message factory for decoding
MESSAGE_CLASSES = {
    MessageType.TEXT_BATCH: TextBatchMessage,
    MessageType.IMAGE_TRANSFER_START: ImageStartMessage,
    MessageType.IMAGE_CHUNK: ImageChunkMessage,
    MessageType.IMAGE_TRANSFER_END: ImageEndMessage,
    MessageType.BACKLIGHT_ON: BacklightOnMessage,
    MessageType.BACKLIGHT_OFF: BacklightOffMessage,
    MessageType.PING_REQUEST: PingRequestMessage,
    MessageType.PING_RESPONSE: PingResponseMessage,
    MessageType.ACKNOWLEDGMENT: AckMessage,
    MessageType.ERROR_MESSAGE: ErrorMessage,
}