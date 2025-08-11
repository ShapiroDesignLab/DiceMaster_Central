import sys
import time
import argparse
from time import perf_counter,sleep

sys.path.append('/home/dice/DiceMaster/DiceMaster_Central/')
from dicemaster_central.hw.screen import SPIDevice
from dicemaster_central.config import SPIConfig
from dicemaster_central.constants import Rotation
# from dicemaster_central.media_typing.protocol import TextBatchMessage
from dicemaster_central.media_typing import TextGroup, Image, GIF

import os
current_path = os.path.dirname(os.path.abspath(__file__))

SCREEN_ID = 1
SPID = 0

# Setup SPI device
spi_config = SPIConfig(
    max_speed_hz=9600000,  # Example speed 4800000
)

spidev = SPIDevice(
    bus_id=SPID,
    bus_dev_id=0,
    spi_config=spi_config,
    verbose=True
)

text_group = TextGroup(
    file_path=os.path.join(current_path, 'test_assets/hey_guys.json'),
)
text_msg = text_group.to_msg(screen_id=SCREEN_ID)
spidev.send(text_msg.payload)
print(f"Sent {len(text_msg.payload)} bytes text message")
time.sleep(1)

text_group = TextGroup(
    file_path=os.path.join(current_path, 'test_assets/text2.json'),
)
text_msg = text_group.to_msg(screen_id=SCREEN_ID)
spidev.send(text_msg.payload)
print(f"Sent {len(text_msg.payload)} bytes text message")
time.sleep(1)

text_group = TextGroup(
    file_path=os.path.join(current_path, 'test_assets/text3.json'),
)
text_msg = text_group.to_msg(screen_id=SCREEN_ID)
spidev.send(text_msg.payload)
print(f"Sent {len(text_msg.payload)} bytes text message")
time.sleep(1)

# Then test an image
image_media = Image(
    file_path=os.path.join(current_path, 'test_assets/cat_480.jpg'),
    image_id=0,
    delay_time=255
)
# Send
msgs = image_media.to_msg(screen_id=SCREEN_ID, rotation=Rotation(0))
for msg in msgs:
    spidev.send(msg.payload)
    print(f"Sent {len(msg.payload)} bytes image message")
    time.sleep(0.002)

# Then test GIF
gif_media = GIF(
    file_path=os.path.join(current_path, f'test_assets/miss-you.gif.d'),
    delay_time=100,
)
gif_msgs = gif_media.to_msg(screen_id=SCREEN_ID)
for frame_msgs in gif_msgs:
    for msg in frame_msgs:
        print("Sent", len(msg.payload), "bytes")
        spidev.send(msg.payload)
    time.sleep(0.1)