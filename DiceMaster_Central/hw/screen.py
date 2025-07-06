"""
U-M Shapiro Design Lab
Daniel Hou @2024

This module handles communication with peripheral ESP32 boards through a chosen interface.

Protocols: see https://docs.google.com/document/d/1ovbKFz1-aYnTLMupWtqQHsDRdrbPbAs7edm_ehnVuko
"""

import time
from time import sleep
from queue import Queue
import threading
import os
from abc import abstractmethod
from typing import Dict, Optional, Tuple, List
from dataclasses import dataclass
from enum import Enum

import spidev
import rclpy
from rclpy.node import Node
from rclpy.service import Service
from std_srvs.srv import Empty
from std_msgs.msg import String, Int32
from geometry_msgs.msg import Vector3
import tf2_ros
import tf2_geometry_msgs
import numpy as np
from PIL import Image, ImageFont

from DiceMaster_Central.config.constants import (
    NOBUS, PING_CMD, TXT_CMD, IMG_CMD, OPT_CMD, OPT_END, RES_CMD, HYB_CMD,
    SCREEN_BOOT_DELAY, SCREEN_PING_INTERNVAL, HYB_SLEEP_TIME, WORK_SLEEP_TIME,
    NUM_SCREEN, NUM_SPI_CTRL, NUM_DEV_PER_SPI_CTRL, IMG_RES_240SQ, 
    IMG_RES_480SQ, CHUNK_SIZE, MAX_TEXT_LEN, TXT_CMD, FONT_SIZE, 
    TEXT_PADDING, SCREEN_WIDTH, BYTE_SIZE, USING_ORIENTED_SCREENS,
    MessageType, ImageFormat, ImageResolution, Rotation,
    IMG_EXTS, VID_EXTS, TXT_EXTS
)
from DiceMaster_Central.media.protocol import (
    ProtocolMessage, TextMessage, ImageStartMessage, ImageChunkMessage, 
    ImageEndMessage, GIFStartMessage, GIFFrameMessage, GIFEndMessage,
    OptionMessage, split_image_into_chunks
)
from DiceMaster_Central.data_types.media_types import VirtualTextGroup


# Service message types
class ContentType(Enum):
    TEXT = "text"
    IMAGE = "image"
    GIF = "gif"
    OPTION = "option"

@dataclass
class ScreenRequest:
    """Request to display content on a screen"""
    screen_id: int
    content_type: ContentType
    request_id: int
    
    # Text-specific fields
    text_content: Optional[str] = None
    bg_color: Optional[int] = None
    font_color: Optional[int] = None
    text_positions: Optional[List[Tuple[int, int, int, str]]] = None
    
    # Virtual text group for notifications and programmatic text
    virtual_text_group: Optional['VirtualTextGroup'] = None
    
    # File-based content fields
    file_path: Optional[str] = None
    file_data: Optional[bytes] = None
    
    # Image/GIF specific fields
    resolution: Optional[ImageResolution] = None
    delay_time: Optional[int] = None
    
    # Option-specific fields
    options: Optional[List[str]] = None
    selected_option: Optional[int] = None

@dataclass
class ScreenResponse:
    """Response from screen service"""
    success: bool
    request_id: int
    error_message: Optional[str] = None


class VirtualSPIDevice:
    """SPI Device for Screen communication"""
    def __init__(self,
        spi_id: int,
        bus_id: int,
        bus_dev_id: int,
        verbose=False
    ):
        self.id = spi_id
        self.bus = bus_id
        self.dev = bus_dev_id
        self.awake = False
        self.spi = None
        self.verbose = verbose

    def __del__(self):
        self.down()

    def up(self):
        """select device"""
        if self.awake:
            return
        self.awake = True
        if self.spi is not None:
            self.spi.open(self.bus, self.dev)

    def down(self):
        """close spi connection"""
        self.awake = False
        if self.spi is not None:
            self.spi.close()

    def is_awake(self):
        """See if bus is awake,  usually unnecessary"""
        return self.awake

    @abstractmethod
    def send(self, msg):
        """send and return received content"""
        raise NotImplementedError("This is a virtual SPI device, no actual communication will occur.")

