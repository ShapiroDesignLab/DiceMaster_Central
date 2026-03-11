import json
import os
import tempfile
from abc import ABC, abstractmethod
from typing import List, Optional, Any, Union, Tuple
from pydantic import BaseModel, Field, validator
from dicemaster_central.config import dice_config
from dicemaster_central.constants import (
    ImageFormat,
    ImageResolution,
    Rotation,
    FontID,
    FONT_NAME_TO_ID,
    MAX_TEXT_NUM_BYTES
)

from dicemaster_central.media_typing.protocol import (
    TextBatchMessage,
    ImageStartMessage,
    ImageChunkMessage,
)

SPI_CHUNK_SIZE = dice_config.spi_config.max_buffer_size

def is_str_of_hex_num(s: str, numbytes=2):
    """Check if a string is a valid hex number of specified byte length"""
    if not isinstance(s, str):
        return False
    if not s.startswith('0x'):
        return False
    hex_part = s[2:]
    if len(hex_part) != 2 * numbytes:
        return False
    return all(c in '0123456789ABCDEFabcdef' for c in hex_part)

def hex_str_to_int(s: str, numbytes=2):
    """Convert str '0xFFFF' to int 0xFFFF"""
    assert is_str_of_hex_num(s, numbytes)
    return int(s, 16)

class Media(BaseModel, ABC):
    """Base class for all media types"""
    media_type: str
    file_path: str
    content: Optional[Any] = Field(default=None, exclude=True)
    
    class Config:
        arbitrary_types_allowed = True
    
    def __init__(self, **data):
        super().__init__(**data)
        try:
            self.content = self._load_content()
        except Exception as e:
            raise Exception(f"Error loading content from {self.file_path}: {e}")

    @abstractmethod
    def _load_content(self):
        pass

    @abstractmethod
    def to_msg(self, **kwargs) -> Any:
        """Generate protocol messages for the media."""
        pass

class TextEntry(BaseModel):
    """Individual text entry with position, font, color, and content"""
    x_cursor: int = Field(default=48, description="X cursor position (0-479)")
    y_cursor: int = Field(default=48, description="Y cursor position (0-479)")
    font_id: int = Field(default=0, description="Font ID (0-5)")
    font_color: Union[str, int] = Field(default=0xFFFF, description="Font color (16-bit RGB565)")
    text: str = Field(default='', description="Text content (UTF-8 encoded)")
    
    @validator('x_cursor')
    def validate_x_cursor(cls, v):
        if not 0 <= v < 480:
            raise ValueError(f"X cursor position ({v}) must be between 0 and 479")
        return v
    
    @validator('y_cursor')
    def validate_y_cursor(cls, v):
        if not 0 <= v < 480:
            raise ValueError(f"Y cursor position ({v}) must be between 0 and 479")
        return v
    
    @validator('font_id')
    def validate_font_id(cls, v):
        try:
            FontID(v)
        except ValueError:
            raise ValueError(f"Font ID {v} not available!")
        return v
    
    @validator('font_color')
    def validate_font_color(cls, v):
        if isinstance(v, str):
            try:
                v = hex_str_to_int(v, numbytes=2)
            except ValueError:
                raise ValueError(f"Invalid hex color format: {v}")
        if not 0 <= v <= 0xFFFF:
            raise ValueError(f"Font color must be a 16-bit value (0-65535), got {v}")
        return v
    
    @validator('text')
    def validate_text_length(cls, v):
        text_bytes = v.encode('utf-8')
        if len(text_bytes) > MAX_TEXT_NUM_BYTES:
            raise ValueError(f"Text string too long (max 255 bytes): '{v[:50]}...'")
        return v
    
    def to_tuple(self) -> Tuple[int, int, int, int, str]:
        """Convert to tuple format for protocol compatibility"""
        return (self.x_cursor, self.y_cursor, self.font_id, self.font_color, self.text)

