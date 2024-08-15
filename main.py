"""
U-M Shapiro Design Lab
Huaidian Daniel Hou @2024

This is the main driver of the DiceMaster_Central module
"""

import time
from modules.file_loader import FileLoader
from modules.comm import Screen, Bus
from modules.sensor import MPU6050, MPU6050Dummy
from modules.const import *
from config import *


# Initialize IMU
IMU = MPU6050() if not NOBUS else MPU6050Dummy()

# Initialize screens
screens = []
bus = Bus()
for i, cfg in enumerate(SCREEN_CFG):
    screens.append(Screen(i+1, cfg["bus"], cfg["dev"], bus))
bus.run()

# Initialize File Loader
file_loader = FileLoader(SD_ROOT_PATH)      # Load content

def main():

    # l = list(range(128, 144))
    # br = bytearray(l)

    # The App Loop
    while True:
        try:
            file_loader.update_processors(_verbose=True)

            screens[0].draw_text(COLOR_BABY_BLUE, [("Hello World", 1)])
            # screens[0].send_array(br)
            time.sleep(3)
            
        except KeyboardInterrupt:
            print("[DEBUG][Main] Program Shutdown")
            exit()

if __name__ == "__main__":
    main()
