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

from .config import DYNAMIC_LOADING, TYPE_IMG, TYPE_TXT, TYPE_VID, TYPE_UNKNOWN, \
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
        self.raw_size = self.fsize(self.raw_path)

        # Loaded parameters
        self.loaded = False
        self.content = None
        self.uuid = uuid.uuid4()

    def fsize(self, path):
        """Get file size"""
        return os.path.getsize(path)
    
    @abstractmethod
    def load(self):
        pass

    @abstractmethod
    def release(self):
        del self.content
        self.content = None
        self.loaded = False

    @abstractmethod
    def to_bytes(self):
        pass




class TextWrapper(FileWrapper):
    """Wrapper for text files"""

    def __init__(self, path):
        super(TextWrapper, self).__init__(path)
        self.load()

    def load(self):
        """Load text content"""
        if self.loaded:
            return
        try:
            # Read JSON file
            with open(self.raw_path, 'r') as json_file:
                data = json.load(json_file)
                bytes = [l["bytes"] for l in data["lines"]]
                self.content = [self.to_bytes(b) for b in bytes]
                self.loaded = True
                return True
        except FileNotFoundError:
            print(f"File {self.raw_path} not found.")
            return False
        except json.JSONDecodeError:
            print("Error decoding JSON.")
            return False

    @staticmethod
    def to_bytes(ascii_string):
        """return encoded bytes for ESP"""
        """Convert an ASCII string back into a raw byte array."""
        byte_values = ascii_string.split()
        return bytearray(int(byte, 16) for byte in byte_values)


class ImageWrapper(FileWrapper):
    """Image Wrapper"""
    def __init__(self, path):
        super(ImageWrapper, self).__init__(path)
        self.content = None

    def load(self):
        if self.loaded == True:
            return
        """Loads the image from the file and queues it for processing."""
        self.processed_path = ImageWrapper.processor.enqueue(self.uuid, self.raw_path, IMG_WIDTH_FULL, IMG_HEIGHT_FULL)
        with open(self.processed_path, 'rb') as file:
            self.content = file.read()
        
    def get(self):
        """return content from this wrapper"""
        self.load()
        if self.loaded is False or self.processed_path is None:
            return None
        
        return self.content

    def to_bytes(self):
        """return encoded bytes for ESP"""
        return self.get()

class VideoWrapper(FileWrapper):
    """Video Wrapper"""
    def __init__(self, path):
        super(VideoWrapper, self).__init__(path)
        self.total_frame_cnt = 0
        self.processed_frame_cnt = 0
        self.next_frame_id = 0
        self.processed_path = []

    def get(self):
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

    def to_bytes(self):
        return self.get

if __name__ == "__main__":
    print("Error, calling module file directly!")
