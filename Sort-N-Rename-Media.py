import os
import subprocess
import re
import sys

from logger_config import setup_custom_logger
from shared_methods import get_exif_data, add_exif_data, move_or_rename_file
logger = setup_custom_logger('Sort-N-Rename-Media')

start_directory = os.path.abspath("D:\\My Photos\\Steve")  # Default directory

# Regular expression patterns for date matching in filenames
DATE_PATTERN = re.compile(r'^(\w{3}_)?(?P<year>\d{4})[\.\-:]?(?P<month>\d{2})[\.\-:]?(?P<day>\d{2})[\s\-_](?P<hour>\d{2})[\.\-:]?(?P<minute>\d{2})[\.\-:]?(?P<second>\d{2})(?:[\.\-:]?(?P<microseconds>\d{0,9}))?(?P<offset>\+\d{2}[\.\-:]\d{2})?',re.IGNORECASE)
DESIRED_PATTERN = re.compile(r'^(\d{4}-\d{2}-\d{2} \d{2}\.\d{2}\.\d{2}\.\d{3})', re.IGNORECASE)
DATETIME_ORIGINAL = 'DateTimeOriginal'
ORIGINAL_SUBSECONDS = 'SubSecTimeOriginal'
CREATED_DATE = 'CreateDate'
FILE_MODIFY_DATE = 'FileModifyDate'
ASF_CREATION_DATE = 'CreationDate'
CREATED_SUBSECONDS = 'SubSecTimeDigitized'
PHOTO_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.tiff', '.bmp', '.gif'}
VIDEO_EXTENSIONS = {'.m4v', '.mov', '.mp4', '.avi', '.mkv', '.wmv', '.flv', '.webm'}

def process_files(start_directory):

    # Find folders which are not named with a YEAR pattern (yyyy), or Month Pattern (MM) and not hidden folders
    folders = [f for f in os.listdir(start_directory) if os.path.isdir(os.path.join(start_directory, f))]
    folders = [f for f in folders if not re.match(r'\d{4}', f)]
    folders = [f for f in folders if not re.match(r'\d{2}', f)]
    folders = [f for f in folders if not f.startswith('.') and not f.startswith('$') and not f.startswith('~') and not f.startswith('@')]

    folders.sort()
    
    # if folders exist, process them
    if len(folders) > 0:
        for folder in folders:
            # Find any year folders inside this folder, at any level.
            year_folders = []
            for root, dirs, files in os.walk(os.path.join(start_directory, folder)):
                year_folders.extend([d for d in dirs if re.match(r'\d{4}', d)])
                if (len(year_folders) > 0):
                    year_folders.sort()
                    for year_folder in year_folders:
                        
                        # Check if year folder exists in start_directory
                        if not os.path.exists(os.path.join(start_directory, year_folder)):
                            os.makedirs(os.path.join(start_directory, year_folder))

                        # Get Full Path of year_folder
                        if (os.path.basename(root) == year_folder):
                            source = root
                        else: 
                            source = os.path.join(root, year_folder)
                        destination = os.path.join(start_directory, year_folder)
                        
                        # Sync files from source to destination
                        sync_folders(source, destination)
                else:            
                    # If directory doesn't have a year folder in it, move and rename files in this folder.
                    rename_files_in_destination(os.path.join(start_directory, folder))
            
            if (len(os.listdir) == 0):
                logger.info(f"Deleting empty folder: {folder}")
                os.rmdir(folder)
    else:
        # If there are no folders in start_directory, process files in start_directory
        rename_files_in_destination(start_directory)

# Get new destination path based on year and month
def get_new_destination(year, month, new_filename):
    if os.path.basename(start_directory) == year:
        new_full_path = os.path.join(start_directory, month, new_filename)
    # else if basename of start_directory matches year, then create a new directory with month
    elif os.path.basename(start_directory) == month:
        new_full_path = os.path.join(start_directory, new_filename)    
    elif re.match(r'\d{4}', os.path.basename(start_directory)):
        parent_dir = os.path.dirname(start_directory)
        new_full_path = os.path.join(parent_dir, year, month, new_filename)
    else:
        new_full_path = os.path.join(start_directory, year, month, new_filename)

    return new_full_path
    
def format_new_filename(filename, extension):
    match = DATE_PATTERN.match(filename)
    if match:
        # Get the date and time components from the filename
        year = match.group('year')
        month = match.group('month')
        day = match.group('day')
        hour = match.group('hour')
        minute = match.group('minute')
        second = match.group('second')
        microseconds = match.group('microseconds') or '000'

        # Construct the new filename based on extracted components
        new_filename = f"{year}-{month}-{day} {hour}.{minute}.{second}.{microseconds}{extension}"
        return year, month, new_filename
    
    return None, None, None  # No match found
                
