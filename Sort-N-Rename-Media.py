import os
import re
import sys

from logger_config import setup_custom_logger
from shared_methods import (add_exif_data, move_or_rename_file, get_exif_datetime, log_error, 
                            log_info, log_warning, is_desired_media_file_format, DATETIME)
logger = setup_custom_logger('Sort-N-Rename-Media')

# Regular expression patterns for date matching in filenames
NAMED_DATE_PATTERN = re.compile(r'^(\w{3}_)?(?P<year>\d{4})[\.\-:]?(?P<month>\d{2})[\.\-:]?(?P<day>\d{2})[\s\-_](?P<hour>\d{2})[\.\-:]?(?P<minute>\d{2})[\.\-:]?(?P<second>\d{2})(?:[\.\-:]?(?P<microseconds>\d{0,9}))?(?P<offset>\+\d{2}[\.\-:]\d{2})?',re.IGNORECASE)
DATETIME_ORIGINAL = 'DateTimeOriginal' 
ORIGINAL_SUBSECONDS = 'SubSecTimeOriginal'
CREATED_DATE = 'CreateDate'
FILE_MODIFY_DATE = 'FileModifyDate'
ASF_CREATION_DATE = 'CreationDate'
CREATED_SUBSECONDS = 'SubSecTimeDigitized'
PHOTO_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.tiff', '.bmp', '.gif'}
VIDEO_EXTENSIONS = {'.m4v', '.mov', '.mp4', '.avi', '.mkv', '.wmv', '.flv', '.webm'}

def process_files(start_directory):
    """
    Processes directories and files in a given directory, focusing on folder syncing and file renaming based
    on specific conditions related to folder names and their contents.

    This function looks for directories that do not match typical year (YYYY) or month (MM) patterns,
    and are not hidden. It will either sync files from folders named with year patterns to a similar
    directory structure in the start_directory or rename files in directories that do not contain
    year-labeled subdirectories.

    Parameters:
    - start_directory (str): The path of the directory from which to start processing.

    Notes:
    - This function assumes the presence of additional functions `sync_folders(source, destination)`
      and `rename_files_in_destination(directory)` which handle the synchronization of folders and
      the renaming of files respectively.
    - It also assumes the presence of a logging function `log_info(logger, message)` for logging messages.
    """

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
            for root, dirs, _ in os.walk(os.path.join(start_directory, folder)):
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
            
            if (os.path.exists(folder) and len(os.listdir(folder)) == 0):
                log_info(logger, f"Deleting empty folder: {folder}")
                os.rmdir(folder)
       
    # If there are no folders in start_directory, process files in start_directory
    rename_files_in_destination(start_directory)

