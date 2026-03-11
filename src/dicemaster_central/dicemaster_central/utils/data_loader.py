"""
U-M Shapiro Design Lab
Daniel Hou @2024

Dataset Loader Module for DiceMaster Central

This module provides functionality for loading directories and building a dictionary
of files filtered by ContentTypeExts. It recursively scans directories and returns
a structured representation of valid game files.
"""

import os
import argparse
from typing import Dict, Union
from dicemaster_central.constants import ContentTypeExts


def load_directory(directory_path: str) -> Dict[str, Union[str, Dict]]:
    """
    Recursively load a directory and build a dictionary of files filtered by ContentTypeExts.
    
    Args:
        directory_path: Path to the directory to scan
        
    Returns:
        Dictionary representing the file structure where:
        - Regular files (json, jpg, jpeg) are represented as strings (file paths)
        - GIF directories (.gif.d) are represented as strings (directory paths)
        - Subdirectories containing valid files are represented as nested dictionaries
    """
    if not os.path.exists(directory_path) or not os.path.isdir(directory_path):
        return {}
    
    directory_tree = {}
    
    try:
        for item in os.listdir(directory_path):
            item_path = os.path.join(directory_path, item)
            
            if os.path.isfile(item_path):
                # Check if file has a valid extension
                if is_valid_file(item_path):
                    directory_tree[item] = item_path
                        
            elif os.path.isdir(item_path):
                # Special handling for GIF directories (.gif.d)
                if item.endswith('.gif.d'):
                    # For GIF directories, store as string path instead of recursing
                    directory_tree[item] = item_path
                else:
                    # Recursively process subdirectory
                    sub_dir = load_directory(item_path)
                    if sub_dir:  # Only include if it contains valid files
                        directory_tree[item] = sub_dir
                        
    except PermissionError:
        # Skip directories we can't access
        pass
    except Exception as e:
        # Log other errors but continue processing
        print(f"Warning: Error processing {directory_path}: {e}")
    return directory_tree


def is_valid_file(file_path: str) -> bool:
    """
    Check if a file has a valid extension according to ContentTypeExts.
    
    Args:
        file_path: Path to the file to check
        
    Returns:
        True if the file has a valid extension, False otherwise
    """
    file_ext = os.path.splitext(file_path)[1][1:].lower()  # Remove the dot
    
    for extensions in ContentTypeExts.values():
        if file_ext in extensions:
            return True
    return False


def print_tree(data: Dict[str, Union[str, Dict]], prefix: str = "", is_last: bool = True):
    """
    Print the directory structure in a tree format.
    
    Args:
        data: Dictionary representing the file/directory structure
        prefix: String prefix for tree formatting
        is_last: Whether this is the last item at current level
    """
    items = list(data.items())
    for i, (name, value) in enumerate(items):
        is_last_item = i == len(items) - 1
        
        # Print current item
        connector = "└── " if is_last_item else "├── "
        print(f"{prefix}{connector}{name}")
        
        # If it's a dictionary (subdirectory), recurse
        if isinstance(value, dict):
            extension = "    " if is_last_item else "│   "
            print_tree(value, prefix + extension, is_last_item)


def main(directory_path: str) -> Dict[str, Union[str, Dict]]:
    """
    Main function to load a directory and print its structure.
    
    Args:
        directory_path: Path to the directory to load
        
    Returns:
        Dictionary representing the loaded file structure
    """
    print(f"Loading directory: {directory_path}")
    file_dict = load_directory(directory_path)
    
    if not file_dict:
        print("No valid files found or directory doesn't exist.")
        return {}
    
    print("\nDirectory structure:")
    print_tree(file_dict)
    
    return file_dict


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Load and display directory structure")
    parser.add_argument("directory_path", help="Path to the directory to load")
    
    args = parser.parse_args()
    main(args.directory_path)