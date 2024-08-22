"""
U-M Shapiro Design Lab
Daniel Hou @2024

This module hosts all image switching strategies. 
"""
import time
from abc import ABC, abstractmethod
import numpy as np

from modules.trigger import RandomTimeTrigger



class BaseStrategy(ABC):
    def __init__(self, file_loader, screen_collection):
        self.start_time = time.time()
        self.files = file_loader
        self.screen_collection = screen_collection
        self.triggers = []

    def enable_all_triggers(self):
        for trigger in self.triggers:
            trigger.enable()

    @abstractmethod
    def next_media(self):
        pass

    @abstractmethod
    def next_screen(self, screen_assembly):
        pass
        
class RandomTimeUpdateStrategy(BaseStrategy):
    """Dummy strategy of updating image on each screen in random time series"""
    def __init__(self, file_loader, screen_collection, min_wait=1, max_wait=10):
        super(RandomTimeUpdateStrategy, self).__init__(file_loader, screen_collection)
        self.triggers.append(RandomTimeTrigger(min_wait, max_wait))
        np.random.seed(np.random.randint(21, 800))

    def next_media(self):
        raise NotImplementedError()
    
    def next_screen(self):
        raise NotImplementedError()

if __name__ == "__main__":
    print("Error, calling module comm directly!")