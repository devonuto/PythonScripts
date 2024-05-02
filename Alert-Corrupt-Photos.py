import os
from PIL import Image
import sys
import time  # Import the time module for the sleep function
import shutil # for moving files

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
        # Modify dirs in-place to skip the corrupted directory 
        if corrupted_dir in dirs:
            dirs.remove(corrupted_dir)  # This prevents os.walk from walking into corrupted directory

        for filename in files:
            if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.tiff', '.bmp', '.gif')):
                file_path = os.path.join(root, filename)
                corrupted_file_path = os.path.join(corrupted_dir, filename)
                if is_corrupted(file_path):
                    shutil.move(file_path, corrupted_file_path)  # Move the corrupted file
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
