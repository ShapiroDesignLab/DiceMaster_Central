import sys
import time
import random

sys.path.append('/home/dice/DiceMaster/DiceMaster_Central/')
from DiceMaster_Central.hw.spi_device import SPIDevice
from DiceMaster_Central.config.dice_config import SPIConfig
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
    max_speed_hz=9600000,  # Example speed
    mode=0b00,             # SPI Mode 0, not sure what that means
    bits_per_word=8
)

# At this point, devices should be wired up. 
spid = SPIDevice(
    bus_id=0,
    bus_dev_id=1,
    spi_config=spi_config,
    verbose=False
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
spid.send(text_msg.payload, held=True)
print(f"Sent {len(text_msg.payload)} bytes: {text_msg.payload}")

spid.up()
payload = text_msg2.payload
# Dupicate that 30 times to 1800 bytes
payload = payload * 30
print(f"Total payload length: {len(payload)} bytes")
spid.send(payload, held=True)
print(f"Sent {len(payload)} bytes")
# time.sleep(1)

# import os
# # Then test an image
# image_media = Image(
#     file_path=os.path.expanduser('~/DiceMaster/DiceMaster_Central/tests/cat_480.jpg')
# )
# msgs = image_media.to_msg()
# print(f"{len(msgs)} messages:", msgs)

# print([hex(byte) for byte in msgs[0].payload])

# for msg in msgs:
#     spid.send(msg.payload)
#     time.sleep(0.5)  # Give some time between messages

# # Then test a GIF