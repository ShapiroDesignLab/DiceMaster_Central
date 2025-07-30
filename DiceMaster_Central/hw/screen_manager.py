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
from typing import Dict, Optional, Tuple, List



from DiceMaster_Central.hw.spi_device import SPIDevice

from DiceMaster_Central.config.constants import (
    NOBUS, PING_CMD, TXT_CMD, IMG_CMD, OPT_CMD, OPT_END, RES_CMD, HYB_CMD,
    SCREEN_BOOT_DELAY, SCREEN_PING_INTERNVAL, HYB_SLEEP_TIME, WORK_SLEEP_TIME,
)
from DiceMaster_Central.media.protocol import (
    ProtocolMessage, TextMessage, ImageStartMessage, ImageChunkMessage, 
    ImageEndMessage, GIFStartMessage, GIFFrameMessage, GIFEndMessage,
    OptionMessage, split_image_into_chunks
)
from DiceMaster_Central.data_types.media_types import VirtualTextGroup, TextGroup, Image as MediaImage, MotionPicture


class ScreenSPIManager:
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

    def _get_next_request_id(self) -> int:
        """Get next request ID"""
        self.request_id_counter = (self.request_id_counter + 1) % 65536
        return self.request_id_counter

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

class ScreenManager:
    def __init__(
        self, 
        node,
        spi_config: Dict,
    ):
        self.spi_config = spi_config
        self.node = node
        self.screen_spi_managers = {
            0: ScreenSPIManager(spi_config),
            1: ScreenSPIManager(spi_config),  # Example for multiple SPI managers
            2: ScreenSPIManager(spi_config)  # Add more as needed
        }
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

    def _get_manager_for_screen(self, screen_id: int) -> ScreenSPIManager:
        """Get the SPI manager for a given screen ID"""
        return self.screen_spi_managers[screen_id // NUM_DEV_PER_SPI_CTRL]

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

    def queue_request(self, request: ScreenRequest) -> int:
        """Queue a screen request for processing"""
        request_id = self._get_next_request_id()
        request.request_id = request_id
        self.request_queue.put(request)
        return request_id