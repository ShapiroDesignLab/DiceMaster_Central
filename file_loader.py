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

import uuid
import os

from media_processor import VideoProcessor, ImageProcessor
import config

# Macros
from utils import *

class FileLoader:
    """
    Loads directory and gets file dictionary
    """
    def __init__(self, root, clear_cache=True):
        self.uuid_dict = {}
        self.root_path = self.find_valid_sd_path(root)
        ImageWrapper.processor.run()
        VideoWrapper.processor.run()
        
        self.finder = self.build_file_dict(self.root_path)
        if clear_cache:
            os.system(f"rm -r {config.CACHE_PATH}/*")
        
    def find_valid_sd_path(self, root):
        """Return the first directory found in root"""
        for directory in os.listdir(root):
            if os.path.isdir(os.path.join(root, directory)):
                print(f"Found SD Root {os.path.join(root, directory)}")
                return os.path.join(root, directory)

    def build_file_dict(self, root_path, depth=0):
        """
        Build dictionary of activities: 
            - class, session, activity, then files (no more directory detection)
        """
        if depth == 3:  # If at the end
            finder = []
            for f in os.listdir(root_path):
                f = os.path.join(root_path, f)
                if os.path.isfile(f) and self._get_file_type(f) is not TYPE_UNKNOWN:
                    wrapper = self.factory(f)
                    finder.append((f, wrapper))
                    self.uuid_dict[wrapper.uuid] = wrapper
            return finder

        # Otherwise Recurse down
        finder = {}  # name from macOS finder :)
        for directory in os.listdir(root_path):
            dpath = os.path.join(root_path, directory)
            # Get all directories that are not hidden to be classes
            if os.path.isdir(dpath) and not directory.startswith('.'):
                finder[directory] = self.build_file_dict(dpath, depth+1)
        return finder

    @staticmethod
    def _get_file_type(path):
        """Get type of file, out of IMG, """
        # Ignore hidden files
        if os.path.basename(path.lower()).startswith('.'):
            return TYPE_UNKNOWN
        
        # Find the last thing of the file name split by the dot operator
        ext = os.path.basename(path.lower()).split('.')[-1]
        if ext in TXT_EXTS:
            return TYPE_TXT
        if ext in IMG_EXTS:
            return TYPE_IMG
        if ext in VID_EXTS:
            return TYPE_VID
        return TYPE_UNKNOWN

    def factory(self, file_path):
        ftype = FileLoader._get_file_type(file_path)
        if ftype == TYPE_TXT:
            return TextWrapper(file_path)
        if ftype == TYPE_IMG:
            return ImageWrapper(file_path)
        if ftype == TYPE_VID:
            return VideoWrapper(file_path)

    def iterate(self):
        """Generator for iterating over the file dictionary"""
        for (course, dc) in self.finder.items():
            for (session, ds) in dc.items():
                for (activity, la) in ds.items():
                    for f in la:
                        yield course, session, activity, f

    def visualize(self):
        """Debug only: print valid files detected"""
        print("Found the following valid files: ")
        for _,_,_, f in self.iterate():
            print(f[0])
            
    def update_processors(self, _verbose=False):
        """
        TO BE CALLED IN MAIN THREAD
        
        Fetches results from the other process
        """
        processed_images = ImageWrapper.processor.fetch_results()
        for (uid, path) in processed_images:
            self.uuid_dict[uid].processed_path = path
            print(f"Processed Image {os.path.basename(self.uuid_dict[uid].raw_path)}")
        processed_videos = VideoWrapper.processor.fetch_results()
        for (uid, path, frame_id) in processed_videos:
            self.uuid_dict[uid].processed_frame_cnt = frame_id
            print(f"Processed Frame for {os.path.basename(self.uuid_dict[uid].raw_path)}")


class FileWrapper:
    """ The base class for a file """
    processor = ImageProcessor()
    def __init__(self, path):
        self.raw_path = path
        self.raw_size = self.fsize(self.raw_path)

        # Loaded parameters
        self.loaded = False
        self.uuid = uuid.uuid4()
        self.processed_path = None
        self.processed_size = None

    def fsize(self, path):
        """Get file size"""
        return os.path.getsize(path)


class TextWrapper(FileWrapper):
    """Wrapper for text files"""

    def __init__(self, path):
        super(TextWrapper, self).__init__(path)
        if config.DYNAMIC_LOADING is False: 
            self._load()

    def _load(self):
        """Load text content"""
        self.loaded = True

    def get(self):
        """Get content to send, in this case, raw string"""
        with open(self.raw_path, 'r', encoding='utf-8') as file:
            return file.read().rstrip('\n')

    def get_esp_encode(self):
        """return encoded bytes for ESP"""
        return self.get()


class ImageWrapper(FileWrapper):
    """Image Wrapper"""

    def __init__(self, path):
        super(ImageWrapper, self).__init__(path)
        if config.DYNAMIC_LOADING is False: 
            self._load()

    def _load(self):
        """Loads the image from the file and queues it for processing."""
        ImageWrapper.processor.enqueue(self.uuid, self.raw_path, IMG_WIDTH_FULL, IMG_HEIGHT_FULL)

    def get(self, rotation=0):
        """return content from this wrapper"""
        if self.loaded is False:
            return ERR_NOT_LOADED
        with open(self.processed_path, 'rb') as file:
            binary_data = file.read()
        return binary_data

    def get_readable(self, rotation=0):
        """return encoded bytes for ESP"""
        content = self.get()
        if content is not ERR_NOT_LOADED:
            return content
        raise KeyError("File Not Processed Yet!")


class VideoWrapper(FileWrapper):
    """Video Wrapper"""
    processor = VideoProcessor()
    def __init__(self, path):
        super(VideoWrapper, self).__init__(path)
        self.total_frame_cnt = 0
        self.processed_frame_cnt = 0
        self.next_frame_id = 0
        self.processed_path = []
        if config.DYNAMIC_LOADING is False:
            self._load()

    def _load(self):
        """processes the video"""
        VideoWrapper.processor.enqueue(self.uuid, self.raw_path, IMG_WIDTH_HALF, IMG_HEIGHT_HALF)

    def get(self, rotation=0):
        """return binary content from this wrapper for esp encoding"""
        if self.processed_frame_cnt <= self.next_frame_id:
            return ERR_NOT_LOADED

        # Get image path for next frame
        img_path = os.path.join(self.processed_path, f"{self.next_frame_id}_{rotation}.jpg")
        self.next_frame_id += 1
        if self.next_frame_id >= self.total_frame_cnt:
            self.next_frame_id = 0

        with open(img_path, 'rb') as f:
            binary_data = f.read()
        return binary_data


if __name__ == "__main__":
    print("Error, calling module file directly!")
