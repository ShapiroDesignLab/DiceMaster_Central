"""
Protocol implementation for DiceMaster SPI communication
Based on the protocol specification in docs/protocol.md
"""

import struct
from typing import List, Tuple, Optional
from enum import IntEnum
from abc import ABC, abstractmethod
from .constants import MessageType, Rotation, ImageFormat, ImageResolution

# Private constants for this module
_SOF = 0x7E  # Start of Frame
_HEADER_SIZE = 5  # Header is 5 bytes (SOF + Type + ID + Length)


class ProtocolMessage(ABC):
    """Base class for all protocol messages"""
    
    def __init__(self, msg_type: MessageType, msg_id: int = 0):
        self.msg_type = msg_type
        self.msg_id = msg_id
        self.payload = bytearray()
    
    def encode(self) -> bytearray:
        """Build complete message with header and payload"""
        message = bytearray()
        message.append(_SOF)  # BYTE 0: Start of Frame
        message.append(self.msg_type)  # BYTE 1: Message Type
        message.append(self.msg_id)  # BYTE 2: Message ID
        
        # BYTE 3-4: Payload length (BIG_ENDIAN)
        payload_len = len(self.payload)
        message.append((payload_len >> 8) & 0xFF)  # High byte
        message.append(payload_len & 0xFF)  # Low byte
        
        # Payload starts at BYTE 5 onwards
        message.extend(self.payload)
        return message
    
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
    
    @abstractmethod
    def decode_payload(self, payload: bytearray):
        """Decode the payload and populate message fields"""
        pass


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
        self._encode_payload()
    
    def _encode_payload(self):
        """Encode the text batch payload"""
        self.payload.clear()
        
        # Text Group header
        self.payload.extend(struct.pack('>H', self.bg_color))  # BYTE 0-1: BG Color
        self.payload.extend(struct.pack('>H', self.font_color))  # BYTE 2-3: Font Color
        self.payload.append(len(self.texts))  # BYTE 4: number of lines
        self.payload.append(self.rotation)  # BYTE 5: rotation
        
        # Individual text chunks
        for x_cursor, y_cursor, font_id, text_string in self.texts:
            text_bytes = text_string.encode('utf-8')
            if len(text_bytes) > 255:
                raise ValueError("Text string too long (max 255 bytes)")
            
            self.payload.extend(struct.pack('>H', x_cursor))  # BYTE 0-1: x cursor
            self.payload.extend(struct.pack('>H', y_cursor))  # BYTE 2-3: y cursor
            self.payload.append(font_id)  # BYTE 4: font id
            self.payload.append(len(text_bytes))  # BYTE 5: text length
            self.payload.extend(text_bytes)  # PAYLOAD STRING
    
    def decode_payload(self, payload: bytearray):
        """Decode text batch payload"""
        if len(payload) < 6:
            raise ValueError("Insufficient payload for text batch")
        
        # Decode text group header
        self.bg_color = struct.unpack('>H', payload[0:2])[0]
        self.font_color = struct.unpack('>H', payload[2:4])[0]
        num_texts = payload[4]
        self.rotation = Rotation(payload[5])
        
        # Decode individual text chunks
        self.texts = []
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
            
            self.texts.append((x_cursor, y_cursor, font_id, text_string))


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
        self._encode_payload()
    
    def _encode_payload(self):
        """Encode the image start payload"""
        self.payload.clear()
        
        self.payload.append(self.image_id)  # BYTE 0: image ID
        
        # BYTE 1: 4-bit Format, 4-bit Resolution
        format_res_byte = (self.image_format << 4) | self.resolution
        self.payload.append(format_res_byte)
        
        self.payload.append(self.delay_time)  # BYTE 2: Delay Time (0-255 ms)
        
        # BYTE 3-5: total image size (24-bit big endian)
        self.payload.append((self.total_size >> 16) & 0xFF)
        self.payload.append((self.total_size >> 8) & 0xFF)
        self.payload.append(self.total_size & 0xFF)
        
        self.payload.append(self.num_chunks)  # BYTE 6: num chunks
        self.payload.append(self.rotation)  # BYTE 7: rotation
    
    def decode_payload(self, payload: bytearray):
        """Decode image start payload"""
        if len(payload) < 8:
            raise ValueError("Insufficient payload for image start")
        
        self.image_id = payload[0]
        
        format_res_byte = payload[1]
        self.image_format = ImageFormat((format_res_byte >> 4) & 0x0F)
        self.resolution = ImageResolution(format_res_byte & 0x0F)
        
        self.delay_time = payload[2]
        
        # Decode 24-bit total size
        self.total_size = (payload[3] << 16) | (payload[4] << 8) | payload[5]
        
        self.num_chunks = payload[6]
        self.rotation = Rotation(payload[7])


