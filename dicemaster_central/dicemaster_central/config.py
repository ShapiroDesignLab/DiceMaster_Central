"""
Configuration loader for DiceMaster screens
Loads screen configuration from JSON file and provides client library for ROS nodes


spi_config: SPIConfig class
screen_config_global: ScreenConfigGlobal class
screen_configs: dict of id -> ScreenConfig instances
"""
import os
from typing import Dict
from dataclasses import dataclass
from dicemaster_central.constants import Rotation

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
class SPIBusConfig:
    bus_id: int
    use_dev: int = 0

@dataclass
class ScreenConfig:
    """Configuration for a single screen"""
    id: int
    bus_id: int
    default_orientation: int
    description: str

@dataclass
class IMUConfig:
    """IMU configuration settings"""
    i2c_bus = 6
    i2c_address: int = 0x68
    calibration_duration: float = 5.0
    polling_rate: int = 50

EXAMPLE_DIR = os.path.expanduser("~/DiceMaster/DiceMaster_Central/dicemaster_central/examples")

class GameConfig:
    default_game_locations=[
        os.path.expanduser("~/.dicemaster/games"),
        os.path.join(EXAMPLE_DIR, "games")
    ]
    default_strategy_locations=[
        os.path.expanduser("~/.dicemaster/strategies"),
        os.path.join(EXAMPLE_DIR, "strategies")
    ]
    default_game="chinese_quizlet"
    
class DiceConfig:
    spi_config = SPIConfig()
    bus_configs: Dict[int, SPIBusConfig] = {
        0: SPIBusConfig(bus_id=0),
        1: SPIBusConfig(bus_id=1),
        3: SPIBusConfig(bus_id=3)
    }
    screen_configs: Dict[int, ScreenConfig] = {
        1: ScreenConfig(id=1, bus_id=0, default_orientation=Rotation(0), description="Screen 1"),
        2: ScreenConfig(id=2, bus_id=0, default_orientation=Rotation(0), description="Screen 2"),
        3: ScreenConfig(id=3, bus_id=1, default_orientation=Rotation(0), description="Screen 3"),
        4: ScreenConfig(id=4, bus_id=1, default_orientation=Rotation(0), description="Screen 4"),
        5: ScreenConfig(id=5, bus_id=3, default_orientation=Rotation(0), description="Screen 5"),
        6: ScreenConfig(id=6, bus_id=3, default_orientation=Rotation(0), description="Screen 6"),
    }
    active_spi_controllers = set(bus_configs.keys())
    global_screen_config: GlobalScreenConfig = GlobalScreenConfig()
    imu_config: IMUConfig = IMUConfig()
    game_config = GameConfig()

dice_config = DiceConfig()