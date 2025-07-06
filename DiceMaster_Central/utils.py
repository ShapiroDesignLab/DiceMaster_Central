import numpy as np

class RingBufferNP:
    """
    The RingBufferNP class provides a Ring Buffer implementation for storing history values efficiently. 
    """
    def __init__(self, shape):
        # Make Buffer
        self.shape = shape
        self.buffer = np.zeros(shape=shape, dtype=np.float32)

        # Make Pointers
        self.front_ptr = 0  # On the next writable site
        self.back_ptr = 0  # On the last 
        self.size = 0

    def __len__(self):
        return self.size
    
    def full(self):
        return self.size == self.shape[0]
    
    def empty(self):
        return self.size == 0

    def safe_push_front(self, item):
        """"""
        if self.full():
            raise Exception("Buffer Full! To overwrite, use append()")
        self.push_front(item)

    def push_front(self, item):
        """
        Append item to Ring Buffer
        """
        if self.size == self.shape[0]:                   # If full, remove an item first
            self.pop_tail()
        self.buffer[self.front_ptr] = item                      # Finally add item
        self.front_ptr = (self.front_ptr + 1) % self.size       
        self.size += 1

    def pop_tail(self):
        if self.empty(): 
            return
        self.back_ptr = (self.back_ptr + 1) % self.size
        self.size -= 1
    
    def get_items(self):
        if self.empty():            # Empty ring returns nothing
            return np.zeros(shape=(1,self.shape[1]))
        if self.front_ptr > self.back_ptr:
            return self.buffer[self.back_ptr:self.front_ptr, :].reshape(-1, self.shape[1])
        if self.front_ptr < self.back_ptr:
            return np.concatenate((self.buffer[self.back_ptr:, :], self.buffer[:self.front_ptr, :])).reshape(-1, self.shape[1])
        return self.buffer
    

class LimitedID:
    def __init__(self, init_id=0, max_id=256):
        self.next_id = init_id-1
        self.max_id = max_id

    def __call__(self):
        self.next_id = (self.next_id+1)%self.max_id
        return self.next_id

def HIBYTE(val):
    return (val >> 8) & 0xFF

def LOBYTE(val):
    return val & 0xFF