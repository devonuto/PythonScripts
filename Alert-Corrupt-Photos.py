import os
import re
import sys
import time  # Import the time module for the sleep function
from logger_config import setup_custom_logger
from PIL import Image
from shared_methods import move_or_rename_file, PHOTO_EXTENSIONS

logger = setup_custom_logger('Alert-Custom-Images')

def is_corrupted(filepath, max_attempts=3):
    attempt = 0
    while attempt < max_attempts:
        try:
            # Verify the image
            with Image.open(filepath) as img:
                img.verify()  # Verify the integrity
            # Reopen the image for further operations
            with Image.open(filepath) as img:
                img.transpose(Image.FLIP_LEFT_RIGHT)  # Simple operation to force image reading
            return False  # If no exception, image is OK
        except Exception as e:
            print(f"Attempt {attempt+1}: Error checking {filepath}: {str(e)}")
            attempt += 1
            time.sleep(1)  # Wait a bit before retrying
    return True  # If all attempts fail, image is corrupted

def find_corrupted_images(directory):
    corrupted_files = []
    for root, dirs, files in os.walk(directory):
        dirs[:] = [d for d in dirs if re.match(r'^[a-zA-Z0-9]' and not d == corrupted_dir, d)]
        files = [f for f in files if '.' + f.split('.')[-1].lower() in PHOTO_EXTENSIONS]
        for filename in files:
            _, extension = os.path.splitext(filename)
            if extension.lower() in PHOTO_EXTENSIONS:
                file_path = os.path.join(root, filename)
                corrupted_file_path = os.path.join(corrupted_dir, filename)
                if is_corrupted(file_path):
                    move_or_rename_file(file_path, corrupted_file_path, logger, None)
                    corrupted_files.append(corrupted_file_path)
    return corrupted_files

if __name__ == "__main__":
    search_directory = os.path.abspath("./")
    corrupted_dir = os.path.join(search_directory, "corrupted")
    corrupted = find_corrupted_images(search_directory)
    if corrupted:
        print("Corrupted files found:")
        for file in corrupted:
            print(file)
        sys.exit("Error: Corrupted files detected.")  # Trigger an error for Task Scheduler
    else:
        print("No corrupted files found.")
