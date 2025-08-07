import sys
import time
from time import perf_counter

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
    max_speed_hz=96000,  # Example speed
)

# At this point, devices should be wired up. 
spid1 = SPIDevice(
    bus_id=0,
    bus_dev_id=0,
    spi_config=spi_config,
    verbose=True
)
# spid2 = SPIDevice(
#     bus_id=BUS_ID,
#     bus_dev_id=1,
#     spi_config=spi_config,
#     verbose=True
# )

text_group = TextGroup(
    file_path=os.path.join(current_path, 'test_assets/hey_guys.json'),
)
text_msg = text_group.to_msg()
print(text_msg.payload)
spid1.up()
spid1.send(text_msg.payload)
spid1.down()
# spid2.up()
# spid2.send(text_msg.payload)
# spid2.down()

print(f"Sent {len(text_msg.payload)} bytes")
time.sleep(1)

# Then test an image
image_media = Image(
    file_path=os.path.join(current_path, 'test_assets/cat_480.jpg'),
    image_id=0,
    delay_time=255,
)
msgs = image_media.to_msg(rotation=Rotation(0))
# Send spid1
spid1.up()
spid1.send(msgs[0].payload)
spid1.down()
spid1.up()
spid1.send_continuum([msg.payload for msg in msgs[1:]])
spid1.down()

time.sleep(0.1)

# Send spid2
# spid2.up()
# spid2.send(msgs[0].payload)
# spid2.down()
# spid2.up()
# spid2.send_continuum([msg.payload for msg in msgs[1:]])
# spid2.down()


st = perf_counter()
time.sleep(1)

# Then test GIF
# gif_media = GIF(
#     file_path=os.path.join(current_path, f'test_assets/miss-you.gif.d'),
#     delay_time=100,
# )
# gif_msgs = gif_media.to_msg()

# spid.up()
# for frame_msgs in gif_msgs:
#     for msg in frame_msgs:
#         spid.send(msg.payload)
#         sleep(0.05)
# spid.down()