class TextGroup(Media):
    """Text group media loaded from JSON files - implements protocol TEXT_BATCH format"""
    media_type: str = Field(default='text', const=True)
    
    # Protocol fields for TEXT_BATCH message
    bg_color: Union[str, int] = Field(default=0x0000, description="Background color (16-bit RGB565)")
    texts: List[TextEntry] = Field(default_factory=list, description="List of TextEntry objects")
    
    @validator('file_path')
    def validate_json_file(cls, v):
        """Validate json"""
        if not v.endswith(".json"):
            raise ValueError("TextGroup file must be a .json file")
        return v
    
    @validator('bg_color')
    def validate_bg_color(cls, v):
        if isinstance(v, str):
            # Handle hex string format
            if not v.startswith('0x') or len(v) != 6:
                raise ValueError(f"Background color hex string must be in format '0xXXXX', got {v}")
            try:
                v = hex_str_to_int(v, numbytes=2)
            except ValueError:
                raise ValueError(f"Invalid hex color format: {v}")
        
        if not 0 <= v <= 0xFFFF:
            raise ValueError(f"Background color must be a 16-bit value (0-65535), got {v}")
        return v

    def _load_content(self):
        with open(self.file_path, 'r', encoding='utf-8') as f:
            payload = json.load(f)
        
        # Load protocol-required fields from JSON - let validator handle conversion
        self.bg_color = payload.get('bg_color', 0x0000)
        self.bg_color = hex_str_to_int(self.bg_color, numbytes=2) if isinstance(self.bg_color, str) else self.bg_color

        # Load text entries - expect array of objects with x, y, font_name/font_id, font_color, text
        texts_data = payload.get('texts', [])
        self.texts = []
        
        for text_entry in texts_data:
            # Handle font name conversion to font ID
            font_id = text_entry.get('font_id', 0)
            if 'font_name' in text_entry:
                font_name = text_entry['font_name']
                if font_name not in FONT_NAME_TO_ID:
                    raise ValueError(f"Unknown font name: {font_name}")
                font_id = FONT_NAME_TO_ID[font_name]
            
            # Handle font color (can be hex string or int) - let validator handle conversion
            font_color = text_entry.get('font_color', 0xFFFF)
            
            # Support both old format (without font_color) and new format (with font_color)
            text_obj = TextEntry(
                x_cursor=text_entry.get('x', text_entry.get('x_cursor', 0)),
                y_cursor=text_entry.get('y', text_entry.get('y_cursor', 0)),
                font_id=font_id,
                font_color=font_color,
                text=text_entry.get('text', '')
            )
            self.texts.append(text_obj)
        return payload
    
    def to_msg(self, **kwargs) -> TextBatchMessage:
        """Create protocol message with rotation support"""
        rotation = kwargs.get('rotation', Rotation.ROTATION_0)
        screen_id = kwargs.get('screen_id', 0)
        
        # Pass TextEntry objects directly for optimized encoding
        return TextBatchMessage(
            bg_color=self.bg_color,
            texts=self.texts,  # Pass TextEntry objects directly
            rotation=rotation,
            screen_id=screen_id
        )

class OptionGroup(TextGroup):
    """Virtual text group with predefined content"""
    
    def __init__(self,
        file_path: str,
        bg_color: int = 0x0000,
        texts: Optional[List[TextEntry]] = None,
        **data
    ):
        # Set the content before calling parent init
        self._predefined_content = {
            'bg_color': bg_color,
            'texts': texts or []
        }
        super().__init__(file_path=file_path, **data)

    def _load_content(self):
        # Load from predefined content instead of file
        self.bg_color = self._predefined_content['bg_color']
        self.texts = self._predefined_content['texts']
        return self._predefined_content


