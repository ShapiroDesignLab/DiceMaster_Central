"""
Ring buffer implementation for numpy arrays
"""
import numpy as np


class RingBufferNP:
    """
    Efficient ring buffer for numpy arrays with fixed size
    """
    
    def __init__(self, capacity, dtype=np.float64, shape=None):
        """
        Initialize ring buffer
        
        Args:
            capacity (int): Maximum number of elements
            dtype: numpy data type
            shape (tuple): Shape of each element (None for scalar)
        """
        self.capacity = capacity
        self.dtype = dtype
        self.shape = shape if shape is not None else ()
        
        # Create buffer
        if shape is not None:
            self.buffer = np.zeros((capacity,) + shape, dtype=dtype)
        else:
            self.buffer = np.zeros(capacity, dtype=dtype)
            
        self.head = 0
        self.tail = 0
        self.size = 0
        self.is_full = False
        
    def append(self, item):
        """Add item to buffer"""
        if self.shape:
            self.buffer[self.head] = np.array(item, dtype=self.dtype)
        else:
            self.buffer[self.head] = self.dtype(item)
            
        if self.is_full:
            self.tail = (self.tail + 1) % self.capacity
            
        self.head = (self.head + 1) % self.capacity
        
        if self.size < self.capacity:
            self.size += 1
        else:
            self.is_full = True
            
    def get_all(self):
        """Get all items as numpy array"""
        if self.size == 0:
            if self.shape:
                return np.array([]).reshape(0, *self.shape)
            else:
                return np.array([])
                
        if not self.is_full:
            return self.buffer[:self.size].copy()
        else:
            # Return in chronological order
            return np.concatenate([
                self.buffer[self.tail:],
                self.buffer[:self.head]
            ])
            
    def get_latest(self, n):
        """Get latest n items"""
        if n <= 0 or self.size == 0:
            if self.shape:
                return np.array([]).reshape(0, *self.shape)
            else:
                return np.array([])
                
        n = min(n, self.size)
        
        if not self.is_full:
            return self.buffer[max(0, self.size - n):self.size].copy()
        else:
            if n <= self.head:
                return self.buffer[self.head - n:self.head].copy()
            else:
                return np.concatenate([
                    self.buffer[self.capacity - (n - self.head):],
                    self.buffer[:self.head]
                ])
                
    def mean(self):
        """Get mean of all items"""
        if self.size == 0:
            return 0.0
        return np.mean(self.get_all())
        
    def std(self):
        """Get standard deviation of all items"""
        if self.size == 0:
            return 0.0
        return np.std(self.get_all())
        
    def __len__(self):
        return self.size
        
    def __bool__(self):
        return self.size > 0
        
    def clear(self):
        """Clear the buffer"""
        self.head = 0
        self.tail = 0
        self.size = 0
        self.is_full = False
