"""
U-M Shapiro Design Lab
Huaidian Daniel Hou @2024

This is the main driver of the DiceMaster_Central module
"""

import time
from DiceMaster_Central.media.file_loader import FileLoader
from DiceMaster_Central.hw.screen import ScreenCollection
from DiceMaster_Central.config.constants import SD_ROOT_PATH
from DiceMaster_Central.strategies.strategy_manager import RandomTimeUpdateStrategy


def main():
    # Initialize File Loader
    file_loader = FileLoader(SD_ROOT_PATH)
    # Initialize screens
    screen_collection = ScreenCollection()
    # Initialize Strategy
    strategy = RandomTimeUpdateStrategy(file_loader, screen_collection)

    # The App Loop
    while True:
        try:
            # Update File Processor
            file_loader.update()

            # Update Triggers
            for trigger in strategy.triggers:
                trigger.update()

            # Apply Strategy
            strategy.update()

            # # DEBUG
            # screen_collection[0].draw_text(0x89CFF0, [("Hello World", 1)])

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
