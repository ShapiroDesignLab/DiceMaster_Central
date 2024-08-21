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


# Initialize Sensors
imu = MPU6050() if not NOBUS else MPU6050Dummy()
sensors = [imu]

# Initialize screens
bus = Bus()
bus.run()
screens = []
for i, cfg in enumerate(SCREEN_CFG):
    screens.append(Screen(i+1, cfg["bus"], cfg["dev"], bus))


# Initialize File Loader
file_loader = FileLoader(SD_ROOT_PATH)      # Load content

def main():

    # l = list(range(128, 144))
    # br = bytearray(l)

    # The App Loop
    while True:
        try:
            # Update File Processor
            file_loader.update_processors()

            # Update Sensors
            _ = [sensor.update() for sensor in sensors]


            # Apply Strategy

            # Screens
            screens[0].draw_text(COLOR_BABY_BLUE, [("Hello World", 1)])
            # screens[0].send_array(br)


            time.sleep(3)
            
        except KeyboardInterrupt:
            print("[DEBUG][Main] Program Shutdown")
            exit()

        except:


if __name__ == "__main__":
    main()
