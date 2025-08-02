import sys
import time
from time import perf_counter, sleep
import random

sys.path.append('/home/dice/DiceMaster/DiceMaster_Central/')
from dicemaster_central.hw.screen import SPIDevice
from dicemaster_central.config import SPIConfig
from dicemaster_central.constants import Rotation
# from dicemaster_central.media_typing.protocol import TextBatchMessage
from dicemaster_central.media_typing import TextGroup, Image, GIF

import os
current_path = os.path.dirname(os.path.abspath(__file__))

# Setup SPI device

spi_config = SPIConfig(
    max_speed_hz=4800000,  # Example speed
    mode=0b00,             # SPI Mode 0, not sure what that means
    bits_per_word=8
)

# At this point, devices should be wired up. 
spid = SPIDevice(
    bus_id=0,
    bus_dev_id=1,
    spi_config=spi_config,
    verbose=True
)

text_group = TextGroup(
    file_path=os.path.join(current_path, 'test_assets/hey_guys.json'),
)
text_msg = text_group.to_msg()
spid.up()
response = spid.send(text_msg.payload)
spid.down()
print(f"Sent {len(text_msg.payload)} bytes")
time.sleep(1)

# Then test an image
image_media = Image(
    file_path=os.path.join(current_path, 'test_assets/cat_480.jpg'),
    image_id=0,
    delay_time=255,
)
msgs = image_media.to_msg(rotation=Rotation(0))
spid.up()
spid.send(msgs[0].payload)
spid.down()
spid.up()
spid.send_continuum([msg.payload for msg in msgs[1:]])
spid.down()

st = perf_counter()
time.sleep(1)


# Then test GIF
gif_media = GIF(
    file_path=os.path.join(current_path, f'test_assets/miss-you.gif.d'),
    delay_time=100,
)
gif_msgs = gif_media.to_msg()

spid.up()
for frame_msgs in gif_msgs:
    for msg in frame_msgs:
        spid.send(msg.payload)
        sleep(0.05)
spid.down()