class SPIDevice(VirtualSPIDevice):
    """SPI Device for Screen communication"""
    def __init__(self,
        spi_id: int,
        bus_id: int,
        bus_dev_id: int,
        spi_config: Dict,
        verbose=False
    ):
        super().__init__(spi_id, bus_id, bus_dev_id, verbose)

        # Create instance from config
        self.spi = spidev.SpiDev()
        # Open, configure, and close
        self.spi.open(self.bus, self.dev)
        self.spi.max_speed_hz = spi_config.get("max_speed_hz", 96000)
        self.spi.mode = spi_config.get("mode", 0b00)          # Set SPI Mode to 0
        self.spi.threewire = spi_config.get("threewire", False)  # Set three-wire mode if needed
        self.spi.close()

    def send(self, msg):
        """send and return received content"""
        assert self.awake
        if self.verbose:
            print(f"Written {len(msg)}")
            print(f"Sent {msg}")
        self.spi.writebytes(msg)           # Send the chunk


class ScreenManager:
    """
    Class that manages SPI devices and coordinates communication between screens.
    Merged functionality from Bus class to ensure proper SPI bus management.
    """
    def __init__(self, spi_config: Dict):
        self.spi_config = spi_config
        self.screens = {}
        self.spi_devices = {}
        
        # Communication queue and management
        self.send_jobs = Queue()
        self.last_spi_dev = None
        self.running = False
        self.ping_devs = []
        self.next_ping_time = time.monotonic()
        self.fixed_msgs = self._build_reused_msgs()
        
        # Communication thread
        self.comm_thread = threading.Thread(target=self._comm_worker)
        
        # Request management
        self.request_queue = Queue()
        self.request_id_counter = 0
        self.pending_responses = {}
        
        # Processing thread
        self.processing_thread = threading.Thread(target=self._processing_worker)

    def __del__(self):
        """stop communications"""
        self.running = False
        if hasattr(self, 'comm_thread'):
            self.comm_thread.join()
        if hasattr(self, 'processing_thread'):
            self.processing_thread.join()
        for dev in self.ping_devs:
            dev.down()

    def _build_reused_msgs(self):
        """Build commonly reused messages"""
        # Implementation depends on your protocol
        return {
            'ping': [0x01],  # Ping command
            'hibernate': [0x02],  # Hibernate command
            'wake': [0x03]  # Wake command
        }

    def create_spi_device(self, screen_id: int, bus_num: int, dev_num: int) -> SPIDevice:
        """Create and register an SPI device"""
        if NOBUS:
            device = VirtualSPIDevice(screen_id, bus_num, dev_num, verbose=True)
        else:
            device = SPIDevice(screen_id, bus_num, dev_num, self.spi_config, verbose=True)
        
        self.spi_devices[screen_id] = device
        self.ping_devs.append(device)
        return device

    def register_screen(self, screen_node):
        """Register a screen node with the manager"""
        self.screens[screen_node.screen_id] = screen_node

    def start(self):
        """Start the manager's communication and processing threads"""
        self.next_ping_time = time.monotonic() + SCREEN_BOOT_DELAY
        self.running = True
        self.comm_thread.start()
        self.processing_thread.start()

    def stop(self):
        """Stop the manager"""
        self.running = False

    def queue_message(self, spi_device: SPIDevice, command: int, msg: List[int]):
        """
        Queue message to send (not in a hurry by default)
        msg = (spi dev, command, msg)
        """
        padded_msg = msg.copy()
        pad_len = (4 - (len(padded_msg) % 4)) % 4
        padded_msg.extend([0] * pad_len)
        self.send_jobs.put((spi_device, command, padded_msg))

    def queue_request(self, request: ScreenRequest) -> int:
        """Queue a screen request for processing"""
        request_id = self._get_next_request_id()
        request.request_id = request_id
        self.request_queue.put(request)
        return request_id

    def get_response(self, request_id: int) -> Optional[ScreenResponse]:
        """Get response for a request ID"""
        return self.pending_responses.get(request_id)

    def _get_next_request_id(self) -> int:
        """Get next request ID"""
        self.request_id_counter = (self.request_id_counter + 1) % 65536
        return self.request_id_counter

    def _comm_worker(self):
        """Communication worker thread - handles SPI communication"""
        while True:
            if not self.running and self.send_jobs.empty():
                sleep(HYB_SLEEP_TIME)
                continue

            # Check if any jobs
            if self.send_jobs.empty():
                sleep(WORK_SLEEP_TIME)
                continue

            # Retrieve message from queue
            msg = self.send_jobs.get()
            spi_device, command, msg_data = msg
            
            # If different device, shutdown and open another spi dev
            if self.last_spi_dev is not None and self.last_spi_dev != spi_device:
                self.last_spi_dev.down()
                sleep(0.001)
            
            spi_device.up()
            self.last_spi_dev = spi_device

            # Actually send message
            spi_device.send(msg_data)
            print(f"Sent message with length {len(msg_data)}")
            time.sleep(0.009)

    def _processing_worker(self):
        """Processing worker thread - handles screen requests"""
        while True:
            if not self.running and self.request_queue.empty():
                sleep(0.1)
                continue

            # Check if any requests
            if self.request_queue.empty():
                sleep(0.05)
                continue

            # Retrieve request from queue
            request = self.request_queue.get()
            
            # Process the request
            try:
                response = self._process_request(request)
                self.pending_responses[request.request_id] = response
            except Exception as e:
                error_response = ScreenResponse(
                    success=False,
                    request_id=request.request_id,
                    error_message=str(e)
                )
                self.pending_responses[request.request_id] = error_response

    def _process_request(self, request: ScreenRequest) -> ScreenResponse:
        """Process a screen request"""
        screen_node = self.screens.get(request.screen_id)
        if not screen_node:
            return ScreenResponse(
                success=False,
                request_id=request.request_id,
                error_message=f"Screen {request.screen_id} not found"
            )

        # Delegate to screen node's process method
        return screen_node.process(request)

    # Hibernate/Wake Functions
    def hibernate(self):
        """Put all ESP32 screens to hibernation"""
        for dev in self.ping_devs:
            self.queue_message(dev, HYB_CMD, self.fixed_msgs['hibernate'])
        self.running = False

    def wake(self):
        """Wake up all ESP32 screens and verify connection"""
        self.running = True
        for dev in self.ping_devs:
            self.queue_message(dev, RES_CMD, self.fixed_msgs['wake'])

