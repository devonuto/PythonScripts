import os
import re
import sys

from logger_config import setup_custom_logger
from shared_methods import delete_empty_folders, get_exif_data, move_or_rename_file, delete_empty_folders
logger = setup_custom_logger('Rename-Jpgs')

# Regular expression patterns for date matching in filenames
date_pattern = re.compile(r'^(\w{3}_)?(?P<year>\d{4})-?(?P<month>\d{2})-?(?P<day>\d{2})[\s_](?P<hour>\d{2})\.?(?P<minute>\d{2})\.?(?P<second>\d{2})(?:\.?(?P<microseconds>\d{0,3}))?',re.IGNORECASE)
desired_format = re.compile(r'^(\d{4}-\d{2}-\d{2} \d{2}\.\d{2}\.\d{2}\.\d{3})', re.IGNORECASE)
no_time = re.compile(r'00\.00\.00(\.000)?$')

def adjust_datetime_string(datetime_str):
    # Check if the datetime string ends with a dot followed by three digits
    if not re.search(r'\.\d{3}$', datetime_str):
        # If not, append '.000'
        datetime_str += '.000'
    return datetime_str

def find_base_directory(current_directory):
    # This function walks up the directory tree to find the base directory just above the year folder
    parts = current_directory.split(os.sep)
    for i in range(len(parts) - 1, 0, -1):
        if parts[i].isdigit() and len(parts[i]) == 4:  # Looks for a directory that is numeric and 4 digits (likely a year)
            # Return the directory one level up from the year directory
            return os.sep.join(parts[:i])
    return current_directory  # Fallback to

# Function to extract datetime from filename
def get_datetime_from_filename(full_path):
    filename = os.path.basename(full_path)
    match = date_pattern.search(filename)
    if match:
        # Accessing the named groups using the group() method
        year = match.group('year')
        month = match.group('month')
        day = match.group('day')
        hour = match.group('hour')
        minute = match.group('minute')
        second = match.group('second')
        microseconds = match.group('microseconds')
        
        # Construct the datetime string
        datetime_string = '-'.join([year, month, day]) + ' ' + '.'.join([hour, minute, second])
        if microseconds:  # Add microseconds only if they are present
            datetime_string += '.' + microseconds
            
        return datetime_string
    else:
        return None
    

# Function to get the datetime from EXIF data using exiftool
def get_exif_datetime(file_path):
    micro = '000'    
    datetime_str = get_exif_data(file_path, 'DateTimeOriginal', logger)
    if not datetime_str:
        return None

    microseconds = get_exif_data(file_path, 'SubSecTimeOriginal', logger)
    # Check and format micro, even if it hasn't changed from '000'
    if microseconds and microseconds.isdigit():
        # Ensure micro has exactly three digits
        micro = (microseconds.ljust(3, '0') if len(microseconds) < 3 else str(round(float('0.' + microseconds), 3))[2:].ljust(3, '0'))
    
        # Build the final datetime string
    datetime_str += '.' + micro
    return datetime_str        

# Utility functions for checking file types and formats
def is_jpeg_extension(file_name):
    return file_name.lower().endswith(('.jpg', '.jpeg'))

def is_correct_format(filename):
    return bool(date_pattern.match(filename))

def is_correct_index(new_path):
    directory, filename = os.path.split(new_path)
    basename, extension = os.path.splitext(filename)

    # Check if the filename has an index
    match = re.search(r' \((\d+)\)$', basename)
    if match:
        index = int(match.group(1))
        base_without_index = re.sub(r' \(\d+\)$', '', basename)

        # Gather all files that start with the same base name (excluding the extension)
        matching_files = [f for f in os.listdir(directory) if f != filename and os.path.splitext(f)[0].startswith(base_without_index)]

        # Count the files that strictly match the base name without index and same extension
        exact_matches = sum(1 for f in matching_files if os.path.splitext(f)[0] == base_without_index and os.path.splitext(f)[1] == extension)

        # If the index is 1 and there are no exact matches, it's incorrect to have an index
        if index == 1 and exact_matches == 0:
            return False

        # If the index is greater than 1, there should be exactly 'index - 1' other files
        if index > 1 and exact_matches != index - 1:
            return False

        return True
    else:
        return True

def is_desired_format(filename):
    return bool(desired_format.match(filename))

def is_missing_time(filename):
    return bool(no_time.search(filename))

# Function to ensure files are in correct date folder structure
def move_file_to_date_folder(original_path, datetime_str):
    datetime_str = adjust_datetime_string(datetime_str)
    year, month = datetime_str[:4], datetime_str[5:7]
    current_directory = os.path.dirname(original_path)

    # Find the base directory that is above the 'year' directory
    base_directory = find_base_directory(current_directory)

    # Build the expected directory using the base directory found
    expected_directory = os.path.join(base_directory, year, month)

    filename = os.path.basename(original_path)
    new_path = os.path.join(expected_directory, filename)

    if os.path.abspath(original_path) == os.path.abspath(new_path) and is_desired_format(filename) and is_correct_index(new_path):
        logger.info(f"{original_path} is already in the correct format and directory.")
        return

    if not os.path.exists(expected_directory):
        os.makedirs(expected_directory)
    
    # Define new filename or use existing logic to ensure it matches the desired format
    new_filename = f"{datetime_str}.jpg" 
    new_path = os.path.join(expected_directory, new_filename)
    move_or_rename_file(original_path, new_path, logger)

# Main function to process all files in a directory
def process_files(directory):
    for root, dirs, files in os.walk(directory):
        # Modify dirs in-place to skip non-standard directories
        dirs[:] = [d for d in dirs if re.match(r'^[a-zA-Z0-9]', d)]

        for file in files:
            if is_jpeg_extension(file):
                full_path = os.path.join(root, file)
                datetime_str = get_datetime_from_filename(full_path)  # Get datetime from filename 
                if not datetime_str or not is_desired_format(datetime_str):
                    exif_datetime = get_exif_datetime(full_path)  # Get datetime from EXIF data
                    if (exif_datetime and not is_missing_time(exif_datetime)) or (exif_datetime and not datetime_str):
                        datetime_str = exif_datetime

                if datetime_str:
                    move_file_to_date_folder(full_path, datetime_str)
                else:
                    logger.info(f"Skipping {full_path} due to missing or invalid datetime information.")

# Command line interaction
if __name__ == "__main__":
    logger.info(f"Current working directory: {os.getcwd()}")
    if len(sys.argv) < 2:
        start_directory = os.path.abspath("D:\\My Photos\\Loui")
        # logger.error("Error: Please provide a directory to process. Usage: python Rename-Jpgs.py <directory>")
    else:
        start_directory = sys.argv[1]
    if not os.path.isdir(start_directory):
        logger.error(f"Error: {start_directory} is not a valid directory.")
        sys.exit(1)        
    process_files(start_directory)
    delete_empty_folders(start_directory, logger)
