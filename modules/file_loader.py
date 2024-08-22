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

from media_processor import VideoProcessor, ImageProcessor
from .config import DYNAMIC_LOADING, CACHE_PATH, TYPE_IMG, TYPE_TXT, TYPE_VID, TYPE_UNKNOWN, \
    README_REGEX_PATTERN, TXT_EXTS, IMG_EXTS, VID_EXTS, IMG_WIDTH_FULL, IMG_HEIGHT_FULL, \
    IMG_WIDTH_HALF, IMG_HEIGHT_HALF, ERR_NOT_LOADED

class FileLoader:
    """
    Loads directory and gets file dictionary
    """
    def __init__(self, root, clear_cache=True):
        self.uuid_dict = {}
        self.root_path = self.__find_first_sd_path(root)
        ImageWrapper.processor.run()
        VideoWrapper.processor.run()
        
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

    def __visualize(self):
        """Debug only: print valid files detected"""
        print("Found the following valid files: ")
        for _, f in self.__iterate():
            print(f[0])
            
    def update(self):
        """
        Fetches results from the processors
        """
        processed_images = ImageWrapper.processor.fetch_results()
        for (uid, path) in processed_images:
            self.uuid_dict[uid].processed_path = path
            print(f"Processed Image {os.path.basename(self.uuid_dict[uid].raw_path)}")
        processed_videos = VideoWrapper.processor.fetch_results()
        for (uid, path, frame_id) in processed_videos:
            self.uuid_dict[uid].processed_frame_cnt = frame_id
            print(f"Processed Frame for {os.path.basename(self.uuid_dict[uid].raw_path)}")

class FileWrapper(ABC):
    """ The base class for a file """
    def __init__(self, path):
        self.raw_path = path
        self.raw_size = self.fsize(self.raw_path)

        # Loaded parameters
        self.loaded = False
        self.content = None
        self.uuid = uuid.uuid4()
        self.processed_path = None
        self.processed_size = None

    def fsize(self, path):
        """Get file size"""
        return os.path.getsize(path)
    
    @abstractmethod
    def load(self):
        pass

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
        if DYNAMIC_LOADING is False: 
            self.load()

    def load(self):
        """Load text content"""
        if self.loaded:
            return
        with open(self.raw_path, 'r', encoding='utf-8') as file:
            self.content = file.read().rstrip('\n')
        self.loaded = True

    def get(self):
        """Get content to send, in this case, raw string"""
        self.load()
        return self.content

    def to_bytes(self):
        """return encoded bytes for ESP"""
        return self.get()


class ImageWrapper(FileWrapper):
    """Image Wrapper"""
    processor = ImageProcessor()
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
    processor = VideoProcessor()
    def __init__(self, path):
        super(VideoWrapper, self).__init__(path)
        self.total_frame_cnt = 0
        self.processed_frame_cnt = 0
        self.next_frame_id = 0
        self.processed_path = []

    def load(self):
        """processes the video"""
        VideoWrapper.processor.enqueue(self.uuid, self.raw_path, IMG_WIDTH_HALF, IMG_HEIGHT_HALF)

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