class VirtualScreen(Node):
    """Virtual Screen Node for testing purposes"""
    def __init__(self, 
        screen_id: int, 
        manager: ScreenManager
    ):
        super().__init__(f'virtual_screen_{screen_id}_node')
        self.screen_id = screen_id
        self.manager = manager
        self.get_logger().info(f'Virtual Screen {screen_id} initialized')

    def process(self, request: ScreenRequest) -> ScreenResponse:
        """Process a screen request (virtual implementation)"""
        self.get_logger().info(f'Virtual screen {self.screen_id} processing {request.content_type} request')
        return ScreenResponse(success=True, request_id=request.request_id)

class ScreenNode(Node):
    """
    ROS2 Screen Node that handles SPI communication and auto-rotation for a single screen.
    Each screen is spawned as a separate node with a unique ID.

    Screen node provides services for:
    1. Display text content
    2. Display image files  
    3. Display GIF files
    4. Display option menus
    5. Query request status
    """
    def __init__(self, 
        screen_id: int, 
        bus_num: int, 
        dev_num: int, 
        manager: ScreenManager,
        auto_rotate: bool = True, 
        rotation_margin: float = 0.2
    ):
        super().__init__(f'screen_{screen_id}_node')

        # Basic properties
        self.screen_id = screen_id
        self.bus_num = bus_num
        self.dev_num = dev_num
        self.manager = manager
        self.auto_rotate = auto_rotate
        self.rotation_margin = rotation_margin
        self.current_rotation = Rotation.ROTATION_0
        
        # Content management
        self.last_content = None
        self.last_content_type = None
        
        # SPI Communication setup
        self.spi_device = manager.create_spi_device(screen_id, bus_num, dev_num)
        manager.register_screen(self)
        
        # Message ID counter
        self._msg_id_counter = 0
        
        # Create ROS services
        self._create_services()
        
        # TF2 setup for orientation tracking (if auto-rotate enabled)
        if self.auto_rotate:
            self.tf_buffer = tf2_ros.Buffer()
            self.tf_listener = tf2_ros.TransformListener(self.tf_buffer, self)
            
            # Screen edge frame names for orientation detection
            self.edge_frames = [
                f'screen_{screen_id}_edge_top',
                f'screen_{screen_id}_edge_right', 
                f'screen_{screen_id}_edge_bottom',
                f'screen_{screen_id}_edge_left'
            ]
            
            # Timer for orientation checking
            self.orientation_timer = self.create_timer(0.1, self.check_orientation)
        
        self.get_logger().info(f'Screen {screen_id} node initialized on bus {bus_num}, device {dev_num}')

    def _create_services(self):
        """Create ROS services for the screen"""
        # Service for displaying text
        self.text_service = self.create_service(
            String,  # Using String for simplicity - in practice you'd create custom service types
            f'screen_{self.screen_id}/display_text',
            self._handle_text_service
        )
        
        # Service for displaying images
        self.image_service = self.create_service(
            String,
            f'screen_{self.screen_id}/display_image',
            self._handle_image_service
        )
        
        # Service for displaying GIFs
        self.gif_service = self.create_service(
            String,
            f'screen_{self.screen_id}/display_gif',
            self._handle_gif_service
        )
        
        # Service for displaying options
        self.option_service = self.create_service(
            String,
            f'screen_{self.screen_id}/display_options',
            self._handle_option_service
        )
        
        # Service for querying request status
        self.status_service = self.create_service(
            Int32,
            f'screen_{self.screen_id}/get_status',
            self._handle_status_service
        )

    def _handle_text_service(self, request, response):
        """Handle text display service request"""
        try:
            # Parse request (in practice, use proper service message types)
            text_content = request.data
            
            screen_request = ScreenRequest(
                screen_id=self.screen_id,
                content_type=ContentType.TEXT,
                request_id=0,  # Will be set by manager
                text_content=text_content,
                bg_color=0x000000,  # Default black background
                font_color=0xFFFFFF  # Default white text
            )
            
            request_id = self.manager.queue_request(screen_request)
            response.data = str(request_id)
            
        except Exception as e:
            self.get_logger().error(f'Error handling text service: {str(e)}')
            response.data = "-1"
            
        return response

    def _handle_image_service(self, request, response):
        """Handle image display service request"""
        try:
            file_path = request.data
            
            # Validate file exists and is an image
            if not os.path.exists(file_path):
                raise ValueError(f"File not found: {file_path}")
                
            file_ext = os.path.splitext(file_path)[1][1:].lower()
            if file_ext not in IMG_EXTS:
                raise ValueError(f"Unsupported image format: {file_ext}")
            
            screen_request = ScreenRequest(
                screen_id=self.screen_id,
                content_type=ContentType.IMAGE,
                request_id=0,
                file_path=file_path,
                resolution=ImageResolution.RES_480x480
            )
            
            request_id = self.manager.queue_request(screen_request)
            response.data = str(request_id)
            
        except Exception as e:
            self.get_logger().error(f'Error handling image service: {str(e)}')
            response.data = "-1"
            
        return response

    def _handle_gif_service(self, request, response):
        """Handle GIF display service request"""
        try:
            file_path = request.data
            
            # Validate file exists and is a GIF/video
            if not os.path.exists(file_path):
                raise ValueError(f"File not found: {file_path}")
                
            file_ext = os.path.splitext(file_path)[1][1:].lower()
            if file_ext not in VID_EXTS + ['gif']:
                raise ValueError(f"Unsupported video/GIF format: {file_ext}")
            
            screen_request = ScreenRequest(
                screen_id=self.screen_id,
                content_type=ContentType.GIF,
                request_id=0,
                file_path=file_path,
                resolution=ImageResolution.RES_480x480
            )
            
            request_id = self.manager.queue_request(screen_request)
            response.data = str(request_id)
            
        except Exception as e:
            self.get_logger().error(f'Error handling GIF service: {str(e)}')
            response.data = "-1"
            
        return response

    def _handle_option_service(self, request, response):
        """Handle option display service request"""
        try:
            # Parse options from request data (format: "option1,option2,option3")
            options = request.data.split(',')
            
            screen_request = ScreenRequest(
                screen_id=self.screen_id,
                content_type=ContentType.OPTION,
                request_id=0,
                options=options
            )
            
            request_id = self.manager.queue_request(screen_request)
            response.data = str(request_id)
            
        except Exception as e:
            self.get_logger().error(f'Error handling option service: {str(e)}')
            response.data = "-1"
            
        return response

    def _handle_status_service(self, request, response):
        """Handle status query service request"""
        try:
            request_id = request.data
            screen_response = self.manager.get_response(request_id)
            
            if screen_response:
                response.data = 1 if screen_response.success else 0
            else:
                response.data = -1  # Request not found or still processing
                
        except Exception as e:
            self.get_logger().error(f'Error handling status service: {str(e)}')
            response.data = -1
            
        return response

    @property
    def _next_msg_id(self) -> int:
        """Get next message ID for protocol"""
        self._msg_id_counter = (self._msg_id_counter + 1) % 256
        return self._msg_id_counter

    def process(self, request: ScreenRequest) -> ScreenResponse:
        """
        Process a screen request. Called by ScreenManager.
        Routes the request to the appropriate processing function.
        """
        try:
            if request.content_type == ContentType.TEXT:
                return self._process_text_request(request)
            elif request.content_type == ContentType.IMAGE:
                return self._process_image_request(request)
            elif request.content_type == ContentType.GIF:
                return self._process_gif_request(request)
            elif request.content_type == ContentType.OPTION:
                return self._process_option_request(request)
            else:
                return ScreenResponse(
                    success=False,
                    request_id=request.request_id,
                    error_message=f"Unsupported content type: {request.content_type}"
                )
                
        except Exception as e:
            return ScreenResponse(
                success=False,
                request_id=request.request_id,
                error_message=str(e)
            )

    def _process_text_request(self, request: ScreenRequest) -> ScreenResponse:
        """Process text display request"""
        try:
            # Check if this is a VirtualTextGroup (for notifications) or regular text
            if request.virtual_text_group:
                # Handle VirtualTextGroup (notifications)
                vtg = request.virtual_text_group
                
                # Store content for potential re-rotation
                self.last_content = {
                    'bg_color': vtg.bg_color,
                    'font_color': vtg.font_color,
                    'texts': vtg.texts,
                    'virtual': True
                }
                self.last_content_type = 'virtual_text'
                
                # Create text message using VirtualTextGroup data
                text_msg = TextMessage(msg_id=self._next_msg_id)
                text_msg.add_text_group(
                    vtg.bg_color,
                    vtg.font_color,
                    vtg.texts,
                    self.current_rotation
                )
                
            else:
                # Handle regular text content
                # Store content for potential re-rotation
                self.last_content = {
                    'bg_color': request.bg_color or 0x000000,
                    'font_color': request.font_color or 0xFFFFFF,
                    'text': request.text_content
                }
                self.last_content_type = 'text'
                
                # Create text message
                text_msg = TextMessage(msg_id=self._next_msg_id)
                
                # Format text for display (simple centering for now)
                texts = [(SCREEN_WIDTH//2, SCREEN_WIDTH//2, FONT_SIZE, request.text_content)]
                text_msg.add_text_group(
                    request.bg_color or 0x000000,
                    request.font_color or 0xFFFFFF,
                    texts,
                    self.current_rotation
                )
            
            # Send via manager
            msg_bytes = text_msg.build_message()
            msg_list = list(msg_bytes)
            self.manager.queue_message(self.spi_device, TXT_CMD, msg_list)
            
            self.get_logger().debug(f'Sent text to screen {self.screen_id}')
            
            return ScreenResponse(success=True, request_id=request.request_id)
            
        except Exception as e:
            return ScreenResponse(
                success=False,
                request_id=request.request_id,
                error_message=str(e)
            )

    def _process_image_request(self, request: ScreenRequest) -> ScreenResponse:
        """Process image display request"""
        try:
            # Load image file
            with open(request.file_path, 'rb') as f:
                image_data = f.read()
            
            # Store content for potential re-rotation
            self.last_content = {
                'data': image_data,
                'resolution': request.resolution or ImageResolution.RES_480x480,
                'delay': request.delay_time or 0
            }
            self.last_content_type = 'image'
            
            # Split image into chunks
            chunks = split_image_into_chunks(image_data, CHUNK_SIZE)
            
            # Send image start message
            start_msg = ImageStartMessage(
                image_id=self.screen_id,
                image_format=ImageFormat.JPEG,  # Determine based on file extension
                resolution=request.resolution or ImageResolution.RES_480x480,
                delay_time=request.delay_time or 0,
                total_size=len(image_data),
                num_chunks=len(chunks),
                rotation=self.current_rotation,
                msg_id=self._next_msg_id
            )
            
            start_msg_bytes = start_msg.build_message()
            self.manager.queue_message(self.spi_device, IMG_CMD, list(start_msg_bytes))
            
            # Send image chunks
            for chunk_id, start_location, chunk_data in chunks:
                chunk_msg = ImageChunkMessage(
                    image_id=self.screen_id,
                    chunk_id=chunk_id,
                    start_location=start_location,
                    chunk_data=chunk_data,
                    msg_id=self._next_msg_id
                )
                chunk_msg_bytes = chunk_msg.build_message()
                self.manager.queue_message(self.spi_device, IMG_CMD, list(chunk_msg_bytes))
            
            # Send image end message
            end_msg = ImageEndMessage(
                image_id=self.screen_id,
                msg_id=self._next_msg_id
            )
            end_msg_bytes = end_msg.build_message()
            self.manager.queue_message(self.spi_device, IMG_CMD, list(end_msg_bytes))
            
            self.get_logger().debug(f'Sent image to screen {self.screen_id}')
            
            return ScreenResponse(success=True, request_id=request.request_id)
            
        except Exception as e:
            return ScreenResponse(
                success=False,
                request_id=request.request_id,
                error_message=str(e)
            )

    def _process_gif_request(self, request: ScreenRequest) -> ScreenResponse:
        """Process GIF display request"""
        try:
            # Load and process GIF file
            # For now, treat as single image - full GIF support would require frame extraction
            with open(request.file_path, 'rb') as f:
                gif_data = f.read()
            
            # Store content for potential re-rotation
            self.last_content = {
                'data': gif_data,
                'resolution': request.resolution or ImageResolution.RES_480x480
            }
            self.last_content_type = 'gif'
            
            # Send as GIF start message
            gif_start_msg = GIFStartMessage(
                image_id=self.screen_id,
                image_format=ImageFormat.JPEG,  # Determine based on file extension
                resolution=request.resolution or ImageResolution.RES_480x480,
                delay_time=100,  # Default delay for GIF frames
                total_size=len(gif_data),
                num_chunks=1,  # Simplified for now
                rotation=self.current_rotation,
                msg_id=self._next_msg_id
            )
            
            gif_msg_bytes = gif_start_msg.build_message()
            self.manager.queue_message(self.spi_device, IMG_CMD, list(gif_msg_bytes))
            
            self.get_logger().debug(f'Sent GIF to screen {self.screen_id}')
            
            return ScreenResponse(success=True, request_id=request.request_id)
            
        except Exception as e:
            return ScreenResponse(
                success=False,
                request_id=request.request_id,
                error_message=str(e)
            )

    def _process_option_request(self, request: ScreenRequest) -> ScreenResponse:
        """Process option display request"""
        try:
            # Store content for potential re-rotation
            self.last_content = {
                'options': request.options,
                'selected': request.selected_option or 0
            }
            self.last_content_type = 'option'
            
            # Create option message
            option_msg = OptionMessage(
                options=request.options,
                selected_option=request.selected_option or 0,
                rotation=self.current_rotation,
                msg_id=self._next_msg_id
            )
            
            option_msg_bytes = option_msg.build_message()
            self.manager.queue_message(self.spi_device, OPT_CMD, list(option_msg_bytes))
            
            self.get_logger().debug(f'Sent options to screen {self.screen_id}')
            
            return ScreenResponse(success=True, request_id=request.request_id)
            
        except Exception as e:
            return ScreenResponse(
                success=False,
                request_id=request.request_id,
                error_message=str(e)
            )

    def check_orientation(self):
        """Check current orientation and trigger rotation if needed"""
        if not self.auto_rotate:
            return
            
        try:
            # Get transform from base_link to each edge frame
            edge_vectors = []
            
            for edge_frame in self.edge_frames:
                try:
                    transform = self.tf_buffer.lookup_transform(
                        'base_link', edge_frame, rclpy.time.Time())
                    
                    # Extract the position vector
                    edge_pos = np.array([
                        transform.transform.translation.x,
                        transform.transform.translation.y,
                        transform.transform.translation.z
                    ])
                    edge_vectors.append(edge_pos)
                    
                except (tf2_ros.LookupException, tf2_ros.ExtrapolationException):
                    return  # Data not available yet
                    
            if len(edge_vectors) != 4:
                return
                
            # Determine which edge is most "up" (highest Z component)
            z_components = [vec[2] for vec in edge_vectors]
            max_z_idx = np.argmax(z_components)
            max_z_value = z_components[max_z_idx]
            
            # Check if this edge is significantly more "up" than current top
            current_top_idx = (4 - self.current_rotation) % 4
            current_top_z = z_components[current_top_idx]
            
            # If the highest edge is different and exceeds margin, rotate
            if (max_z_idx != current_top_idx and 
                max_z_value - current_top_z > self.rotation_margin):
                
                # Calculate required rotation
                new_rotation = Rotation((4 - max_z_idx) % 4)
                
                if new_rotation != self.current_rotation:
                    self.get_logger().info(f'Auto-rotating screen {self.screen_id} from {self.current_rotation} to {new_rotation}')
                    self.current_rotation = new_rotation
                    
                    # Re-send last content with new rotation
                    if self.last_content is not None:
                        self._resend_with_rotation()
                        
        except Exception as e:
            self.get_logger().warn(f'Error in orientation check: {str(e)}')

    def _resend_with_rotation(self):
        """Re-send the last content with current rotation"""
        if self.last_content is None:
            return
            
        # Create a new request with updated rotation and resend
        if self.last_content_type == 'text':
            request = ScreenRequest(
                screen_id=self.screen_id,
                content_type=ContentType.TEXT,
                request_id=self._next_msg_id,
                text_content=self.last_content['text'],
                bg_color=self.last_content['bg_color'],
                font_color=self.last_content['font_color']
            )
            self._process_text_request(request)
        elif self.last_content_type == 'image':
            # For images, we'd need to store the file path or recreate the request
            pass  # Implementation depends on how you want to handle re-rotation

    def set_auto_rotate(self, enabled: bool):
        """Enable or disable auto-rotation"""
        self.auto_rotate = enabled
        if enabled and not hasattr(self, 'orientation_timer'):
            self.orientation_timer = self.create_timer(0.1, self.check_orientation)
        elif not enabled and hasattr(self, 'orientation_timer'):
            self.orientation_timer.cancel()
            delattr(self, 'orientation_timer')

    def set_rotation(self, rotation: Rotation):
        """Manually set screen rotation (disables auto-rotate)"""
        self.set_auto_rotate(False)
        old_rotation = self.current_rotation
        self.current_rotation = rotation
        
        if old_rotation != rotation and self.last_content is not None:
            self._resend_with_rotation()
            
        self.get_logger().info(f'Manually set screen {self.screen_id} rotation to {rotation}')

    def destroy_node(self):
        """Clean shutdown"""
        if hasattr(self, 'orientation_timer'):
            self.orientation_timer.cancel()
        super().destroy_node()


class ScreenManager:
    """
    Class that reads configuration and spawns the appropriate screen nodes.
    Merged functionality from Bus class to ensure proper SPI bus management.
    """
    def __init__(self, spi_config: Dict = None):
        if spi_config is None:
            spi_config = {
                "max_speed_hz": 96000,
                "mode": 0b00,
                "threewire": False
            }
        
        self.spi_config = spi_config
        self.screens = {}
        self.spi_devices = {}
        
        # Communication queue and management
        self.send_jobs = Queue()
        self.last_spi_dev = None
        self.running = False
        self.ping_devs = []
        self.next_ping_time = time.monotonic()
        self.fixed_msgs = self._build_reused_msgs()
        
        # Communication thread
        self.comm_thread = threading.Thread(target=self._comm_worker)
        
        # Request management
        self.request_queue = Queue()
        self.request_id_counter = 0
        self.pending_responses = {}
        
        # Processing thread
        self.processing_thread = threading.Thread(target=self._processing_worker)

    def create_screen_node(self, screen_id: int, bus_num: int, dev_num: int, 
                          auto_rotate: bool = True) -> ScreenNode:
        """Create and return a new screen node"""
        return ScreenNode(screen_id, bus_num, dev_num, self, auto_rotate)

    def start_all(self):
        """Start the manager and all screen nodes"""
        self.start()
        # Note: Individual screen nodes are managed by ROS2, not directly by the manager


if __name__ == "__main__":
    print("Error, calling module screen directly!")