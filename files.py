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

from PIL import Image
import os


class ImgPlayer():

  DICEMASTER_FORMATS = ['.jpg', '.jpeg', '.png', '.svg', '.bmp']

  def __init__():
    pass
  
  @classmethod
  def loadImage(img_path: str):
    """
    Returns PIL Image object from file
    """
    # If parameter is not string, raise error
    if not isinstance(img_path, str):
      raise ValueError("[Files loadImage] Error: invalid path argument. Path must be a string")
    
    # Check if file exists on disk
    if not os.path.isfile(img_path):
      raise ValueError(f"[Files loadImage] Error: file {img_path} could not be found!")

    # Check if file has supported extension
    if not os.path.isfile(img_path):
      raise ValueError(f"[Files loadImage] Error: file {img_path} format is unsupported!")

    im = Image.open(img_path)
    return im

  @classmethod
  def resize_image_aspect_ratio(img, target_width=None, target_height=None):
      original_width, original_height = img.size
      
      # Calculate the ratios needed to resize to the target dimensions
      width_ratio = target_width / original_width
      height_ratio = target_height / original_height
      
      # Use the larger ratio to ensure the image covers the target size
      larger_ratio = max(width_ratio, height_ratio)
      
      new_width = int(original_width * larger_ratio)
      new_height = int(original_height * larger_ratio)
      new_size = (new_width, new_height)
      
      resized_img = img.resize(new_size, Image.Resampling.LANCZOS)
      return resized_img

  @classmethod
  def crop_center(img, target_width, target_height):
      img_width, img_height = img.size
      left = (img_width - target_width) / 2
      top = (img_height - target_height) / 2
      right = (img_width + target_width) / 2
      bottom = (img_height + target_height) / 2
      
      cropped_img = img.crop((left, top, right, bottom))
      return cropped_img

  @classmethod
  def saveAsBMP(img, filename):
    img.save(filename+'.bmp')


class FilePlayer():

  def __init__(self, root_path="./"):
    self.root_path = root_path
    exist_config, config_path = self.check_config_file(root_path)
    if not exist_config:
       raise ValueError(f"Config File for {self.root_path} not found!")
    self.config_path = config_path


  @classmethod
  def check_config_file(self, root_dir):
    # Construct the absolute path for the config.py file
    config_file_path = os.path.join(root_dir, 'config.py')
    
    # Check if the config.py file exists in the root directory
    if os.path.isfile(config_file_path):
        # Return True and the absolute path of config.py without a backslash at the end
        return True, os.path.abspath(config_file_path).rstrip('/')
    else:return False, None



# Dummy for testing this library
def main():
  player = ImgPlayer()

  block_m = player.loadImage("./block_m.png")
  resized_block = player.resize_image_aspect_ratio(block_m, 128,128)
  cropped_img = player.crop_center(resized_block, 128, 128)
  player.saveAsBMP(cropped_img, "block_m")

if __name__ == "__main__":
  main()