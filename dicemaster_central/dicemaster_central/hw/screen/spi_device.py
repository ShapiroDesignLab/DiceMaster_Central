"""
U-M Shapiro Design Lab
Daniel Hou @2024

This module handles communication with peripheral ESP32 boards through a chosen interface.

Protocols: see https://docs.google.com/document/d/1ovbKFz1-aYnTLMupWtqQHsDRdrbPbAs7edm_ehnVuko
"""
import spidev
from time import perf_counter, sleep
from dicemaster_central.config import SPIConfig

class SPIDevice:
    """SPI Device for Screen communication"""
    NOT_EXPECTING_WAIT_TIME = 0.1
    EXPECTING_WAIT_TIME = 0.002
    def __init__(self,
        bus_id: int,
        bus_dev_id: int,
        spi_config: SPIConfig,
        verbose=False
    ):
        self.bus = bus_id
        self.dev = bus_dev_id
        self.awake = False
        self.verbose = verbose
        self.last_sent_time = 0.0

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

    def send(self, msg):
        """send and return received screen response"""
        # Ensure 10ms delay between xfer() calls
        time_since_last = perf_counter() - self.last_sent_time
        if time_since_last < self.NOT_EXPECTING_WAIT_TIME:  # Expecting time
            sleep(self.NOT_EXPECTING_WAIT_TIME - time_since_last)

        msg = self.spi.xfer2(msg)
        self.last_sent_time = perf_counter()
        return msg

    def send_continuum(self, msgs):
        """send and return received screen response"""
        # Ensure 10ms delay between xfer() calls
        time_since_last = perf_counter() - self.last_sent_time
        if time_since_last < self.NOT_EXPECTING_WAIT_TIME:  # Expecting time
            sleep(self.NOT_EXPECTING_WAIT_TIME - time_since_last)
        
        st = perf_counter()
        for msg in msgs:
            if perf_counter() - st < self.EXPECTING_WAIT_TIME:
                sleep(self.EXPECTING_WAIT_TIME - (perf_counter() - st))
            msg = self.spi.xfer2(msg)
            st = perf_counter()

        self.last_sent_time = perf_counter()
        return msg