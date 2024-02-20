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

DICEMASTER_FORMATS = ['.jpg', '.jpeg', '.png', '.svg', '.bmp', '.gif']

def loadImage(img_path: str):

  # If parameter is not string, raise error
  if not isinstance(img_path, str):
    raise("[Files loadImage] Error: invalid path argument. Path must be a string")
  
  # Check if file exists on disk
  if not os.path.isfile(img_path):
    raise(f"[Files loadImage] Error: file {img_path} could not be found!")

  # Check if file has supported extension
  if not os.path.isfile(img_path):
    raise(f"[Files loadImage] Error: file {img_path} format is unsupported!")

  im = Image.open(img_path)
  return im
  

# Dummy for testing this library
def main():
  pass

if __name__ == "__main__":
  main()