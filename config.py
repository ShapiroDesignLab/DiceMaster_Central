"""
Configuration File for project
"""
import os

# Whether running on dev machines or in production
# NOBUS = True means we are debugging
NOBUS = False
DYNAMIC_LOADING = False

SCREEN_BOOT_DELAY = 3
SCREEN_PING_INTERNVAL = 10

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
NUM_SCREEN = 1
SCREEN_CFG = []
def build_screen_config():
    """build screen dictionary according to numbers"""
    for bus in range(2):
        for dev in range(2):
            if bus * 2 + dev == NUM_SCREEN:
                return
            SCREEN_CFG.append({
                "bus": bus,
                "dev": dev
            })
build_screen_config()


# Draw Text Options
ALIGN_LEFT = 0
ALIGN_RIGHT = 1
ALIGN_TOP = 2
ALIGN_BOTTOM = 3
ALIGN_CENTER = 4

TEXT_WIDTH = 12
TEXT_HEIGHT = 16
TEXT_PADDING = 4

MAX_TEXT_LEN = 256
FONT_SIZE = 10

SCREEN_WIDTH = 480