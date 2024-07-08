import os
import sys
from PIL import Image

from logger_config import setup_custom_logger
from shared_methods import log_error, log_info

logger = setup_custom_logger('Delete-Small-Images')

def delete_small_jpeg_files(directory):
    """
    Recursively deletes JPEG files in the specified directory and its subdirectories that are smaller than 100 KB 
    or have a width or height smaller than 500 pixels. Excludes any directories starting with '@'.

    Args:
        directory (str): The path to the root directory containing JPEG files.
    """
    # Define the size limit below which files will be deleted (in bytes)
    size_limit = 100 * 1024  # 100 KB
    # Define the pixel limit below which files will be deleted
    pixel_limit = 500

    # Walk through the directory tree
    for root, dirs, files in os.walk(directory):
        # Modify dirs in-place to skip any directories starting with '@'
        dirs[:] = [d for d in dirs if not d.startswith('@')]

        # Iterate over all files in the current directory
        for filename in files:
            # Check if the file is a JPEG
            if filename.lower().endswith(('.jpeg', '.jpg')):
                # Construct the full path to the file
                file_path = os.path.join(root, filename)

                try:
                    # Get the size of the file
                    file_size = os.path.getsize(file_path)

                    # Open the image file to check its dimensions
                    with Image.open(file_path) as img:
                        width, height = img.size

                    # If the file size is less than the limit and dimensions are smaller than the pixel limit, delete the file
                    if file_size < size_limit and (width < pixel_limit or height < pixel_limit):
                        # os.remove(file_path)
                        log_info(logger, f"Deleted \"{filename}\" because it was smaller than 100 KB or dimensions were smaller than 500px.")
                    else:
                        log_info(logger, f"\"{filename}\" checked at {file_size}KB, width {width}px, height {height}px.")
                
                except Exception as e:
                    log_error(logger, f"Error processing file \"{filename}\": {e}")

# Command line interaction
if __name__ == '__main__':
    log_info(logger, f"Current working directory: {os.getcwd()}")
    if len(sys.argv) < 2:
        log_error(logger, "No directory path provided.")
        sys.exit(1)
    start_directory = sys.argv[1]
    if not os.path.isdir(start_directory):
        log_error(logger, f"\"{start_directory}\" is not a valid directory.")
        sys.exit(1)        
    delete_small_jpeg_files(start_directory)
