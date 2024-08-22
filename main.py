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

# Initialize File Loader
file_loader = FileLoader(SD_ROOT_PATH)      # Load content
# Initialize Sensors
sensor_collection = SensorCollection()
# Initialize Strategy
strategy = 
# Initialize screens
screen_collection = ScreenCollection()



def main():
    # l = list(range(128, 144))
    # br = bytearray(l)

    while not sensor_collection.is_all_sensors_ready():
        time.sleep(0.1)

    # The App Loop
    while True:
        try:
            # Update File Processor
            file_loader.update()

            # Update Sensors
            for sensor in sensor_collection.values():
                sensor.update()

            # Update Triggers
            for trigger in strategy.triggers():
                trigger.update()

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
