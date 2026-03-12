"""Tests for SPIBusConfig event-loop rate-limit field.

Imports config and constants directly (bypassing the package __init__ which
pulls in ROS2/pydantic dependencies that aren't available on macOS dev machines).
"""
import importlib.util
import sys
import os

_PKG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         'dicemaster_central')


def _load_module_into_sys(name, rel_path):
    """Load a module file directly and register it in sys.modules under `name`."""
    path = os.path.join(_PKG_DIR, rel_path)
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod  # register before exec so intra-package imports find it
    spec.loader.exec_module(mod)
    return mod


# Load constants first so config.py's `from dicemaster_central.constants import ...`
# resolves without triggering the package __init__.
constants = _load_module_into_sys('dicemaster_central.constants', 'constants.py')
config = _load_module_into_sys('dicemaster_central.config', 'config.py')

GIF_FRAME_TIME = constants.GIF_FRAME_TIME
SPIBusConfig = config.SPIBusConfig
dice_config = config.dice_config


def test_spi_bus_config_has_rate_limit():
    cfg = SPIBusConfig(bus_id=0)
    assert hasattr(cfg, 'bus_min_interval_s')
    assert cfg.bus_min_interval_s == GIF_FRAME_TIME


def test_dice_config_bus_configs_have_rate_limit():
    for bus_id, cfg in dice_config.bus_configs.items():
        assert hasattr(cfg, 'bus_min_interval_s'), f"bus {bus_id} missing bus_min_interval_s"
        assert cfg.bus_min_interval_s > 0
