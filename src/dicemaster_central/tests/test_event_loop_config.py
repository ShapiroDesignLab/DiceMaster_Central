from dicemaster_central.config import dice_config, SPIBusConfig
from dicemaster_central.constants import GIF_FRAME_TIME


def test_spi_bus_config_has_rate_limit():
    cfg = SPIBusConfig(bus_id=0)
    assert hasattr(cfg, 'bus_min_interval_s')
    assert cfg.bus_min_interval_s == GIF_FRAME_TIME


def test_dice_config_bus_configs_have_rate_limit():
    for bus_id, cfg in dice_config.bus_configs.items():
        assert hasattr(cfg, 'bus_min_interval_s'), f"bus {bus_id} missing bus_min_interval_s"
        assert cfg.bus_min_interval_s > 0
