"""
U-M Shapiro Design Lab
Daniel Hou @2024

This module handles communication with peripheral ESP32 boards through a chosen interface.

Protocols: see https://docs.google.com/document/d/1ovbKFz1-aYnTLMupWtqQHsDRdrbPbAs7edm_ehnVuko
"""
from typing import Dict
import spidev

class SPIDevice:
    """SPI Device for Screen communication"""
    def __init__(self,
        bus_id: int,
        bus_dev_id: int,
        spi_config: Dict,
        verbose=False
    ):
        self.bus = bus_id
        self.dev = bus_dev_id
        self.awake = False
        self.verbose = verbose

        # Create instance from config
        self.spi = spidev.SpiDev()
        # Open, configure, and close
        self.spi.open(self.bus, self.dev)
        self.spi.max_speed_hz = spi_config.max_speed_hz
        self.spi.mode = spi_config.mode
        self.spi.threewire = False
        self.spi.close()

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

    def send(self, msg, held=False):
        """send and return received content"""
        assert self.awake
        if self.verbose:
            print(f"Written {len(msg)}")
            print(f"Sent {[hex(byte) for byte in msg]}")
        # self.spi.writebytes(msg)           # Send the chunk
        if not held:
            self.spi.xfer(msg)
        else:
            self.spi.xfer2(msg)