"""
Configuration loader for DiceMaster screens
Loads screen configuration from JSON file and provides client library for ROS nodes


spi_config: SPIConfig class
screen_config_global: ScreenConfigGlobal class
screen_configs: dict of id -> ScreenConfig instances
"""

from typing import Dict
from dataclasses import dataclass
from dicemaster_central.constants import Rotation

@dataclass
class ScreenConfig:
    """Configuration for a single screen"""
    id: int
    bus_id: int
    bus_dev_id: int
    default_orientation: int
    description: str

@dataclass
class GlobalScreenConfig:
    """Global screen settings"""
    auto_rotate: bool = True
    rotation_margin: float = 0.1

@dataclass
class SPIConfig:
    """SPI configuration settings"""
    max_speed_hz: int = 9600000
    mode: int = 0
    bits_per_word: int = 8
    max_buffer_size: int = 8192
    num_devices_per_bus: int = 2

@dataclass
class IMUConfig:
    """IMU configuration settings"""
    i2c_bus = 6
    i2c_address: int = 0x68
    calibration_duration: float = 5.0
    polling_rate: int = 50

class DiceConfig:
    screen_configs: Dict[int, ScreenConfig] = {
        1: ScreenConfig(id=1, bus_id=0, bus_dev_id=0, default_orientation=Rotation(0), description="Screen 1"),
        2: ScreenConfig(id=2, bus_id=0, bus_dev_id=1, default_orientation=Rotation(0), description="Screen 2"),
        3: ScreenConfig(id=3, bus_id=1, bus_dev_id=0, default_orientation=Rotation(0), description="Screen 3"),
        4: ScreenConfig(id=4, bus_id=1, bus_dev_id=1, default_orientation=Rotation(0), description="Screen 4"),
        5: ScreenConfig(id=5, bus_id=3, bus_dev_id=0, default_orientation=Rotation(0), description="Screen 5"),
        6: ScreenConfig(id=6, bus_id=3, bus_dev_id=1, default_orientation=Rotation(0), description="Screen 6"),
    }
    active_spi_controllers = set([s.bus_id for s in screen_configs.values()])
    global_screen_config: GlobalScreenConfig = GlobalScreenConfig()
    spi_config: SPIConfig = SPIConfig()
    imu_config: IMUConfig = IMUConfig()

dice_config = DiceConfig()