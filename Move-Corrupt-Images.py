import os
from PIL import Image
import time
import shutil  
import sys

from logger_config import setup_custom_logger
logger = setup_custom_logger('Move-Corrupt-Images')
start_directory = os.path.abspath("D:\\My Photos\\Loui")  # Default directory
corrupt_directory = None

def is_corrupted(filepath, max_attempts=3):
    attempt = 0
    while attempt < max_attempts:
        try:
            with Image.open(filepath) as img:
                img.verify()  # Verify the integrity
            with Image.open(filepath) as img:
                img.transpose(Image.FLIP_LEFT_RIGHT)  # Simple operation to force image reading
            return False  # If no exception, image is OK
        except Exception as e:
            logger.error(f"Attempt [{attempt+1}]: Error checking \"{filepath}\": {str(e)}")
            attempt += 1
            time.sleep(1)  # Wait a bit before retrying
    return True  # If all attempts fail, image is corrupted

def process_directory(directory):
    # Process images and move corrupted ones
    total_files = 0
    corrupted_files = 0
    corrupt_directory = os.path.join(start_directory, "Corrupted")
    
    if not os.path.exists(corrupt_directory):
        os.makedirs(corrupt_directory)


    for root, dirs, files in os.walk(directory):
        # Modify dirs in-place to skip hidden directories starting with '@'
        dirs[:] = [d for d in dirs if not d.startswith('@')]

        for filename in files:
            if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.tiff', '.bmp', '.gif')):
                total_files += 1
                file_path = os.path.join(root, filename)
                if is_corrupted(file_path):
                    new_full_path = os.path.join(corrupt_directory, filename)
                    os.rename(file_path, new_full_path)
                    logger.warning(f"Moved corrupted file: \"{file_path}\" to \"{new_full_path}\".")
                    corrupted_files += 1
                else:
                    logger.info(f"File checked and OK: \"{file_path}\".")


    # Output the total number of image files and corrupted files
    logger.info(f"Total image files checked: [{total_files}]")
    logger.info(f"Total corrupted files found: [{corrupted_files}]")

    # Throw an error if corrupted files were found
    if corrupted_files > 0:
        logger.error(f"[{corrupted_files}] found within \"{start_directory}\", they have been moved to \"{corrupt_directory}\".")
        sys.exit(1)

# Command line interaction
if __name__ == "__main__":
    if len(sys.argv) > 1:
        start_directory = sys.argv[1]
    if not os.path.isdir(start_directory):
        logger.error(f"Error: \"{start_directory}\" is not a valid directory.")
        sys.exit(1)        
    process_directory(start_directory)
