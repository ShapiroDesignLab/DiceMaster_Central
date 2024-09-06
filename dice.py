"""
U-M Shapiro Design Lab
Huaidian Daniel Hou @2024

This is the main driver of the DiceMaster_Central module
"""

import time
from modules.file_loader import FileLoader
from modules.screen import ScreenCollection
from modules.sensor import SensorCollection
from modules.config import SD_ROOT_PATH
from modules.strategy import RandomTimeUpdateStrategy


def main():
    # Initialize File Loader
    file_loader = FileLoader(SD_ROOT_PATH)
    # Initialize Sensors
    sensor_collection = SensorCollection()
    # Initialize screens
    screen_collection = ScreenCollection()
    # Initialize Strategy
    strategy = RandomTimeUpdateStrategy(file_loader, screen_collection)

    while not sensor_collection.is_all_sensors_ready():
        time.sleep(0.1)

    # The App Loop
    while True:
        try:
            # # Update File Processor
            # file_loader.update()

            # # Update Sensors
            # for sensor in sensor_collection.values():
            #     sensor.update()

            # # Update Triggers
            # for trigger in strategy.triggers:
            #     trigger.update()

            # # Apply Strategy
            # strategy.update()

            # DEBUG
            screen_collection[0].draw_text(0x89CFF0, [("Hello World", 1)])

            time.sleep(10)
            
        except KeyboardInterrupt:
            print("[DEBUG][Main] Program Shutdown")
            del strategy
            del sensor_collection
            del screen_collection
            del file_loader
            exit()

if __name__ == "__main__":
    main()