class Image(Media):
    """Image media with protocol-compliant metadata - implements IMAGE_TRANSFER_START format"""
    media_type: str = Field(default='image', const=True)
    
    # Protocol fields for IMAGE_TRANSFER_START message
    image_id: int = Field(default=0, description="Image ID (0-255)")
    image_format: ImageFormat = Field(default=ImageFormat.JPEG, description="Image format")
    resolution: ImageResolution = Field(default=ImageResolution.SQ480, description="Image resolution")
    delay_time: int = Field(default=0, description="Delay time in ms (0-65535)")
    total_size: int = Field(default=0, description="Total image size in bytes")
    num_chunks: int = Field(default=0, description="Number of chunks for transfer")
    
    # Additional metadata
    dimensions: Optional[Tuple[int, int]] = None
    
    @validator('image_id')
    def validate_image_id(cls, v):
        if not 0 <= v <= 255:
            raise ValueError("Image ID must be between 0 and 255")
        return v
    
    @validator('delay_time')
    def validate_delay_time(cls, v):
        if not 0 <= v <= 65535:  # Updated for 16-bit range
            raise ValueError("Delay time must be between 0 and 65535 ms")
        return v
    
    @validator('total_size')
    def validate_total_size(cls, v):
        if not 0 <= v <= 0xFFFFFF:  # 24-bit max
            raise ValueError("Total size must be between 0 and 16777215 bytes")
        return v
    
    @validator('num_chunks')
    def validate_num_chunks(cls, v):
        if not 0 <= v <= 255:
            raise ValueError("Number of chunks must be between 0 and 255")
        return v
    
    def _load_content(self):
        # Load the image file into a bytes object
        with open(self.file_path, 'rb') as f:
            content = f.read()
        
        # Load metadata and determine protocol fields
        self._load_metadata()
        
        # Set protocol fields based on file content
        self.total_size = len(content)
        
        # Calculate num_chunks using effective chunk size to account for DMA restrictions
        try:
            from .protocol import calculate_effective_chunk_size
            effective_chunk_size = calculate_effective_chunk_size(SPI_CHUNK_SIZE)
            self.num_chunks = self._calculate_chunks(len(content), effective_chunk_size)
        except ImportError:
            # Fallback to original calculation if protocol module not available
            self.num_chunks = self._calculate_chunks(len(content))
        
        return content

    def _load_metadata(self):
        """Get the file type and dimensions, validate against protocol requirements"""
        from PIL import Image as PILImage
        img = PILImage.open(self.file_path)
        
        # Map PIL format to protocol format
        format_mapping = {
            'JPEG': ImageFormat.JPEG,
            'BMP': ImageFormat.RGB565,
        }
        
        self.image_format = format_mapping.get(img.format, ImageFormat.JPEG)
        self.dimensions = img.size
        
        # Validate and set resolution based on dimensions
        if self.dimensions == (480, 480):
            self.resolution = ImageResolution.SQ480
        elif self.dimensions == (240, 240):
            self.resolution = ImageResolution.SQ240
        else:
            raise ValueError(f"Unsupported image dimensions: {self.dimensions}. "
                           f"Must be 480x480, 240x240, 320x240, or 640x480")
    
    def _calculate_chunks(self, total_size: int, chunk_size: int = SPI_CHUNK_SIZE) -> int:
        """Calculate number of chunks needed for transfer"""
        return (total_size + chunk_size - 1) // chunk_size  # Ceiling division
    
    def to_msg(self, **kwargs) -> List[Union[ImageStartMessage, ImageChunkMessage]]:
        """Generate all protocol messages for image transfer with DMA-aware chunking and embedded chunk 0"""
        from .protocol import calculate_effective_chunk_size, calculate_effective_chunk_size_for_image_start
        
        rotation = kwargs.get('rotation', Rotation.ROTATION_0)
        screen_id = kwargs.get('screen_id', 0)
        spi_chunk_size = kwargs.get('chunk_size', SPI_CHUNK_SIZE)
        
        # Calculate effective chunk sizes considering DMA restrictions
        regular_chunk_size = calculate_effective_chunk_size(spi_chunk_size)
        embedded_chunk_size = calculate_effective_chunk_size_for_image_start(spi_chunk_size)
        
        if not self.content:
            raise ValueError("Image content not loaded")
            
        messages = []
        
        # Extract chunk 0 data for embedding in ImageStart
        chunk_0_data = self.content[:embedded_chunk_size] if len(self.content) > 0 else b''
        
        # Recalculate total number of chunks
        # Chunk 0 is embedded, remaining chunks use regular chunk size
        remaining_data_size = len(self.content) - len(chunk_0_data)
        remaining_chunks = (remaining_data_size + regular_chunk_size - 1) // regular_chunk_size if remaining_data_size > 0 else 0
        total_chunks = 1 + remaining_chunks  # 1 for embedded chunk 0 + remaining chunks
        
        # Create start message with embedded chunk 0
        start_message = ImageStartMessage(
            screen_id=screen_id,
            image_id=self.image_id,
            image_format=self.image_format,
            resolution=self.resolution,
            delay_time=self.delay_time,
            total_size=self.total_size,
            num_chunks=total_chunks,
            chunk_0_data=chunk_0_data,
            rotation=rotation
        )
        messages.append(start_message)
        
        # Create remaining chunk messages (starting from chunk ID 1)
        chunk_id = 1
        start_location = len(chunk_0_data)
        
        for i in range(len(chunk_0_data), len(self.content), regular_chunk_size):
            chunk_data = self.content[i:i + regular_chunk_size]
            
            chunk_message = ImageChunkMessage(
                screen_id=screen_id,
                image_id=self.image_id,
                chunk_id=chunk_id,
                start_location=start_location,
                chunk_data=chunk_data
            )
            messages.append(chunk_message)
            
            chunk_id += 1
            start_location += len(chunk_data)
        
        return messages


