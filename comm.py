"""
U-M Shapiro Design Lab
Daniel Hou @2024

This module handles communication with peripheral ESP32 boards through a chosen interface.

Protocols:

MOSI: 1024 Bytes (1kb buffer)
- byte 1: target device ID (1 - 6 for screens, 255 for broadcast)
- byte 2: command
    - 1: ping (backlight on, operation mode)
    - 3: draw text
    - 7: image chunk
    - 127: draw options
    - 255: sleep (backlight off)
- byte 3-4: length of message (actual length is len + 4)

- Later Bytes: content
    - image: 
        - 5th byte: image ID (local, no need to be unique across, as long as different between three consecutive images)
        - 6th byte: resolution + chunk ID + more chunks?
            - 0-63 for 480x480 chunks (no more than 64 chunks for sure)
            - 64 - 127 for 240x240 chunks
            - top bit for whether this is the last chunk
        - 7th byte: forced stay up time, milliseconds, 0 for unlimited (image)
        - 8th byte: parity data (sum of array mod 256)
        - 9th to len + 4-th byte: image chunk data
    - Video:
        - Same as image, with 7th byte for enforced frame time
    - Draw Text:
        - For Each text draw:
            - 5-6 byte: draw x cursor
            - 7-8 byte: draw y cursor
            - 9th byte: size of text
            - 10th byte: size of text chunk in utf-8
            - 11-th byte onward: text
            - NOTE: there could be multiple text draw calls in one API call, to take full advantage of 1kb buffer
            - NOTE: each text block can be NO LONGER THAN 255 BYTES
    - Draw Settings Menu Option:
        - 
    
    
MISO: 64 Bytes
- byte 1: target device ID (0 for host)
"""

IMG_RES_240SQ = 1
IMG_RES_480SQ = 0

BYTE_SIZE = 2**8

CHUNK_SIZE = 1016

import spidev
from time import time
import numpy as np

class SPI4ESP:
    def __init__(self, id, bus, dev):
        self.ESP_ID = id
        self.bus = bus
        self.dev = dev
        self.spi = spidev.SpiDev()
        self.spi.open(bus, dev)
        self.last_ping = time.now()
        self.last_img_id = 0

    @staticmethod
    def send(content):
        pass

    def transfer_img(self, img_bytes, img_res=IMG_RES_480SQ):
        self.last_img_id = (self.last_img_id + 1) % 256
        chunks = SPI4ESP.make_img_chunks(img_bytes, CHUNK_SIZE, self.last_img_id, IMG_RES_480SQ)
        # We Need Async Implementation

    # For Images
    @staticmethod
    def make_img_chunks(img_bytearray, chunk_size, img_id, img_res=IMG_RES_480SQ):
        max_len = len(img_bytearray)
        chunk_id = 0
        chunks = []
        for start in range(0,max_len, chunk_size):
            # Get the chunk
            end = min(start+chunk_size, max_len)
            img_chunk = img_bytearray[start:end]

            # Build ID
            bit5 = 64*img_res + chunk_id + 128*(end==max_len)
            chunk = [img_id, bit5, parity]
            chunk_len = end - start
            parity = SPI4ESP.parity(chunk)

            # Append 0, after parity check
            if chunk_len < chunk_size:
                zeros = [0] * (chunk_size + start - end)
                img_chunk.append(zeros)
            chunk.extend(img_chunk)

            # Add to all chunks
            chunks.append(chunk)
            chunk_id += 1
        return chunks
    
    @staticmethod
    def parity(byte_chunk):
        
        return np.array(byte_chunk).sum() % BYTE_SIZE