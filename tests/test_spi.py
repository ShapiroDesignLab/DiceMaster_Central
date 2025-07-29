import sys
import random

sys.path.append('/home/dice/DiceMaster/DiceMaster_Central/')
from DiceMaster_Central.hw.spi_device import SPIDevice
from DiceMaster_Central.config.dice_config import SPIConfig
from DiceMaster_Central.media_typing.media_types import TextEntry
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
print(text_msg.payload)

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
    verbose=True
)

spid.up()
spid.send(text_msg.payload)