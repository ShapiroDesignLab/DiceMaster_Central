import sys
import random
import time

sys.path.append('/home/dice/DiceMaster/DiceMaster_Central/')
from DiceMaster_Central.hw.spi_device import SPIDevice
from DiceMaster_Central.config.dice_config import SPIConfig
from DiceMaster_Central.data.protocol import TextBatchMessage

sample_texts = [
    "Miss you Renee :)",
    "Hey Kevin!",
]

sample_text = random.choice(sample_texts)
print(f"Selected text: {sample_text}")

text_msg = TextBatchMessage(
    font_color=0x8E7D,
    texts=[(48, 48, 1, sample_text)],
)

another_text_msg = TextBatchMessage.decode(text_msg.payload)
assert text_msg == another_text_msg, "Decoded message does not match original"
print(text_msg.payload)

spi_config = SPIConfig(
    max_speed_hz=960000,  # Example speed
    mode=0b00,             # SPI Mode 0, not sure what that means
    bits_per_word=8
)

spid = SPIDevice(
    bus_id=3,
    bus_dev_id=0,
    spi_config=spi_config,
    verbose=True
)