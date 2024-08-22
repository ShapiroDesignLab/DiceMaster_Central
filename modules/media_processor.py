"""Media processing library"""

import os
import multiprocessing
from collections import deque
from time import sleep
from abc import ABC, abstractmethod

# Image imports
import cv2
from PIL import Image

# Configuration
from .config import CACHE_PATH


SLEEP_TIME = 0.001      # 1ms sleep time


class BaseProcessor(ABC):
    """Processor base class"""
    def __init__(self):
        self.task_queue = multiprocessing.Queue()
        # self.task_queue = deque()
        self.result_queue = multiprocessing.Queue()
        self.process = None
        self.started = False
        
    def __del__(self):
        if self.process is not None:
            self.process.terminate()

    def async_enqueue(self, uuid, raw_path, target_width, target_height):
        """Enqueue an image for processing."""
        self.task_queue.put((uuid, raw_path, target_width, target_height))

    def sync_enqueue(self, uuid, raw_path, target_width, target_height):
        """Enqueue an image for processing."""
        self.task_queue.put((uuid, raw_path, target_width, target_height))

    def run(self):
        """Send shutdown signal to the processing loop."""
        if self.started is True:
            return
        self.process = multiprocessing.Process(target=self.process_worker, args=(self.task_queue,self.result_queue))
        self.process.start()
        self.started = True
        
    def wake(self):
        """Wake up the process for service"""
        self.run()
        
    def sleep(self):
        """Put process to sleep, i.e. deleting it upon everything finishing up"""
        if self.process is None:
            return
        while self.process.is_alive():
            sleep(1)
        self.process.close()

    def fetch_results(self):
        """Retrieve all processed images from the result queue."""
        processed_images = []
        while not self.result_queue.empty():
            processed_images.append(self.result_queue.get())
        return processed_images

    @abstractmethod
    def process_worker(self, task_queue, result_queue):
        """Function to process images, to be run in a separate process."""
        pass
        

class ImageProcessor(BaseProcessor):
    """Processor for images"""
    def __init__(self):
        super(ImageProcessor, self).__init__()

    def process_worker(self, task_queue, result_queue):
        """Function to process images, to be run in a separate process."""
        while True:
            if task_queue.empty():
                sleep(SLEEP_TIME)        # Keep process alive during entire program
                continue

            uuid, raw_path, target_width, target_height = task_queue.get()
            img = Image.open(raw_path)
            img = ImageProcessor.resize_image_aspect_ratio(
                img, target_width, target_height)
            img = ImageProcessor.crop_center(img, target_width, target_height)
            path = ImageProcessor.save_rotated_images(img, uuid)
            result_queue.put((uuid, path))

    @staticmethod
    def resize_image_aspect_ratio(img, target_width, target_height):
        """Resize Image while retaining aspect ratio"""
        original_width, original_height = img.size
        # If already cropped by user, just exit
        if img.width == target_width and img.height == target_height:
            return img
        width_ratio = target_width / original_width
        height_ratio = target_height / original_height
        larger_ratio = max(width_ratio, height_ratio)

        new_width = int(original_width * larger_ratio)
        new_height = int(original_height * larger_ratio)
        new_size = (new_width, new_height)

        resized_img = img.resize(new_size, Image.Resampling.LANCZOS)
        return resized_img

    @staticmethod
    def crop_center(img, target_width, target_height):
        """Crop Image to Center"""
        img_width, img_height = img.size
        # If already cropped by user, just exit
        if img.width == target_width and img.height == target_height:
            return img
        # Otherwise, process
        left = (img_width - target_width) / 2
        top = (img_height - target_height) / 2
        right = (img_width + target_width) / 2
        bottom = (img_height + target_height) / 2
        cropped_img = img.crop((left, top, right, bottom))
        return cropped_img

    @staticmethod
    def save_rotated_images(img, uuid):
        """Save 4 rotated images of the same processed image"""
        rotations = [90, 180, 270, 0]
        for angle in rotations:
            rotated_img = img.rotate(angle)
            filename = f"{uuid}_{angle}.png"
            save_path = os.path.join(CACHE_PATH, filename)
            rotated_img.save(save_path, "PNG")
            if angle == 0:  # Store path of the 0 degree rotated image
                return save_path

class VideoProcessor(BaseProcessor):
    """Processor for video files"""
    def __init__(self):
        super(VideoProcessor, self).__init__()

    def process_worker(self, task_queue, result_queue):
        """Function to process videos, running in a separate process."""
        while True:
            if task_queue.empty():
                sleep(SLEEP_TIME)        # Keep process alive during entire program
                continue

            uuid, raw_path, target_width, target_height = task_queue.get()
            cap = cv2.VideoCapture(raw_path)
            if not cap.isOpened():
                print(f"Error: Cannot open video {raw_path}")
                continue

            frame_cnt = 0
            save_dir = os.path.join(CACHE_PATH, str(uuid))
            os.makedirs(save_dir, exist_ok=True)

            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                frame = self.resize_and_crop(
                    frame, target_width, target_height)
                # self.save_rotated_frames(frame, frame_cnt, save_dir)
                self.result_queue.put((uuid, save_dir, frame_cnt))
                frame_cnt += 1
            cap.release()

    @staticmethod
    def resize_and_crop(frame, target_width, target_height):
        """Resize and crop the frame to the target dimensions."""
        height, width = frame.shape[:2]
        # Calculate ratios and determine which ratio to use for scaling
        width_ratio = target_width / width
        height_ratio = target_height / height
        if width_ratio > height_ratio:
            new_width = target_width
            new_height = int(height * width_ratio)
        else:
            new_height = target_height
            new_width = int(width * height_ratio)
        # Resize the frame
        resized_frame = cv2.resize(
            frame, (new_width, new_height), interpolation=cv2.INTER_AREA)
        # Crop the center
        start_x = (new_width - target_width) // 2
        start_y = (new_height - target_height) // 2
        cropped_frame = resized_frame[start_y:start_y +
                                      target_height, start_x:start_x + target_width]
        return cropped_frame


if __name__ == "__main__":
    print("Error, calling module media_processor directly!")
