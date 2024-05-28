"""
U-M Shapiro Design Lab
Daniel Hou @2024

This module handles communication with peripheral ESP32 boards through a chosen interface.

Protocols: see https://docs.google.com/document/d/1ovbKFz1-aYnTLMupWtqQHsDRdrbPbAs7edm_ehnVuko
"""

from time import time, sleep
from collections import deque
import threading
import numpy as np

from config import NOBUS, SCREEN_CFG, NUM_SCREEN
# if not NOBUS:
#     import spidev

# Image Macros
IMG_RES_240SQ = 1
IMG_RES_480SQ = 0

#        # SPI Configuration
BYTE_SIZE = 2**8
DUMMY_BUFFER_SIZE = 4
TOTAL_SPI_SEND_SIZE = 1024 + DUMMY_BUFFER_SIZE
CHUNK_SIZE = 1016       # Maimum 1016 bytes (excluding 8 byte header for image)
PING_INTERVAL = 5       # Interval for pinging screens, in seconds, default every 5 seconds
RECV_BYTES = 32         # Return messages are 32 bytes long.
WORK_SLEEP_TIME = 0.002  # 500Hz update frequency when running
HYB_SLEEP_TIME = 0.2    # 5 Hz update frequency when in hybernation

# Protocl Macros
PING_CMD = 1
IMG_CMD = 3
TXT_CMD = 7
OPT_CMD = 15
RES_CMD = 254
HYB_CMD = 255

ZERO_MSG = [0] * TOTAL_SPI_SEND_SIZE


class Screen:
    """
    This is the screen class handing communication and context to and from each screen
    """

    def __init__(self, id, bus, dev):
        self.id = id
        self.ping_msg, self.hyb_msg, self.restore_msg = self._build_reused_msgs()

        # SPI Config
        self.bus = bus
        self.dev = dev
        self.spi = SPIDummy(self.id)
        # if not NOBUS:
        #     self.spi = spidev.SpiDev()
        #     self.spi.max_speed_hz = 96e5  # Set speed to 9.6 Mhz
        #     self.spi.mode = 0b00          # Set SPI Mode to 0
        #     self.spi.threewire = True
        #     self.spi.open(bus, dev)
        self.awake = False

        # Background Job Config
        self.background_running = False
        self.send_jobs = deque()
        self.send_job_cnt = 0
        self.recv_msgs = deque()
        self.recv_msg_cnt = 0

        self.running = True
        self.thread = threading.Thread(target=self._comm)
        self.thread.start()

        # Ping Configuration
        self.last_ping = time.time()
        self.last_img_id = 0

        # Image Transfer Records
        self.img_transfer_record = {}

    # Generic Functions

    def _build_reused_msgs(self):
        # Empty Message with ID
        template = ZERO_MSG.copy()
        template[0] = self.id
        # Ping message could be reused
        ping_msg = template.copy()
        ping_msg[1] = 1
        # Hybernate message could be reused
        hyb_msg = template.copy()
        hyb_msg[1] = 255
        # Restore screen message could be reused
        restore_msg = template.copy()
        restore_msg[1] = 254
        return ping_msg, hyb_msg, restore_msg

    def build_msg(self, command, content):
        """Build a message body from command and content, calculates lengths, parity, etc"""
        assert (0 <= command and command <= 255)
        len_hibyte = len(content) // 256
        len_lobyte = len(content) % 256
        msg = [self.id, command, len(content), len_hibyte, len_lobyte]
        msg.extend(Screen.parity(msg, content))
        msg.extend(content)
        return msg

    @staticmethod
    def parity(header, content):
        """Computes parity of bytes, """
        return (np.array(header).sum() + np.array(content).sum()) % BYTE_SIZE

    # Queueing functions

    def queue_send(self, msg):
        """queue message to send (not in a hurry by default)"""
        self.send_jobs.append(msg)

    def send_now(self, content):
        """send as next immediate message, jumping the queue essentially"""
        self.send_jobs.appendleft(content)

    # Commands
    def ping(self):
        """Ping device periodically"""
        self.send_now(self.ping_msg)

    # Sleep Wake related tasks
    def hybernate(self):
        """Put ESP32 to hybernation"""
        self.send_now(self.hyb_msg)

    def wake(self):
        """
        Wake up ESP 32 screen and verify connection. 
        REQUIRE: All ESP32 must have been waken up by sytem before this function call
        """
        self.send_now(self.restore_msg)
        self.ping()

    # Image related functions
    def transfer_img(self, img_bytes, img_res=IMG_RES_480SQ, frame_time=0):
        """given an image in bytes, transfer the image over"""
        self.last_img_id = (self.last_img_id + 1) % 256
        chunks = Screen.make_img_chunks(
            img_bytes, CHUNK_SIZE, self.last_img_id, IMG_RES_480SQ, frame_time)
        # We Need Async Implementation
        for chunk in chunks:
            self.queue_send(self.build_msg(IMG_CMD, chunk))
        # Build dictionary for storing image transfer status
        self.img_transfer_record[self.last_img_id] = [0] * len(chunks)

    # For Images
    @staticmethod
    def make_img_chunks(img_bytearray, chunk_size, img_id, img_res=IMG_RES_480SQ, frame_time=0):
        """Make chunks of image from complete jpg file"""
        max_len = len(img_bytearray)
        chunk_id = 0
        chunks = []
        for start in range(0, max_len, chunk_size):
            # Get the chunk
            end = min(start+chunk_size, max_len)
            img_chunk = img_bytearray[start:end]

            # Build ID
            bit7 = 64*img_res + chunk_id + 128*(end == max_len)
            chunk = [img_id, bit7]

            # Append 0, after parity check
            chunk_len = end - start
            if chunk_len < chunk_size:
                zeros = [0] * (chunk_size + start - end)
                img_chunk.append(zeros)
            chunk.extend(img_chunk)

            # Add to all chunks
            chunks.append(chunk)
            chunk_id += 1
        return chunks

    # Text related functions

    # Option Menu Related Functions

    # Communication Always On Thread

    def _comm(self):
        while self.running:
            try:
                # Check if there are messages to send
                if len(self.send_jobs):
                    msg = self.send_jobs[0]
                    self.send_jobs.popleft()
                    # Send the 1024-byte chunk
                    self.spi.writebytes(msg)

                    # Then receive
                    self.spi.readbytes(RECV_BYTES)
                else:
                    sleep(WORK_SLEEP_TIME)  # Prevent busy-waiting
            except Exception as e:
                print(f"Error in SPI communication: {e}")

    def stop(self):
        """stop communications"""
        self.running = False
        self.thread.join()
        self.spi.close()


