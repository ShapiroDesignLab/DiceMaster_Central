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
from .constants import NOBUS
from .constants import PING_CMD, TXT_CMD, IMG_CMD, OPT_CMD, OPT_END, RES_CMD, HYB_CMD, \
        SCREEN_BOOT_DELAY, SCREEN_PING_INTERNVAL, HYB_SLEEP_TIME, WORK_SLEEP_TIME

if not NOBUS:
    import spidev

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
            self.spi.max_speed_hz = 96000
            self.spi.mode = 0b00                # Set SPI Mode to 0
            # self.spi.threewire = True
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
        ping_msg = [1] * 8                      # Ping message could be reused
        hyb_msg = [253] * 8                     # Hybernate message could be reused
        restore_msg = [254] * 8                 # Restore screen message could be reused
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
        padded_msg = msg[2]
        pad_len = (4 - (len(padded_msg) % 4)) % 4
        padded_msg.extend([0] * pad_len)
        self.send_jobs.put((msg[0], msg[1], padded_msg))

    # Communication Always On Thread
    def __comm(self):
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
            
            # If different device, shutdown and open another spi dev
            if self.last_spi_dev is not None:
                self.last_spi_dev.down()
                sleep(0.001)
            msg[0].up()
            self.last_spi_dev = msg[0]

            # Actually send message
            msg[0].send(msg[2])
            print(f"Sent message with length {len(msg[2])}")
            time.sleep(0.009)

class SPIDummy:
    """
    Dummy class for debugging without connecting to SPI devices
    """
    def __init__(self, uid):
        self.id = uid
        self.last_sign = 0

    def writebytes(self, content):
        """dummy write bytes function"""
        print(f"[DEBUG][Screen {self.id}] Sending Content with {len(content)} bytes to device {content[0]}")
        print(f"       [Screen {self.id}] Message type {commands[content[1]]} with computed length {content[2]*256 + content[3]}")
        self.last_sign = content[4]
    
    def open(self, bus, dev):
        """close connection dummy function"""
        print(f"[DEBUG][Screen {self.id}] commanded to start")

    def close(self):
        """close connection dummy function"""
        print(f"[DEBUG][Screen {self.id}] commanded to shutdown")

if __name__ == "__main__":
    print("Error, calling module comm directly!")