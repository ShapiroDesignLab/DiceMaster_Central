"""
Configuration File for project
"""
import os

# Whether running on dev machines or in production
# NOBUS = True means we are debugging
NOBUS = True
DYNAMIC_LOADING = False

# Configure SD card path
SD_ROOT_PATH = "/media/dicemaster/"
if NOBUS:
    SD_ROOT_PATH = os.path.join(os.path.expanduser("~"), ".dicedata")
if not os.path.isdir(SD_ROOT_PATH): os.makedirs(SD_ROOT_PATH)

# Configure cache path
CACHE_PATH = os.path.join(os.path.expanduser("~"), ".dicemaster/cache")
if not os.path.isdir(CACHE_PATH):
    os.makedirs(CACHE_PATH)

# Configure DB Path
# Path should have been created from previous step
DB_PATH = os.path.join(os.path.expanduser("~"), ".dicemaster/fdb.sqlite")


# Build config for screens
NUM_SCREEN = 2
SCREEN_CFG = []
def build_screen_config():
    """build screen dictionary according to numbers"""
    for bus in range(2):
        for dev in range(2):
            SCREEN_CFG.append({
                "bus": bus,
                "dev": dev
            })
            if bus * 2 + dev == NUM_SCREEN:
                return
            
build_screen_config()