class ImageChunkMessage(ProtocolMessage):
    """Image chunk message"""
    
    def __init__(self, image_id: int, chunk_id: int, start_location: int, 
                 chunk_data: bytes, msg_id: int = 0):
        super().__init__(MessageType.IMAGE_CHUNK, msg_id)
        self.image_id = image_id
        self.chunk_id = chunk_id
        self.start_location = start_location
        self.chunk_data = chunk_data
        self._encode_payload()
    
    def _encode_payload(self):
        """Encode the image chunk payload"""
        if len(self.chunk_data) > 65535:
            raise ValueError("Chunk data too large (max 65535 bytes)")
        
        self.payload.clear()
        
        self.payload.append(self.image_id)  # BYTE 0: image ID
        self.payload.append(self.chunk_id)  # BYTE 1: chunk ID
        
        # BYTE 2-4: starting location (24-bit big endian)
        self.payload.append((self.start_location >> 16) & 0xFF)
        self.payload.append((self.start_location >> 8) & 0xFF)
        self.payload.append(self.start_location & 0xFF)
        
        # BYTE 5-6: length of chunk
        chunk_len = len(self.chunk_data)
        self.payload.extend(struct.pack('>H', chunk_len))
        
        # PAYLOAD: chunk data
        self.payload.extend(self.chunk_data)
    
    def decode_payload(self, payload: bytearray):
        """Decode image chunk payload"""
        if len(payload) < 7:
            raise ValueError("Insufficient payload for image chunk")
        
        self.image_id = payload[0]
        self.chunk_id = payload[1]
        
        # Decode 24-bit start location
        self.start_location = (payload[2] << 16) | (payload[3] << 8) | payload[4]
        
        # Decode chunk length
        chunk_len = struct.unpack('>H', payload[5:7])[0]
        
        if len(payload) < 7 + chunk_len:
            raise ValueError("Insufficient payload for chunk data")
        
        self.chunk_data = bytes(payload[7:7+chunk_len])


class ImageEndMessage(ProtocolMessage):
    """Image transfer end message"""
    
    def __init__(self, image_id: int, msg_id: int = 0):
        super().__init__(MessageType.IMAGE_TRANSFER_END, msg_id)
        self.image_id = image_id
        self._encode_payload()
    
    def _encode_payload(self):
        """Encode the image end payload"""
        self.payload.clear()
        self.payload.append(self.image_id)  # BYTE 0: Image ID
    
    def decode_payload(self, payload: bytearray):
        """Decode image end payload"""
        if len(payload) < 1:
            raise ValueError("Insufficient payload for image end")
        
        self.image_id = payload[0]


class BacklightOnMessage(ProtocolMessage):
    """Backlight on message"""
    
    def __init__(self, msg_id: int = 0):
        super().__init__(MessageType.BACKLIGHT_ON, msg_id)
        # No payload for backlight on
    
    def decode_payload(self, payload: bytearray):
        """Decode backlight on payload (no payload expected)"""
        if len(payload) != 0:
            raise ValueError("Backlight on message should have no payload")


class BacklightOffMessage(ProtocolMessage):
    """Backlight off message"""
    
    def __init__(self, msg_id: int = 0):
        super().__init__(MessageType.BACKLIGHT_OFF, msg_id)
        # No payload for backlight off
    
    def decode_payload(self, payload: bytearray):
        """Decode backlight off payload (no payload expected)"""
        if len(payload) != 0:
            raise ValueError("Backlight off message should have no payload")


