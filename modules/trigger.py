from abc import ABC, abstractmethod
from time import perf_counter
import random

class BaseTrigger(ABC):
  def __init__(self):
    self.is_enabled = False
    pass

  def enable(self):
    self.is_enabled = True

  def disable(self):
    self.is_enabled = False

  @abstractmethod
  def update():
    """Trigger grabs information from subscribed entities and return whether triggered"""
    assert False

class FixedTimeTrigger(BaseTrigger):
  def __init__(self, time_interval=3):
    super(FixedTimeTrigger, self).__init__()
    self.time_interval = time_interval
    self.next_time = perf_counter() + self.time_interval

  def enable(self):
    """
    Overload enable to support re-establishment of time intervals
    """
    super().enable()
    self.next_time = perf_counter() + self.time_interval

  def update(self):
    """
    Triggers if time_interval is reached
    """
    if perf_counter() > self.next_time:
      self.next_time = perf_counter() + self.time_interval
      return True
    return False
  

class RandomTimeTrigger(BaseTrigger):
  def __init__(self, min_int=1, max_int=10):
    super(RandomTimeTrigger, self).__init__()
    random.seed(442)
    self.min_int = min_int
    self.max_int = max_int
    self.next_time = perf_counter() + self.get_rand_time()

  def get_rand_time(self):
    return random.randrange(self.min_int, self.max_int)

  def enable(self):
    """
    Overload enable to support re-establishment of time intervals
    """
    super().enable()
    self.next_time = perf_counter() + self.get_rand_time()

  def update(self):
    """
    Triggers if time_interval is reached
    """
    if perf_counter() > self.next_time:
      self.next_time = perf_counter() + self.get_rand_time()
      return True
    return False