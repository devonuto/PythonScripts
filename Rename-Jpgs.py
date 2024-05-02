import os
import subprocess
import re
import sys

from logger_config import setup_custom_logger
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

def convert_exif_date(exif_date):
    # Check if the input is empty or None
    if not exif_date:
        return None
    
    try:
        # Split the date and time parts
        date_part, time_part = exif_date.split(' ')
        # Replace the colons in the date part
        date_part = date_part.replace(':', '-')
        # Replace the colon in the time part
        time_part = time_part.replace(':', '.')
        # Combine them back into the final format
        formatted_date = date_part + ' ' + time_part
        return formatted_date
    except ValueError as ve:
        return None
    except Exception as e:
        return None

def delete_empty_folders(directory):
    # Walk through all directories and subdirectories, bottom-up to ensure we remove empty subdirectories first
    for dirpath, dirnames, filenames in os.walk(directory, topdown=False):
        # Check if directory is empty
        if not dirnames and not filenames:
            try:
                os.rmdir(dirpath)
                logger.info(f"Deleted empty folder: {dirpath}")
            except OSError as e:
                # Directory not empty or other issue such as insufficient permissions
                logger.error(f"Failed to delete {dirpath}: {e}")

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
    try:
        # First command to get the primary DateTimeOriginal
        cmd = ['magick', 'identify', '-format', '%[EXIF:DateTimeOriginal]', file_path]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode == 0 and result.stdout.strip():
            output = convert_exif_date(result.stdout.strip())
            if not output:
                return None

            # initialize micro to '000' in case there is no SubSecTimeOriginal
            micro = '000'
            microseconds = None

            # Second command to get the SubSecTimeOriginal
            cmd = ['magick', 'identify', '-format', '%[EXIF:SubSecTimeOriginal]', file_path]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if result.returncode == 0 and result.stdout.strip():
                microseconds = result.stdout.strip()

            # Check and format micro, even if it hasn't changed from '000'
            if microseconds and microseconds.isdigit():
                # Ensure micro has exactly three digits
                micro = (microseconds.ljust(3, '0') if len(microseconds) < 3 else str(round(float('0.' + microseconds), 3))[2:].ljust(3, '0'))
            
            # Build the final datetime string
            datetime_str = output + '.' + micro

            return datetime_str        
    except subprocess.TimeoutExpired:
        logger.error(f"Timeout expired while reading EXIF data for {file_path}")
    except Exception as e:
        logger.error(f"Error reading EXIF data for {file_path}: {str(e)}")
    return None

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

# Function to move and optionally rename file
def move_and_rename_file(original_path, new_full_path, rename, move):
    new_directory, new_name = os.path.split(new_full_path)
    if not os.path.exists(new_directory):
        os.makedirs(new_directory)
    if os.path.exists(new_full_path):
        base_name, extension = os.path.splitext(new_name)
        counter = 1
        while os.path.exists(os.path.join(new_directory, f"{base_name} ({counter}){extension}")):
            counter += 1
        new_full_path = os.path.join(new_directory, f"{base_name} ({counter}){extension}")
    os.rename(original_path, new_full_path)

    if move and rename: 
        logger.info(f"Moved and renamed {original_path} to {new_full_path}")
    elif move:
        logger.info(f"Moved {original_path} to {new_full_path}")
    elif rename:
        logger.info(f"Renamed {original_path} to {new_full_path}")

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
    move_and_rename_file(original_path, new_path, new_filename != filename, current_directory != expected_directory)

# Main function to process all files in a directory
def process_files(directory):
    for root, dirs, files in os.walk(directory):
        # Modify dirs in-place to skip hidden directories starting with '@'
        dirs[:] = [d for d in dirs if not d.startswith('@')]

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
    if len(sys.argv) < 2:
        start_directory = os.path.abspath("D:\\My Photos\\Loui")
        # logger.error("Error: Please provide a directory to process. Usage: python Rename-Jpgs.py <directory>")
    else:
        start_directory = sys.argv[1]
    if not os.path.isdir(start_directory):
        logger.error(f"Error: {start_directory} is not a valid directory.")
        sys.exit(1)        
    process_files(start_directory)
    delete_empty_folders(start_directory)