def rename_files_in_destination(folder):
    # Get all entries in the directory
    entries = os.listdir(folder)

    # Filter entries to get only files
    files = [f for f in entries if os.path.isfile(os.path.join(folder, f))]

    # If there are no files in the directory, check the first subdirectory
    if len(entries) == 1 and len(files) == 0:
        rename_files_in_destination(os.path.join(folder, entries[0]))

    if len(entries) == 0 and len(files) == 0:
        logger.info(f"Deleting empty folder: {folder}")
        os.rmdir(folder)

    for filename in files:                
        # extract extension and name from filename
        name, extension = os.path.splitext(filename)                

        # Skip if the file has no extension
        if not extension:
            continue

        # Check if the file is a photo or video
        photo = extension.lower() in PHOTO_EXTENSIONS
        video = extension.lower() in VIDEO_EXTENSIONS

        # If the file is neither a photo nor a video, skip it
        if not photo and not video:
            continue

        new_full_path = None
        from_fileName = False

        # Attempt to format the new filename based on the existing filename
        year, month, new_filename = format_new_filename(name, extension)
        if year and month and new_filename:                     
            new_full_path = get_new_destination(year, month, new_filename)
            
            # If the new full path is the same as the current full path, skip the file
            current_full_path = os.path.join(folder, filename)
            if (current_full_path == new_full_path):
                continue

            result, msg = move_or_rename_file(current_full_path, new_full_path)
            if result == 'INFO':
                logger.info(msg)
                from_fileName = True
            else:
                logger.error(msg)
        else:
            # Check for Date Taken in EXIF data using Magick
            exif_datetime = None
            exif_datetime = get_exif_data(os.path.join(folder, filename), DATETIME_ORIGINAL if photo else CREATED_DATE, logger)
            if not exif_datetime:
                # Check for Date Taken in EXIF data using exiftool
                exif_datetime = get_exif_data(os.path.join(folder, filename), FILE_MODIFY_DATE if photo else ASF_CREATION_DATE, logger)
                if not exif_datetime and video:
                    # Check for Date Taken in EXIF data using exiftool
                    exif_datetime = get_exif_data(os.path.join(folder, filename), DATETIME_ORIGINAL, logger)
            

            if exif_datetime:                   
                micro = '000'

                # Check for Subseconds in EXIF data using exiftool
                microseconds = None
                try:
                    microseconds = get_exif_data(os.path.join(folder, filename), ORIGINAL_SUBSECONDS if photo else CREATED_SUBSECONDS)
                except Exception as e:
                    logger.error(f"Error getting {ORIGINAL_SUBSECONDS if photo else CREATED_SUBSECONDS} EXIF tag from \"{filename}\": {e}")

                if microseconds:                                        
                    # If the microseconds are less than 3 digits, pad with zeros, or more than 3 digits, round to 3 digits
                    micro = (microseconds.ljust(3, '0') if len(microseconds) < 3 else str(round(float('0.' + microseconds), 3))[2:].ljust(3, '0'))

                # Append the microseconds to the datetime string
                year, month, new_filename = format_new_filename(exif_datetime + '.' + micro, extension)

                if not year or not month or not new_filename:
                    continue

                # Construct the new full path based on the extracted components
                new_full_path = get_new_destination(year, month, new_filename)

                # If the new full path is the same as the current full path, skip the file
                current_full_path = os.path.join(folder, filename)
                if (current_full_path == new_full_path):
                    continue

                result, msg = move_or_rename_file(current_full_path, new_full_path)
                if result == 'INFO':
                    logger.info(msg)
                    from_fileName = True
                else:
                    logger.error(msg)

        # Add the name as the Title in the EXIF data for pictures or videos if it was not extracted from the filename
        if new_full_path and name and not from_fileName:
            if add_exif_data(new_full_path, 'Title', name):
                logger.info(f"Added \"{name}\" to \"Title\" on \"{new_full_path}\".")

# Rsync and remove source files
def sync_folders(source_dir, destination_dir):
    if source_dir == destination_dir:
        logger.warning("Source and destination directories are the same.")
        return

    # Ensure the destination directory exists
    os.makedirs(destination_dir, exist_ok=True)

    # Iterate through the source directory
    for item in os.listdir(source_dir):
        source_item = os.path.join(source_dir, item)
        destination_item = os.path.join(destination_dir, item)

        # Check if the item is a file or directory
        if os.path.isfile(source_item):
            # Move the file
            result, msg = move_or_rename_file(source_item, destination_item)
            logger.info(msg) if result == 'INFO' else logger.error(msg)
        elif os.path.isdir(source_item):
            # Recursively call this function for subdirectories
            sync_folders(source_item, destination_item)
            # Optionally remove the source directory if it's empty
            if not os.listdir(source_item):
                logger.info(f"Deleting empty folder: {source_item}")
                os.rmdir(source_item)

    if not os.listdir(source_dir):
        logger.info(f"Deleting empty folder: {source_dir}")
        os.rmdir(source_dir)

    # Rename files in destination directory
    rename_files_in_destination(destination_dir)
    logger.info(f"Synchronization from \"{source_dir}\" to \"{destination_dir}\" complete.")

# Command line interaction
if len(sys.argv) > 1:
    start_directory = sys.argv[1]
if not os.path.isdir(start_directory):
    logger.error(f"\"{start_directory}\" is not a valid directory.")
    sys.exit(1)        
process_files(start_directory)
