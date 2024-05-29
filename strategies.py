"""
U-M Shapiro Design Lab
Daniel Hou @2024

This module hosts all image switching strategies. 
"""
import time


class BaseOrganizer:
    def __init__(self, file_loader):
        for _, _, activity, f in file_loader:
            

class ByTypeOrganizer(BaseOrganizer):
    

class StrategyManager:
    def __init__(self):
        pass


class BaseStrategy():
    def __init__(self, file_loader):
        self.start_time = time.time()
        self.file_dict = file_loader

    def trigger(self):
        

class RandomTimeUpdateStrategy(BaseStrategy):
    """Dummy strategy of updating image on each screen in random time series"""
    def __init__(self, file_loader, max_waight=10, min_wait=4):
        super(RandomTimeUpdateStrategy, self).__init__(file_loader)

    def trigger(self):
    