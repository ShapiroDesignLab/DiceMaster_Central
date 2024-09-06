"""Media processing library"""

import os
import json
import re

# from langdetect import detect
import cv2
from PIL import Image

STATUS_UNPROCESSED = 0
STATUS_EXIST = 1
STATUS_SUCCESS = 2
STATUS_FAIL = 3

class BaseProcessor:
    def __init__(self, src_path, target_path):
        self.src_name = os.path.basename(src_path)
        self.src_path = src_path
        self.target_path = target_path
        if not os.path.isdir(self.target_path):
            os.makedirs(self.target_path)

class ImageProcessor(BaseProcessor):
    """Processor for images"""
    def __init__(self, src_path, target_path):
        super(ImageProcessor, self).__init__(src_path, target_path)
        self.target_width = 480
        self.target_height= 480

    def process(self, force=False):
        """Function to process images, to be run in a separate process."""
        if not force and self.exists():
            return STATUS_EXIST
        try:
            img = Image.open(self.src_path)
            img = ImageProcessor.resize_image_aspect_ratio(
                img, self.target_width, self.target_height)
            img = ImageProcessor.crop_center(img, self.target_width, self.target_height)
            save_path = os.path.join(self.target_path, self.src_name)
            img.save(save_path, "JPEG")
            return STATUS_SUCCESS
        except:
            print("Image Processing failed")
        return STATUS_FAIL

    def exists(self):
        """Skip file sthat are """
        # If file does not exist, then false
        if not os.path.isfile(os.path.join(self.target_path, self.src_name)):
            return False
        # Try open image and investigate
        try:
            img = Image.open(self.src_path)
            if not (img.width == self.target_width and img.height == self.target_height):
                return False
            return True
        except:
            print("Image Processing failed")
        return False


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

class VideoProcessor(ImageProcessor):
    """Processor for video files"""
    def __init__(self, src_path, target_path):
        super(VideoProcessor, self).__init__(src_path, target_path)
        self.target_width = 240
        self.target_height= 240
        self.target_path = os.path.join(self.target_path, self.src_name.split('.')[0])
        os.makedirs(self.target_path, exist_ok=True)

    def process(self, force=False):
        """Function to process videos, saving frames as images."""
        cap = cv2.VideoCapture(self.src_path)
        if not cap.isOpened():
            print(f"Error: Cannot open video {self.src_path}")
            return STATUS_FAIL

        frame_id = 0
        while True:
            # try:
            ret, frame = cap.read()
            if not ret: 
                break
            save_frame_path = os.path.join(self.target_path, f"{self.src_name.split('.')[0]}_{frame_id}.jpg")
            
            # Check if the frame already exists, skip if it does
            if os.path.exists(save_frame_path):
                frame_id += 1
                continue
            
            frame = self.resize_and_crop(frame, self.target_width, self.target_height)
            cv2.imwrite(save_frame_path, frame)  # Save each frame as a JPEG
            frame_id += 1
            # except Exception as e:
            #     print(f"Video Processing failed for frame {frame_id}: {e}")
            #     return STATUS_FAIL
        
        cap.release()
        return STATUS_SUCCESS

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


class TextProcessor(BaseProcessor):
    """Processor for text files"""
    def __init__(self, src_path, target_path):
        super(TextProcessor, self).__init__(src_path, target_path)
        self.target_json = os.path.join(self.target_path, self.src_name.split('.')[0] + ".json")

    def process(self, force=False):
        """Process the text file to identify language and prepare for rendering."""
        if os.path.exists(self.target_json):
            return STATUS_EXIST

        result = {
            "file_name": self.src_name,
            "lines": []
        }
        
        with open(self.src_path, "r", encoding="utf-8") as file:
            for line in file:
                line = line.strip()
                line_data = self.process_line(line)
                if line_data:
                    result["lines"].append(line_data)

        # Save the result to a JSON file
        with open(self.target_json, "w", encoding="utf-8") as json_file:
            json.dump(result, json_file, ensure_ascii=False, indent=4)

        print(f"Processed text and saved to {self.target_json}")
        return STATUS_SUCCESS

    def process_line(self, line):
        """Process a single line, determining language, position, and encoding text chunk."""
        if not line:
            return None

        # Convert to UTF-8 byte array and add '\0'
        utf8_bytes = line.encode('utf-8') + b'\0'
        
        if len(utf8_bytes) > 255:
            return None

        line_data = {
            "text": line,
            "language": self.determine_language(line),
            "cursor_position": self.compute_cursor_position(line),
            "length": len(utf8_bytes),
            "bytes": self.bytes_to_ascii(utf8_bytes)
        }
        return line_data

    def determine_language(self, text):
        """Determine the language of the text by its characters."""
        if re.search(r"[\u4e00-\u9FFF]", text):
            return "Chinese"
        elif re.search(r"[\u0400-\u04FF]", text):
            return "Cyrillic"
        elif re.search(r"[\u0600-\u06FF]", text):
            return "Arabic"
        elif re.search(r"[\u0900-\u097F]", text):
            return "Hindi"
        else:
            return "English"

    def compute_cursor_position(self, text):
        """Compute cursor position for text in a 480x480 canvas using font 11 u8g2."""
        max_chars_per_line = 40  # Approximation for font 11
        x_cursor = 0
        y_cursor = 0

        lines = [text[i:i + max_chars_per_line] for i in range(0, len(text), max_chars_per_line)]
        chunk_count = len(lines)

        # Calculate Y cursor (spacing 11 pixels per line, start at y = 10)
        y_cursor = 10 + chunk_count * 11

        return {"x": x_cursor, "y": y_cursor}

    @staticmethod
    def bytes_to_ascii(byte_array):
        """Convert a byte array into an ASCII string representation."""
        return ' '.join(f'{byte:02X}' for byte in byte_array)

    @staticmethod
    def ascii_to_bytes(ascii_string):
        """Convert an ASCII string back into a raw byte array."""
        byte_values = ascii_string.split()
        return bytearray(int(byte, 16) for byte in byte_values)