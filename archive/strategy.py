"""
U-M Shapiro Design Lab
Daniel Hou @2024

This module hosts all image switching strategies. 
"""
import time
from abc import ABC, abstractmethod
import numpy as np

from archive.trigger import RandomTimeTrigger

class BaseStrategy(ABC):
    def __init__(self, file_loader, screen_collection):
        self.start_time = time.time()
        self.files = file_loader.items()
        self.screen_collection = screen_collection
        self.triggers = []

    def enable_all_triggers(self):
        for trigger in self.triggers:
            trigger.enable()

    @property
    @abstractmethod
    def next_media(self):
        raise NotADirectoryError()
    
    @property
    @abstractmethod
    def next_screen(self):
        raise NotImplementedError()

    @abstractmethod
    def update(self):
        raise NotImplementedError()
        
class RandomTimeUpdateStrategy(BaseStrategy):
    """Dummy strategy of updating image on each screen in random time series"""
    def __init__(self, file_loader, screen_collection, min_wait=1, max_wait=10):
        super(RandomTimeUpdateStrategy, self).__init__(file_loader, screen_collection)
        self.triggers.append(RandomTimeTrigger(min_wait, max_wait))
        np.random.seed(np.random.randint(21, 800))
        self.num_files = len(self.files)
        self.next_file_idx = 0

    @property
    def next_media(self):
        f = self.files[self.next_file_idx]
        self.next_file_idx += 1
        return f
    
    @property
    def next_screen(self):
        return self.screen_collection[0]
    
    def update(self):
        self.next_screen.update()


if __name__ == "__main__":
    print("Error, calling module comm directly!")