def create_new_filename_from_exif_data(folder, filename, extension, photo, video):
    """
    Generates a new filename based on EXIF metadata for given media file and determines its new destination path.
    
    The function uses EXIF data to determine the creation date and time of a media file (photo or video) and formats
    a new filename based on this data. It ensures the new filename is placed in the correct year and month directory
    within the specified start directory.

    Args:
        folder (str): The directory where the media file is located.
        filename (str): The name of the file, including its extension.
        extension (str): The file extension (e.g., '.jpg', '.mp4').
        photo (bool): True if the file is a photo, False otherwise.
        video (bool): True if the file is a video, False otherwise.

    Returns:
        tuple: A tuple containing:
               - The current full path to the file.
               - The new full path to the file if a new filename was successfully generated and differs from the original; None otherwise.
    """

    # Validate input parameters
    if not folder or not filename or not extension:
        return None, None

    # Determine appropriate tags for EXIF data extraction based on media type
    exif_datetime = get_exif_datetime(
        os.path.join(folder, filename),
        DATETIME_ORIGINAL if photo else CREATED_DATE,
        ORIGINAL_SUBSECONDS if photo else CREATED_SUBSECONDS,
        logger
    )
    
    # If initial EXIF data extraction fails, try alternative tags
    if not exif_datetime:
        exif_datetime = get_exif_datetime(
            os.path.join(folder, filename),
            FILE_MODIFY_DATE if photo else ASF_CREATION_DATE,
            None,
            logger
        )
        # Additional attempt for videos if previous steps fail
        if not exif_datetime and video:
            exif_datetime = get_exif_datetime(
                os.path.join(folder, filename),
                DATETIME_ORIGINAL,
                None,
                logger
            )
    
    # If EXIF datetime is successfully extracted, proceed to format new filename
    if exif_datetime:
        # If the named date pattern matches the filename and the extracted EXIF datetime, proceed with formatting
        exif_match = NAMED_DATE_PATTERN.match(exif_datetime)
        filename_match = NAMED_DATE_PATTERN.match(filename)
        
        # Check if the filename and EXIF datetime match the expected pattern
        if exif_match and filename_match and exif_match.group('hour') == '00' and filename_match.group('hour') != '00':
            # If the EXIF data does not hav a year and the filename does, use the filename datetime
            if exif_match.group('year') == '0000' and filename_match.group('year') != '0000':
                exif_datetime = (filename_match.group('year') +
                                ':' + filename_match.group('month') +
                                ':' + filename_match.group('day') +
                                ' ' + filename_match.group('hour') +
                                ':' + filename_match.group('minute') +
                                ':' + filename_match.group('second'))
            # If the filename has a time and the EXIF data does not, use the filename time
            else:
                exif_datetime = (exif_match.group('year') +
                                ':' + exif_match.group('month') +
                                ':' + exif_match.group('day') +
                                ' ' + filename_match.group('hour') +
                                ':' + filename_match.group('minute') +
                                ':' + filename_match.group('second'))

            # Update the EXIF data with the new datetime
            if add_exif_data(os.path.join(folder, filename), DATETIME_ORIGINAL, exif_datetime, logger):
                log_info(logger, f"Updated \"{DATETIME_ORIGINAL}\" to \"{exif_datetime}\" on \"{filename}\".")

        year, month, new_filename = format_new_filename(exif_datetime, extension)

        # Validate new filename components
        if not year or not month or not new_filename:
            return None, None

        # Generate new full path for the file
        new_full_path = get_new_destination(start_directory, year, month, new_filename)

        # Compare new full path with current path to avoid unnecessary changes
        current_full_path = os.path.join(folder, filename)
        if current_full_path == new_full_path:
            return current_full_path, None
        
        return current_full_path, new_full_path

# Get new destination path based on year and month
def get_new_destination(start_directory, year, month, new_filename):
    """
    Construct a new file path based on year and month criteria relative to the start_directory.

    Args:
    - start_directory (str): The base directory from which to calculate the new path.
    - year (str): The year component for the new path.
    - month (str): The month component for the new path.
    - new_filename (str): The filename to append to the constructed path.

    Returns:
    - str: The constructed full path to the new file.
    """

    # Validate input parameters
    if not all([year.isdigit() and len(year) == 4, month.isdigit() and len(month) in (1, 2), new_filename]):
        raise ValueError("Invalid year, month, or filename provided.")

    base_name = os.path.basename(start_directory)
    
    if base_name == year:
        new_full_path = os.path.join(start_directory, month, new_filename)
    elif base_name == month:
        # This condition seems suspicious because 'month' is unlikely to be the root directory's name alone.
        # Consider revising this based on actual requirements or expected directory structure.
        new_full_path = os.path.join(start_directory, new_filename)
    elif re.match(r'\d{4}', base_name):
        # Assuming the base_name is a year, go up one level and create the expected structure
        parent_dir = os.path.dirname(start_directory)
        new_full_path = os.path.join(parent_dir, year, month, new_filename)
    else:
        # Default case: append year and month to the current start_directory
        new_full_path = os.path.join(start_directory, year, month, new_filename)

    return new_full_path
    
