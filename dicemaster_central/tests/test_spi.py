import sys
import time
from time import perf_counter, sleep
import random

sys.path.append('/home/dice/DiceMaster/DiceMaster_Central/')
from DiceMaster_Central.hw.screen import SPIDevice
from DiceMaster_Central.dicemaster_central.config import SPIConfig
from DiceMaster_Central.constants import Rotation
from DiceMaster_Central.media_typing.media_types import TextEntry, Image
from DiceMaster_Central.media_typing.protocol import TextBatchMessage

sample_texts = [
    "Miss you Renee :)",
    "Hey Kevin!",
]

sample_text = random.choice(sample_texts)
print(f"Selected text: {sample_text}")

entry = TextEntry(
    text=sample_text,
    font_color=0x8E7D,  # Example color
    x_cursor=48,               # X position
    y_cursor=48,               # Y position
    font_id=1
)

text_msg = TextBatchMessage(
    bg_color=0xFFFF,
    texts=[entry],
)

another_text_msg = TextBatchMessage.decode(text_msg.payload)
assert text_msg == another_text_msg, "Decoded message does not match original"

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

spid.up()

# Then test a fancier text message
entry1 = TextEntry(
    text="Oh Renee......",
    font_color=0x8E7D,  # Example color
    x_cursor=48,               # X position
    y_cursor=48,               # Y position
    font_id=1
)
entry2 = TextEntry(
    text="想你......",
    font_color=0x8E7D,  # Example color
    x_cursor=48,               # X position
    y_cursor=128,               # Y position
    font_id=3
)
text_msg2 = TextBatchMessage(
    bg_color=0xFFFF,
    texts=[entry1, entry2],
)

# Then test another text
spid.up()
response = spid.send(text_msg.payload)
spid.down()
print(f"Sent {len(text_msg.payload)} bytes: {text_msg.payload} with response {response}")

payload = text_msg2.payload
print(f"Total payload length: {len(payload)} bytes")
spid.up()
spid.send(payload)
spid.down()
print(f"Sent {len(payload)} bytes")

import os
# Then test an image
image_media = Image(
    file_path=os.path.expanduser('~/DiceMaster/DiceMaster_Central/tests/cat_480.jpg'),
    image_id=0,
    delay_time=255,
)
msgs = image_media.to_msg(rotation=Rotation(0))
spid.up()
spid.send(msgs[0].payload)
spid.down()

spid.up()
print(f"Sending {len(msgs[1:])} continuation messages: {msgs[1:]}")
spid.send_continuum([msg.payload for msg in msgs[1:]])
spid.down()

st = perf_counter()
time.sleep(0.1)


# Then test GIF
all_msgs = []
for i in range(24):
    image_media = Image(
        file_path=os.path.expanduser(f'~/DiceMaster/DiceMaster_Central/tests/miss-you/{i}.jpg'),
        image_id=i+1,
        delay_time=100,
    )
    msgs = image_media.to_msg(rotation=Rotation(0))
    all_msgs.extend(msgs)

print(f"Encoded {len(all_msgs)} messages for GIF")
spid.up()
for msg in all_msgs:
    spid.send(msg.payload)
    sleep(0.05)
spid.down()
    