class SPIDummy:
    """Dummy class for debugging without connecting to SPI devices"""

    def __init__(self, id):
        self.commands = {
            1: "ping",
            3: "draw text",
            7: "image chunk",
            127: "draw options",
            255: "sleep/wake",
        }
        self.id = id
        self.dummy_msg = [0] * RECV_BYTES
        self.dummy_msg[0] = self.id
        self.dummy_msg[3] = self.id
        self.last_sign = 0

    def writebytes(self, content):
        """dummy write bytes function"""
        print(f"[DEBUG][Screen {self.id}] Sending Content with \
              {len(content)} bytes to device {content[0]}")
        print(f"       [Screen {self.id}] Message type \
              {self.commands[content[1]]} with computed length {content[2]*256 + content[3]}")
        self.last_sign = content[4]

    def readbytes(self, n):
        """readbytes dummy function"""
        print(f"[DEBUG][Screen {self.id}] read {n} bytes")
        return self.dummy_msg

    def close(self):
        """close connection dummy function"""
        print(f"[DEBUG][Screen {self.id}] commanded to shutdown")


def init_screens():
    # Initialize screens
    screens = []
    # If actual screens attached
    if not NOBUS:
        for i, cfg in enumerate(SCREEN_CFG):
            screens.append(Screen(i, cfg["bus"], cfg["dev"]))
        return screens

    # Otherwise, build a series of dummies
    for i in range(NUM_SCREEN):
        screens.append(SPIDummy(i))


if __name__ == "__main__":
    print("Error, calling module comm directly!")
