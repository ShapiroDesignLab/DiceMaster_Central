import json
import os
from abc import ABC, abstractmethod
from typing import List, Optional, Any, Union, Tuple
from pydantic import BaseModel, Field, validator, root_validator
from DiceMaster_Central.config.constants import ImageFormat, ImageResolution, Rotation


class Media(BaseModel, ABC):
    """Base class for all media types"""
    media_type: str
    file_path: str
    content: Optional[Any] = Field(default=None, exclude=True)
    
    class Config:
        arbitrary_types_allowed = True
    
    def __init__(self, **data):
        super().__init__(**data)
        self.content = self._load_content()
    
    @abstractmethod
    def _load_content(self):
        """Load the content of the media file."""
        pass

class TextGroup(Media):
    """Text group media loaded from JSON files - implements protocol TEXT_BATCH format"""
    media_type: str = Field(default='text', const=True)
    
    # Protocol fields for TEXT_BATCH message
    bg_color: int = Field(default=0x0000, description="Background color (16-bit RGB565)")
    font_color: int = Field(default=0xFFFF, description="Font color (16-bit RGB565)")
    texts: List[Tuple[int, int, int, str]] = Field(default_factory=list, description="List of (x, y, font_id, text) tuples")
    
    @validator('file_path')
    def validate_json_file(cls, v):
        if not v.endswith(".json"):
            raise ValueError("TextGroup file must be a .json file")
        return v
    
    @validator('texts')
    def validate_text_strings(cls, v):
        """Validate that text strings don't exceed 255 bytes when UTF-8 encoded"""
        for x, y, font_id, text in v:
            text_bytes = text.encode('utf-8')
            if len(text_bytes) > 255:
                raise ValueError(f"Text string too long (max 255 bytes): '{text[:50]}...'")
        return v
    
    def _load_content(self):
        with open(self.file_path, 'r', encoding='utf-8') as f:
            payload = json.load(f)
            
            # Load protocol-required fields from JSON
            self.bg_color = payload.get('bg_color', 0x0000)
            self.font_color = payload.get('font_color', 0xFFFF)
            
            # Load text entries - expect array of objects with x, y, font_id, text
            texts_data = payload.get('texts', [])
            self.texts = []
            
            for text_entry in texts_data:
                if isinstance(text_entry, dict):
                    x = text_entry.get('x', 0)
                    y = text_entry.get('y', 0) 
                    font_id = text_entry.get('font_id', 0)
                    text = text_entry.get('text', '')
                    self.texts.append((x, y, font_id, text))
                elif isinstance(text_entry, (list, tuple)) and len(text_entry) >= 4:
                    self.texts.append(tuple(text_entry[:4]))
                else:
                    raise ValueError(f"Invalid text entry format: {text_entry}")
            
            return payload

class OptionGroup(TextGroup):
    """Virtual text group with predefined content"""
    
    def __init__(self,
        file_path: str,
        bg_color: int = 0x0000,
        font_color: int = 0xFFFF, 
        texts: List[Tuple[int, int, int, str]] = None,
        **data
    ):
        # Set the content before calling parent init
        self._predefined_content = {
            'bg_color': bg_color,
            'font_color': font_color,
            'texts': texts or []
        }
        super().__init__(file_path=file_path, **data)

    def _load_content(self):
        # Load from predefined content instead of file
        self.bg_color = self._predefined_content['bg_color']
        self.font_color = self._predefined_content['font_color']
        self.texts = self._predefined_content['texts']
        return self._predefined_content