def format_new_filename(filename, extension):
    """
    Formats a new filename using date and time components extracted from the original filename and appends a specified extension.

    Args:
        filename (str): The original filename expected to contain date and time information.
        extension (str): The extension to be appended to the new filename.

    Returns:
        tuple: A tuple containing the year, month, and new formatted filename.
               Returns (None, None, None) if the filename does not match the expected format.
    """

    match = NAMED_DATE_PATTERN.match(filename)
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
    """
    Renames files in a given directory based on their type (photo or video) and metadata.
    It handles the directory recursively, and removes empty directories.

    Args:
    - folder (str): The path to the directory containing files to be renamed.

    This function performs several key operations:
    - Lists all files in the specified directory.
    - Checks for empty directories and removes them if found.
    - Identifies files based on their extensions and determines if they are photos or videos.
    - Attempts to rename files based on existing filename patterns or metadata (EXIF data).
    - Moves or renames files to new directories structured by year and month.
    - Adds or updates EXIF data where necessary.

    No return value. Log messages are generated for significant actions.
    """
    if not folder or not os.path.isdir(folder):
        return

    entries = os.listdir(folder)

    # Filter entries to get only files
    files = [f for f in entries if os.path.isfile(os.path.join(folder, f))]

    # If there are no files in the directory, check the first subdirectory
    if len(entries) == 1 and len(files) == 0:
        rename_files_in_destination(os.path.join(folder, entries[0]))

    if len(entries) == 0 and len(files) == 0:
        log_info(logger, f"Deleting empty folder: {folder}", )
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

        from_fileName = False
        new_full_path = None
        current_full_path = os.path.join(folder, filename)

        # Attempt to format the new filename based on the existing filename
        if is_desired_media_file_format(name):
            year, month, new_filename = format_new_filename(name, extension)
            if year and month and new_filename:                     
                new_full_path = get_new_destination(start_directory, year, month, new_filename)
                
                # If the new full path is the same as the current full path, skip the file
                if (current_full_path == new_full_path):
                    continue

                from_fileName = True
            else:
                current_full_path, new_full_path = create_new_filename_from_exif_data(folder, filename, extension, photo, video)                         
        else:
            current_full_path, new_full_path = create_new_filename_from_exif_data(folder, filename, extension, photo, video)

        if current_full_path and new_full_path:
            move_or_rename_file(current_full_path, new_full_path, logger)

        # Add the name as the Title in the EXIF data for pictures or videos if it was not extracted from the filename
        if new_full_path and name and not from_fileName and not DATETIME.search(name):
            if add_exif_data(new_full_path, 'Title', name, logger):
                log_info(logger, f"Added \"{name}\" to \"Title\" on \"{new_full_path}\".")

# Sync and remove source files
def sync_folders(source_dir, destination_dir):
    """
    Synchronizes content from a source directory to a destination directory. This includes copying files and
    recursively copying subdirectories. After synchronization, files in the destination directory are renamed
    according to specific criteria defined in `rename_files_in_destination`.

    Parameters:
    - source_dir (str): The path of the source directory.
    - destination_dir (str): The path of the destination directory.

    Notes:
    - Assumes the existence of `move_or_rename_file(source_item, destination_item, logger)` to handle
      the moving and renaming of files.
    - Assumes the existence of `rename_files_in_destination(directory)` to rename files based on certain criteria.
    - Uses `log_warning(logger, message)` and `log_info(logger, message)` for logging purposes.
    """

    # Prevent synchronization to the same directory
    if source_dir == destination_dir:
        log_warning(logger, "Source and destination directories are the same.")
        return

    # Ensure the destination directory exists
    os.makedirs(destination_dir, exist_ok=True)

    # Iterate through each item in the source directory
    for item in os.listdir(source_dir):
        source_item = os.path.join(source_dir, item)
        destination_item = os.path.join(destination_dir, item)

        # Copy files and recursively copy directories
        if os.path.isfile(source_item):
            move_or_rename_file(source_item, destination_item, logger)
        elif os.path.isdir(source_item):
            sync_folders(source_item, destination_item)

            # Remove the source subdirectory if it is empty after synchronization
            if os.path.exists(source_item) and not os.listdir(source_item):
                log_info(logger, f"Deleting empty folder: {source_item}")
                os.rmdir(source_item)

    # Remove the source directory if it is empty after synchronization
    if os.path.exists(source_dir) and not os.listdir(source_dir):
        log_info(logger, f"Deleting empty folder: {source_dir}")
        os.rmdir(source_dir)

    # Rename files in the destination directory and log completion
    rename_files_in_destination(destination_dir)
    log_info(logger, f"Synchronization from \"{source_dir}\" to \"{destination_dir}\" complete.")

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
    process_files(start_directory)
