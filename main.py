"""
U-M Shapiro Design Lab
Daniel Hou @2024

This is the main driver of the DiceMaster_Central module
"""

import time
from file_loader import FileLoader
from comm import Screen, Bus
from sensor import MPU6050, MPU6050Dummy
from config import *
from utils import *


def init_screens():
    # Initialize screens
    screens = []
    bus_obj = Bus()
    for i, cfg in enumerate(SCREEN_CFG):
        screens.append(Screen(i+1, cfg["bus"], cfg["dev"], bus_obj))
    bus_obj.run()
    return bus_obj, screens

def init_IMU():
    if NOBUS:
        return MPU6050Dummy()
    return MPU6050()       # NOT TESTED

def main():
    file_loader = FileLoader(SD_ROOT_PATH)      # Load content
    bus, screens = init_screens()                    # Initialize Screens
    # imu = init_IMU()                            # Initialize IMU

    # The App Loop
    while True:
        try:
            file_loader.update_processors(_verbose=True)
            # screens[0].draw_text(COLOR_BABY_BLUE, [("Hello World", 1)])
            l = list(range(50, 255))
            print(l)
            screens[0].send_array(bytearray(l))
            time.sleep(3)
            
        except KeyboardInterrupt:
            print("[DEBUG][Main] Program Shutdown")
            exit()

if __name__ == "__main__":
    main()