class Image(Media):
    """Image media with protocol-compliant metadata - implements IMAGE_TRANSFER_START format"""
    media_type: str = Field(default='image', const=True)
    
    # Protocol fields for IMAGE_TRANSFER_START message
    image_id: int = Field(default=0, description="Image ID (0-255)")
    image_format: ImageFormat = Field(default=ImageFormat.JPEG, description="Image format")
    resolution: ImageResolution = Field(default=ImageResolution.RES_480x480, description="Image resolution")
    delay_time: int = Field(default=0, description="Delay time in ms (0-255)")
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
        if not 0 <= v <= 255:
            raise ValueError("Delay time must be between 0 and 255 ms")
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
        self.num_chunks = self._calculate_chunks(len(content))
        
        return content

    def _load_metadata(self):
        """Get the file type and dimensions, validate against protocol requirements"""
        from PIL import Image as PILImage
        img = PILImage.open(self.file_path)
        
        # Map PIL format to protocol format
        format_mapping = {
            'JPEG': ImageFormat.JPEG,
            'PNG': ImageFormat.PNG,
            'BMP': ImageFormat.BMP
        }
        
        self.image_format = format_mapping.get(img.format, ImageFormat.JPEG)
        self.dimensions = img.size
        
        # Validate and set resolution based on dimensions
        if self.dimensions == (480, 480):
            self.resolution = ImageResolution.RES_480x480
        elif self.dimensions == (240, 240):
            self.resolution = ImageResolution.RES_240x240
        elif self.dimensions == (320, 240):
            self.resolution = ImageResolution.RES_320x240
        elif self.dimensions == (640, 480):
            self.resolution = ImageResolution.RES_640x480
        else:
            raise ValueError(f"Unsupported image dimensions: {self.dimensions}. "
                           f"Must be 480x480, 240x240, 320x240, or 640x480")
    
    def _calculate_chunks(self, total_size: int, chunk_size: int = 2048) -> int:
        """Calculate number of chunks needed for transfer"""
        return (total_size + chunk_size - 1) // chunk_size  # Ceiling division


class MotionPicture(Media):
    """Motion picture (animated) media from frame directories - implements multi-frame IMAGE transfer"""
    media_type: str = Field(default='motion_picture', const=True)
    
    # Protocol fields - similar to Image but for multiple frames
    image_id: int = Field(default=0, description="Starting image ID for sequence")
    image_format: ImageFormat = Field(default=ImageFormat.JPEG, description="Format of frame images")
    resolution: ImageResolution = Field(default=ImageResolution.RES_480x480, description="Resolution of frames")
    delay_time: int = Field(default=100, description="Frame delay in ms (0-255)")
    
    # Motion picture specific fields
    frames_data: List[bytes] = Field(default_factory=list, description="Frame image data")
    frame_count: int = Field(default=0, description="Number of frames")
    total_duration: int = Field(default=0, description="Total animation duration in ms")
    
    @validator('file_path')
    def validate_gif_directory(cls, v):
        if not v.endswith('.gif.d'):
            raise ValueError("MotionPicture file must be a .gif.d directory")
        return v
    
    @validator('image_id')
    def validate_image_id(cls, v):
        if not 0 <= v <= 255:
            raise ValueError("Image ID must be between 0 and 255")
        return v
    
    @validator('delay_time')
    def validate_delay_time(cls, v):
        if not 0 <= v <= 255:
            raise ValueError("Delay time must be between 0 and 255 ms")
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
        
        # Set motion picture metadata
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
        import tempfile
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
                self.resolution = ImageResolution.RES_480x480
            elif dimensions == (240, 240):
                self.resolution = ImageResolution.RES_240x240
            elif dimensions == (320, 240):
                self.resolution = ImageResolution.RES_320x240
            elif dimensions == (640, 480):
                self.resolution = ImageResolution.RES_640x480
            else:
                raise ValueError(f"Unsupported frame dimensions: {dimensions}. "
                               f"Must be 480x480, 240x240, 320x240, or 640x480")
        finally:
            os.unlink(temp_path)
    
    def frames(self):
        """Iterator for frames"""
        for frame in self.frames_data:
            yield frame
    
    def get_frame_metadata(self, frame_index: int) -> dict:
        """Get protocol metadata for a specific frame"""
        if not 0 <= frame_index < len(self.frames_data):
            raise IndexError(f"Frame index {frame_index} out of range")
        
        frame_data = self.frames_data[frame_index]
        return {
            'image_id': self.image_id + frame_index,
            'image_format': self.image_format,
            'resolution': self.resolution,
            'delay_time': self.delay_time,
            'total_size': len(frame_data),
            'num_chunks': (len(frame_data) + 2047) // 2048  # Ceiling division for 2KB chunks
        }
