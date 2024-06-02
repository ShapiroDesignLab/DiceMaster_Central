"""
U-M Shapiro Design Lab
Daniel Hou @2024

This module handles communication with peripheral ESP32 boards through a chosen interface.

Protocols: see https://docs.google.com/document/d/1ovbKFz1-aYnTLMupWtqQHsDRdrbPbAs7edm_ehnVuko
"""

import time
from time import sleep
from queue import *
import threading
import numpy as np

from config import *

if not NOBUS:
    import spidev

from config import NOBUS, SCREEN_CFG, NUM_SCREEN
from utils import *

from PIL import ImageFont, ImageDraw, Image



def HIBYTE(val):
    return (val >> 8) & 0xFF

def LOBYTE(val):
    return val & 0xFF

commands = {
    PING_CMD: "ping",
    TXT_CMD: "draw text",
    IMG_CMD: "image header",
    OPT_CMD: "draw options",
    OPT_END: "options end",
    RES_CMD: "restore",
    HYB_CMD: "sleep"
}


class SPIDevice:
    """SPI Device for Screen communication"""
    def __init__(self, sid, bus, dev):
        self.bus = bus
        self.dev = dev
        self.id = sid
        self.spi = SPIDummy(sid)

        print("Bus:", self.bus, "dev: ", self.dev)
        if not NOBUS:
            self.spi = spidev.SpiDev()
            self.spi.open(self.bus, self.dev)
            self.spi.max_speed_hz = 96000     # Set speed to 9.6 Mhz
            self.spi.mode = 0b00                # Set SPI Mode to 0
            self.spi.threewire = True
            self.spi.close()
        self.awake = False

    def __del__(self):
        self.awake = False
        self.down()

    def up(self):
        """select device"""
        if self.awake is False:
            self.awake = True
            self.spi.open(self.bus, self.dev)

    def down(self):
        """close spi connection"""
        self.awake = False
        self.spi.close()

    def is_awake(self):
        """See if bus is awake,  usually unnecessary"""
        return self.awake

    def send(self, msg):
        """send and return received content"""
        assert self.awake
        print(f"Written {len(msg)}")
        print(f"Sent {msg}")
        self.spi.writebytes(msg)           # Send the chunk

class Bus:
    """Bus class"""

    def __init__(self):
        self.send_jobs = Queue()
        self.last_spi_dev = None
        self.running = False
        self.ping_devs = []
        self.next_ping_time = time.monotonic()
        self.fixed_msgs = self.__build_reused_msgs()
        self.thread = threading.Thread(target=self.__comm)

    def __del__(self):
        """stop communications"""
        self.running = False
        self.thread.join()
        for dev in self.ping_devs:
            dev.close()

    def register(self, dev):
        """Register screen device to ping periodically and peform sleep/wake"""
        self.ping_devs.append(dev)

    def run(self):
        """Start Bus process"""
        self.next_ping_time = time.monotonic() + SCREEN_BOOT_DELAY
        self.running = True
        self.thread.start()

    @staticmethod
    def __build_reused_msgs():
        ping_msg = [1] * 5                      # Ping message could be reused
        hyb_msg = [253] * 5                     # Hybernate message could be reused
        restore_msg = [254] * 5                 # Restore screen message could be reused
        return [ping_msg, hyb_msg, restore_msg]

    def __broadcast_ping(self):
        """broadcast ping all screens"""
        for i, dev in enumerate(self.ping_devs):
            self.queue((dev, PING_CMD, self.fixed_msgs[0]))
        self.next_ping_time = time.monotonic() + SCREEN_PING_INTERNVAL

    # Hybernate Functions
    def hybernate(self):
        """Put ESP32 to hybernation"""
        for i, dev in enumerate(self.ping_devs):
            self.queue((dev, HYB_CMD, self.fixed_msgs[1]))
        self.running = False

    # Wake Functions
    def wake(self):
        """
        Wake up ESP 32 screen and verify connection.
        """
        self.running = True
        for i, dev in enumerate(self.ping_devs):
            self.queue((dev, RES_CMD, self.fixed_msgs[2]))

    # Queueing functions
    def queue(self, msg):
        """
        queue message to send (not in a hurry by default)
        msg = (spi dev, command, msg)
        """
        assert len(msg)==3
        self.send_jobs.put(msg)

    # Communication Always On Thread
    def __comm(self):
        while True:
            if not self.running and self.send_jobs.empty():
                sleep(HYB_SLEEP_TIME)
                continue
            # try:
            # Periodically ping bus0
            if time.monotonic() > self.next_ping_time:
                self.__broadcast_ping()

            # Check if any jobs
            if self.send_jobs.empty():
                sleep(WORK_SLEEP_TIME)
                continue

            # Retrieve message from queue
            msg = self.send_jobs.get()
            
            # If different device, shutdown and open another spi dev
            if self.last_spi_dev is not None and self.last_spi_dev.id != msg[0].id:
                self.last_spi_dev.down()
            msg[0].up()
            self.last_spi_dev = msg[0]
            print("Upped spi device")

            # Actually send message
            msg[0].send(msg[2])
            print(f"Sent message with length {len(msg[2])}")
            time.sleep(0.01)