class GIF(Media):
    """Motion picture (animated) media from frame directories - implements multi-frame IMAGE transfer"""
    media_type: str = Field(default='motion_picture', const=True)
    
    # Protocol fields - similar to Image but for multiple frames
    image_id: int = Field(default=0, description="Image ID (0-255)")
    image_format: ImageFormat = Field(default=ImageFormat.JPEG, description="Format of frame images")
    resolution: ImageResolution = Field(default=ImageResolution.SQ240, description="Resolution of frames")
    delay_time: int = Field(default=100, description="Frame delay in ms (0-65535)")
    
    # Motion picture specific fields
    frames_data: List[bytes] = Field(default_factory=list, description="Frame image data")
    frame_count: int = Field(default=0, description="Number of frames")
    total_duration: int = Field(default=0, description="Total animation duration in ms")
    
    @validator('file_path')
    def validate_gif_directory(cls, v):
        if not v.endswith('.gif.d'):
            raise ValueError("GIF file must be a .gif.d directory")
        return v
    
    @validator('image_id')
    def validate_image_id(cls, v):
        if not 0 <= v <= 255:
            raise ValueError("Image ID must be between 0 and 255")
        return v
    
    @validator('delay_time')
    def validate_delay_time(cls, v):
        if not 0 <= v <= 65535:  # Updated for 16-bit range
            raise ValueError("Delay time must be between 0 and 65535 ms")
        return v

    def _load_content(self):
        """Load directory of frames from the motion picture file."""
        if not os.path.isdir(self.file_path):
            raise ValueError(f"Motion picture path must be a directory: {self.file_path}")
        
        self.frames_data = []
        frame_files = []
        
        # Collect all .jpg files and sort them numerically
        for frame_file in os.listdir(self.file_path):
            if frame_file.endswith(".jpg"):
                frame_files.append(frame_file)
        
        # Sort numerically (0.jpg, 1.jpg, ..., k.jpg)
        frame_files.sort(key=lambda x: int(x.split('.')[0]))
        
        # Load frame data and validate format/resolution
        for frame_file in frame_files:
            frame_path = os.path.join(self.file_path, frame_file)
            with open(frame_path, 'rb') as f:
                frame_data = f.read()
                self.frames_data.append(frame_data)
        
        # Set gif metadata
        self.frame_count = len(self.frames_data)
        self.total_duration = self.frame_count * self.delay_time
        
        # Validate first frame to determine format and resolution
        if self.frames_data:
            self._validate_frame_metadata()
        
        return self.frames_data
    
    def _validate_frame_metadata(self):
        """Validate format and resolution of frames using the first frame"""
        if not self.frames_data:
            return
            
        # Create a temporary file to analyze the first frame
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as temp_file:
            temp_file.write(self.frames_data[0])
            temp_path = temp_file.name
        
        try:
            from PIL import Image as PILImage
            img = PILImage.open(temp_path)
            
            # Validate format
            if img.format != 'JPEG':
                raise ValueError(f"All frames must be JPEG format, found: {img.format}")
            
            self.image_format = ImageFormat.JPEG
            
            # Validate and set resolution
            dimensions = img.size
            if dimensions == (480, 480):
                self.resolution = ImageResolution.SQ480
            elif dimensions == (240, 240):
                self.resolution = ImageResolution.SQ240
            else:
                raise ValueError(f"Unsupported frame dimensions: {dimensions}. "
                               f"Must be 480x480, 240x240")
        finally:
            os.unlink(temp_path)
    
    def frames(self):
        """Iterator for frames"""
        for frame in self.frames_data:
            yield frame
    
    def get_frame_metadata(self, frame_index: int) -> dict:
        """Get protocol metadata for a specific frame with DMA-aware chunking and embedded chunk 0"""
        from .protocol import calculate_effective_chunk_size, calculate_effective_chunk_size_for_image_start
        
        if not 0 <= frame_index < len(self.frames_data):
            raise IndexError(f"Frame index {frame_index} out of range")
        
        frame_data = self.frames_data[frame_index]
        # Use DMA-aware effective chunk sizes
        regular_chunk_size = calculate_effective_chunk_size(8192)  # Updated to 8KB SPI chunks
        embedded_chunk_size = calculate_effective_chunk_size_for_image_start(8192)
        
        # Calculate chunks similar to Image.to_msg
        chunk_0_size = min(embedded_chunk_size, len(frame_data))
        remaining_data_size = len(frame_data) - chunk_0_size
        remaining_chunks = (remaining_data_size + regular_chunk_size - 1) // regular_chunk_size if remaining_data_size > 0 else 0
        total_chunks = 1 + remaining_chunks  # 1 for embedded chunk 0 + remaining chunks
        
        return {
            'image_id': frame_index,
            'image_format': self.image_format,
            'resolution': self.resolution,
            'delay_time': self.delay_time,
            'total_size': len(frame_data),
            'num_chunks': total_chunks
        }
    
    def to_msg(self, **kwargs) -> List[List[Union[ImageStartMessage, ImageChunkMessage]]]:
        """Return a list of protocol message lists for each frame, built from already-loaded frames_data"""
        from .protocol import calculate_effective_chunk_size, calculate_effective_chunk_size_for_image_start

        rotation = kwargs.get('rotation', Rotation.ROTATION_0)
        screen_id = kwargs.get('screen_id', 0)
        spi_chunk_size = kwargs.get('chunk_size', 8192)

        if not self.frames_data:
            raise ValueError("No frames loaded")

        regular_chunk_size = calculate_effective_chunk_size(spi_chunk_size)
        embedded_chunk_size = calculate_effective_chunk_size_for_image_start(spi_chunk_size)

        frame_messages = []

        for frame_index, frame_data in enumerate(self.frames_data):
            chunk_0_data = frame_data[:embedded_chunk_size]
            remaining_data_size = len(frame_data) - len(chunk_0_data)
            remaining_chunks = (remaining_data_size + regular_chunk_size - 1) // regular_chunk_size if remaining_data_size > 0 else 0
            total_chunks = 1 + remaining_chunks

            messages = []

            start_message = ImageStartMessage(
                screen_id=screen_id,
                image_id=frame_index,
                image_format=self.image_format,
                resolution=self.resolution,
                delay_time=self.delay_time,
                total_size=len(frame_data),
                num_chunks=total_chunks,
                chunk_0_data=chunk_0_data,
                rotation=rotation
            )
            messages.append(start_message)

            chunk_id = 1
            start_location = len(chunk_0_data)
            for i in range(len(chunk_0_data), len(frame_data), regular_chunk_size):
                chunk_data = frame_data[i:i + regular_chunk_size]
                chunk_message = ImageChunkMessage(
                    screen_id=screen_id,
                    image_id=frame_index,
                    chunk_id=chunk_id,
                    start_location=start_location,
                    chunk_data=chunk_data
                )
                messages.append(chunk_message)
                chunk_id += 1
                start_location += len(chunk_data)

            frame_messages.append(messages)

        return frame_messages