class PingRequestMessage(ProtocolMessage):
    """Ping request message"""
    
    def __init__(self, msg_id: int = 0):
        super().__init__(MessageType.PING_REQUEST, msg_id)
        # No payload for ping request
    
    def decode_payload(self, payload: bytearray):
        """Decode ping request payload (no payload expected)"""
        if len(payload) != 0:
            raise ValueError("Ping request message should have no payload")


class PingResponseMessage(ProtocolMessage):
    """Ping response message"""
    
    def __init__(self, status_code: int = 0, status_string: str = "OK", msg_id: int = 0):
        super().__init__(MessageType.PING_RESPONSE, msg_id)
        self.status_code = status_code
        self.status_string = status_string
        self._encode_payload()
    
    def _encode_payload(self):
        """Encode the ping response payload"""
        self.payload.clear()
        
        status_bytes = self.status_string.encode('utf-8')
        if len(status_bytes) > 255:
            raise ValueError("Status string too long (max 255 bytes)")
        
        self.payload.append(self.status_code)  # BYTE 0: status code
        self.payload.append(len(status_bytes))  # BYTE 1: text length
        self.payload.extend(status_bytes)  # BYTE 2 onwards: status string
    
    def decode_payload(self, payload: bytearray):
        """Decode ping response payload"""
        if len(payload) < 2:
            raise ValueError("Insufficient payload for ping response")
        
        self.status_code = payload[0]
        text_len = payload[1]
        
        if len(payload) < 2 + text_len:
            raise ValueError("Insufficient payload for status string")
        
        self.status_string = payload[2:2+text_len].decode('utf-8')


class AckMessage(ProtocolMessage):
    """Acknowledgment message"""
    
    def __init__(self, ack_msg_id: int = 0, msg_id: int = 0):
        super().__init__(MessageType.ACKNOWLEDGMENT, msg_id)
        self.ack_msg_id = ack_msg_id
        self._encode_payload()
    
    def _encode_payload(self):
        """Encode the acknowledgment payload"""
        self.payload.clear()
        self.payload.append(self.ack_msg_id)  # BYTE 0: Message ID being acknowledged
    
    def decode_payload(self, payload: bytearray):
        """Decode acknowledgment payload"""
        if len(payload) < 1:
            raise ValueError("Insufficient payload for acknowledgment")
        
        self.ack_msg_id = payload[0]


class ErrorMessage(ProtocolMessage):
    """Error message (NACK)"""
    
    def __init__(self, error_msg_id: int = 0, error_code: int = 0, msg_id: int = 0):
        super().__init__(MessageType.ERROR_MESSAGE, msg_id)
        self.error_msg_id = error_msg_id
        self.error_code = error_code
        self._encode_payload()
    
    def _encode_payload(self):
        """Encode the error message payload"""
        self.payload.clear()
        self.payload.append(self.error_msg_id)  # BYTE 0: Message ID that caused error
        self.payload.append(self.error_code)  # BYTE 1: Error code
    
    def decode_payload(self, payload: bytearray):
        """Decode error message payload"""
        if len(payload) < 2:
            raise ValueError("Insufficient payload for error message")
        
        self.error_msg_id = payload[0]
        self.error_code = payload[1]


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


def decode_message(data: bytearray) -> ProtocolMessage:
    """Decode a message from raw data"""
    msg_type, msg_id, payload_len, payload_start = ProtocolMessage.decode_header(data)
    
    if len(data) < payload_start + payload_len:
        raise ValueError("Insufficient data for payload")
    
    payload = data[payload_start:payload_start + payload_len]
    
    try:
        msg_type_enum = MessageType(msg_type)
    except ValueError:
        raise ValueError(f"Unknown message type: {msg_type:02x}")
    
    if msg_type_enum not in MESSAGE_CLASSES:
        raise ValueError(f"No decoder for message type: {msg_type_enum}")
    
    # Create message instance and decode payload
    message_class = MESSAGE_CLASSES[msg_type_enum]
    message = message_class.__new__(message_class)  # Create without calling __init__
    ProtocolMessage.__init__(message, msg_type_enum, msg_id)
    message.decode_payload(payload)
    
    return message