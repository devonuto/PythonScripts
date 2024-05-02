import os
import subprocess
import re
import sys
from datetime import datetime

from logger_config import setup_custom_logger
logger = setup_custom_logger('Add-Missing-EXIF')

DATETIME = re.compile(r'^(\d{4}-\d{2}-\d{2} \d{2}\.\d{2}\.\d{2}(\.\d{3})?)', re.IGNORECASE)
PHOTO_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.tiff', '.bmp', '.gif'}
VIDEO_EXTENSIONS = {'.m4v', '.mov', '.mp4', '.avi', '.mkv', '.wmv', '.flv', '.webm'}

start_directory = "D:\\My Photos" # Default start directory

def add_exif_data(file_path, exif_tag, exif_data):
    # Define the command to run exiftool and parse with awk
    cmd = f'exiftool -overwrite_original -{exif_tag}="{exif_data}" "{file_path}"'
    # Execute the command
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, text=True)
    # Check if the command was successful
    if result.returncode == 0:
        logger.info(f"Added \"{exif_data}\" to \"{exif_tag}\" on \"{file_path}\".")
        return True
    else:
        # Handle errors (e.g., file not found, exiftool error)
        logger.error(result.stderr.strip())
        return False

def get_exif_data(file_path, exif_tag):
    logger.info(f"Checking \"{exif_tag}\" on \"{file_path}\".")
    # Define the command to run exiftool and parse with awk
    cmd = f'exiftool -{exif_tag} "{file_path}" | awk -F: "' + '{for (i=2; i<=NF; i++) printf $i (i==NF ? \\"\\\\n\\" : \\":\\") }"'
    # Execute the command
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, text=True)
    # Check if the command was successful
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip()
    elif result.returncode == 1 or result.stderr.strip():
        logger.error(result.stderr.strip())
    else:
        return None

# Determine if the first date is more recent than the second date
def is_first_date_more_recent(date_str1, date_str2):
    # Define the datetime formats
    base_date_format = '%Y.%m.%d %H.%M.%S'
    micro_date_format = '%Y.%m.%d %H.%M.%S.%f'

    # Helper function to sanitize and parse the date string
    def get_date_object(date_str):
        # Sanitize the date string to ensure it uses '.' as the separator for the date
        sanitized_date_str = date_str.replace(':', '.').replace('-', '.')
        try:
            # Try parsing without microseconds
            return datetime.strptime(sanitized_date_str, base_date_format)            
        except ValueError:
            # Fall back to parsing with microseconds
            return datetime.strptime(sanitized_date_str, micro_date_format)

    # Convert strings to datetime objects using the determined format
    date1 = get_date_object(date_str1)
    date2 = get_date_object(date_str2)

    # Compare the dates and return True if date1 is more recent, False otherwise
    return date1 > date2

# Process images in the start_directory    
def process_images(start_directory):
    # Find image files anywhere within the start_directory that match DATETIME format
    for root, dirs, files in os.walk(start_directory):
        for file in files:
            file_path = os.path.join(root, file)
            file_name, file_extension = os.path.splitext(file)
            if file_extension.lower() in PHOTO_EXTENSIONS:
                # Check if the file has a DATETIME in the filename
                match = DATETIME.search(file)
                if match:
                    # Get the date and time from the file's EXIF data
                    exif_date = get_exif_data(file_path, 'DateTimeOriginal')

                    # if not exif_date or exif_date is more recent than date_time in filename, update exif data with date_time
                    if not exif_date or is_first_date_more_recent(exif_date, file_name):
                        # Add the date and time to the file's EXIF data from filename
                        add_exif_data(file_path, 'DateTimeOriginal', file_name)                            

# Command line interaction
if len(sys.argv) > 1:
    start_directory = sys.argv[1]
if not os.path.isdir(start_directory):
    logger.error(f"\"{start_directory}\" is not a valid directory.")
    sys.exit(1)        
process_images(start_directory)