class Screen:
    """
    This is the screen class handing communication and context to and from each screen
    """

    def __init__(self, uid, bus, dev, bus_obj):
        self.id = uid
        self.spi_device = SPIDevice(uid, bus, dev)

        # Image Transfer Records
        self.last_img_id = 0

        # Register spi device to be pinged on bus
        bus_obj.register(self.spi_device)
        self.bus = bus_obj

    # Image Functions
    def draw_img(self, img_bytes, img_res=IMG_RES_480SQ, frame_time=0):
        """given an image in bytes, transfer the image over"""
        chunks = self.__make_img_chunks(
            img_bytes, CHUNK_SIZE, self.last_img_id, img_res, frame_time)
        # We Need Async Implementation (which it is now!)
        for chunk in chunks:
            self.bus.queue(self.__build_msg(self.spi_device, IMG_CMD, chunk))

    @staticmethod
    def __make_img_chunks(img_bytearray, chunk_size, img_id, img_res=IMG_RES_480SQ, frame_time=0):
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

    # Text Functions
    def draw_text(self, color, text_list):
        """Draw Text on screen"""
        text_bytes = []
        # Convert to binary
        for (text, _) in text_list:
            tb = bytearray(text, encoding='utf-8')
            tb.append(0)
            if len(text_bytes) < MAX_TEXT_LEN:
                text_bytes.append(tb)
            else:
                print(f"WARNING: single line of text longer than maximum of {MAX_TEXT_LEN} bytes!")
                
        msg = [TXT_CMD, color[0], color[1], color[2]]
        # Compute cursor positions
        cursor_pos = Screen.__compute_text_cursor_position(text_list)
        for i, (text, font) in enumerate(text_list):
            msg.extend([HIBYTE(cursor_pos[i][0]), LOBYTE(cursor_pos[i][0]),
                        HIBYTE(cursor_pos[i][1]), LOBYTE(cursor_pos[i][1]), 
                        font, len(text_bytes[i])])
            msg.extend(text_bytes[i])
        self.bus.queue((self.spi_device, TXT_CMD, msg))
        
    @staticmethod
    def __compute_text_cursor_position(text_list):
        """Computes list of tuples x,y as cursor locations for text"""
        cursor_pos = []
        
        # Load your specific fixed-width font and size
        font = ImageFont.truetype('unifont-12.1.02.ttf', FONT_SIZE)
        bbox = [font.getbbox(text[0]) for text in text_list]
        widths = [w[2] - w[0] for w in bbox]
        heights = [h[3] - h[1] for h in bbox]
        
        # Get size of the text
        width = max(widths)
        x_cursor = max(0, (SCREEN_WIDTH - width) // 2)

        height = max(heights)
        gap = height + TEXT_PADDING * (len(text_list) > 1)
        y_start = (SCREEN_WIDTH-gap*len(text_list)+TEXT_PADDING) // 2
        for i, text in enumerate(text_list):
            cursor_pos.append((x_cursor, y_start + gap*i))
        return cursor_pos

    # Option Menu Related Functions
    def draw_option(self, menu_items):
        """Draw Menu on screen"""
        pass


    # Generic Message Functions
    @staticmethod
    def __build_msg(spi_device, command, content):
        """Build a message body from command and content, calculates lengths, parity, etc"""
        assert 0 <= command and command <= 255
        len_hibyte = len(content) // 256
        len_lobyte = len(content) % 256
        msg = [spi_device.id, command, len(content), len_hibyte, len_lobyte]
        msg.extend(Screen.__parity(msg, content))
        msg.extend(content)
        msg = bytearray(msg)
        return (spi_device, command, msg)

    @staticmethod
    def __parity(header, content):
        """Computes parity of bytes, """
        return (np.array(header).sum() + np.array(content).sum()) % BYTE_SIZE


class SPIDummy:
    """Dummy class for debugging without connecting to SPI devices"""

    def __init__(self, uid):
        self.id = uid
        self.last_sign = 0

    def writebytes(self, content):
        """dummy write bytes function"""
        print(f"[DEBUG][Screen {self.id}] Sending Content with {len(content)} bytes to device {content[0]}")
        print(f"       [Screen {self.id}] Message type {commands[content[1]]} with computed length {content[2]*256 + content[3]}")
        self.last_sign = content[4]

    def close(self):
        """close connection dummy function"""
        print(f"[DEBUG][Screen {self.id}] commanded to shutdown")


if __name__ == "__main__":
    print("Error, calling module comm directly!")
