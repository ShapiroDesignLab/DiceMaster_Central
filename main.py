"""
U-M Shapiro Design Lab
Daniel Hou @2024

This is the main driver of the DiceMaster_Central module
"""

import time
from comm import init_screens
from file_loader import FileLoader
# from sensor import MPU6050
import config

def main():
    # Load content
    file_loader = FileLoader(config.SD_ROOT_PATH)

    init_screens()
    
    file_loader.visualize()

    # True Kpp
    while True:
        try:
            # print("[DEBUG][Main] Main program Running")
            file_loader.update_processors(_verbose=True)
            time.sleep(0.001)
        except KeyboardInterrupt:
            print("[DEBUG][Main] Program Shutdown")
            exit()




if __name__ == "__main__":
    main()