"""
U-M Shapiro Design Lab
Daniel Hou @2024

This module handles on-disk file IO, particularly, it
- Load and Save images
- Transform images with desired filters 
- Convert image formats
- Package images for serial transmission. 

This module also provides interface with strategies. 
"""

from abc import ABC, abstractmethod
import uuid
import os
import re
import json

from module.utils import LimitedID

from .config import CHUNK_SIZE, DYNAMIC_LOADING, TYPE_IMG, TYPE_TXT, TYPE_VID, TYPE_UNKNOWN, \
    README_REGEX_PATTERN, TXT_EXTS, IMG_EXTS, VID_EXTS, IMG_WIDTH_FULL, IMG_HEIGHT_FULL, \
    IMG_WIDTH_HALF, IMG_HEIGHT_HALF, ERR_NOT_LOADED

class FileLoader:
    """
    Loads directory and gets file dictionary
    """
    def __init__(self, root, clear_cache=True):
        self.uuid_dict = {}
        self.root_path = self.__find_first_sd_path(root)
        
        self.activities = self.__build_act_dict(self.root_path)
        if clear_cache:
            os.system(f"rm -r {CACHE_PATH}/*")
        
    def __find_first_sd_path(self, root):
        """Return the first directory found in root"""
        for directory in os.listdir(root):
            if os.path.isdir(os.path.join(root, directory)):
                print(f"Found SD Root {os.path.join(root, directory)}")
                return os.path.join(root, directory)

    def __build_act_dict(self, root_path, depth=0):
        """
        Build dictionary of activities: 
            - activity, then files
        """
        acts = {}  # name from macOS finder :)
        for directory in os.listdir(root_path):
            dpath = os.path.join(root_path, directory)
            # Get all directories that are not hidden to be classes
            if os.path.isdir(dpath) and not directory.startswith('.'):
                finder = []
                for f in os.listdir(root_path):
                    if f.startswith('.'): 
                        continue
                    f = os.path.join(dpath, f)
                    if os.path.isfile(f) and self.__get_file_type(f) is not TYPE_UNKNOWN:
                        wrapper = self.__factory(f)
                        finder.append((f, wrapper))
                        self.uuid_dict[wrapper.uuid] = wrapper
                acts[directory] = finder
        return acts

    @staticmethod
    def __get_file_type(path):
        """Get type of file, out of image, text, video, or unknown"""
        # Ignore hidden files
        if os.path.basename(path.lower()).startswith('.'):
            return TYPE_UNKNOWN
        
        # Ignore README files
        if re.match(README_REGEX_PATTERN, path):
            return TYPE_UNKNOWN
        
        # Find the last thing of the file name split by the dot operator
        ext = os.path.basename(path.lower()).split('.')[-1]
        if ext in TXT_EXTS: return TYPE_TXT
        if ext in IMG_EXTS: return TYPE_IMG
        if ext in VID_EXTS: return TYPE_VID
        return TYPE_UNKNOWN

    def __factory(self, file_path):
        """Create a wrapper for a file given a path"""
        ftype = FileLoader.__get_file_type(file_path)
        if ftype == TYPE_TXT:
            return TextWrapper(file_path)
        if ftype == TYPE_IMG:
            return ImageWrapper(file_path)
        # Otherwise, it must be video
        return VideoWrapper(file_path)

    def __iterate(self):
        """Generator for iterating over the file dictionary"""
        for (activity, la) in self.activities.items():
            for f in la:
                yield activity, f

class FileWrapper(ABC):
    """ The base class for a file """
    def __init__(self, path):
        self.raw_path = path

        # Loaded parameters
        self.loaded = False
        self.content = None
        self.uuid = uuid.uuid4()
    
    @abstractmethod
    def load(self):
        pass

    @abstractmethod
    def messages(self):
        pass

class TextWrapper(FileWrapper):
    """Wrapper for text files"""
    X_START = 40
    Y_START = 40
    Y_INTERVAL = 80

    def __init__(self, path):
        super(TextWrapper, self).__init__(path)
        self.bg_color = b'\xf7\x9e'
        self.font_color = b'\x08\x61'
        self.load()

    def load(self):
        """
        Load text content into self.content
        """
        if self.loaded:
            return
        try:
            # Read JSON file
            with open(self.raw_path, 'r') as json_file:
                data = json.load(json_file)
                tbytes = [l["bytes"] for l in data["lines"]]
                for tb in tbytes:
                    if tb[-1] != b'\x00':
                        tb += b'\x00'
                self.content = [self.to_bytes(b) for b in tbytes]
                self.fonts = [l["font"] for l in data["lines"]]
                self.loaded = True
                return True
            print(f"File {self.raw_path} not found.")
            return False
        except json.JSONDecodeError:
            print("Error decoding JSON.")
            return False
        
    def to_bytes(self, ascii_string):
        """Convert an ASCII string back into a raw byte array."""
        byte_values = ascii_string.split()
        return bytearray(int(byte, 16) for byte in byte_values)
    
    def build_text_msg(self):
        total_msg = bytes()
        for i, (tbytes, font_id) in enumerate(zip(self.content, self.fonts)):
            msg = bytearray([self.X_START, self.Y_START+i*self.Y_INTERVAL, font_id, len(tbytes)])
            total_msg += (bytes(msg) + tbytes)
        return total_msg
    
    def messages(self):
        yield self.bg_color + self.font_color + bytes(len(self.content)) + self.build_text_msg()
        

class ImageWrapper(FileWrapper):
    CHUNK_SIZE = 8192
    next_id = LimitedID()

    """Image Wrapper"""
    def __init__(self, path):
        super(ImageWrapper, self).__init__(path)
        self.id = self.next_id()
        self.content = None
        self.load(path)

    def load(self, path):
        if self.loaded:
            return
        """Loads the image from the file and queues it for processing."""
        with open(path, 'rb') as file:
            content = bytearray(file.read())
            self.img_size = len(content).to_bytes(4, byteorder='big')
            chunks = []
            for begin in range(0, len(content), CHUNK_SIZE):
                end = min(len(content), begin+CHUNK_SIZE)
                chunks.append(content[begin:end])
            self.content = chunks

    def image_header_msg(self):
        return bytes([self.id, 0, 0]) + self.img_size + bytes([len(self.content)])

    def messages(self):
        pass
        

class VideoWrapper(FileWrapper):
    """Video Wrapper"""
    def __init__(self, path):
        super(VideoWrapper, self).__init__(path)
        self.total_frame_cnt = 0
        self.processed_frame_cnt = 0
        self.next_frame_id = 0
        self.processed_path = []

    def load(self):
        """return binary content from this wrapper for esp encoding"""
        if self.processed_frame_cnt <= self.next_frame_id:
            return ERR_NOT_LOADED

        # Get image path for next frame
        img_path = os.path.join(self.processed_path[self.next_frame_id], f"{self.next_frame_id}.jpg")
        self.next_frame_id += 1
        if self.next_frame_id >= self.total_frame_cnt:
            self.next_frame_id = 0

        with open(img_path, 'rb') as f:
            binary_data = f.read()
        return binary_data
    
    def messages(self):
        pass

if __name__ == "__main__":
    print("Library Only!")
    
