import os
import re
import sys

from tqdm import tqdm
from logger_config import setup_custom_logger
from shared_methods import (add_exif_data, move_or_rename_file, get_exif_datetime, log_error, log_debug, delete_empty_folders, log_info, get_file_count, 
                            is_desired_media_file_format, DATETIME, setup_database, has_been_processed, record_db_update, log_warning,
                            MEDIA_EXTENSIONS, PHOTO_EXTENSIONS, VIDEO_EXTENSIONS)

logger = setup_custom_logger('Sort-N-Rename-Media')
script_directory = os.path.dirname(os.path.abspath(__file__))
DATABASE_NAME = os.path.join(script_directory, 'sort_n_rename_media.db')
DATABASE_TABLE = 'files'
DATABASE_PRIMARY = 'file_name'
DATABASE_COLUMN2 = 'previous_name'
CONN = None

# Regular expression patterns for date matching in filenames
NAMED_DATE_PATTERN = re.compile(r'^(\w{3}_)?(?P<year>\d{4})[\.\-:]?(?P<month>\d{2})[\.\-:]?(?P<day>\d{2})[\s\-_](?P<hour>\d{2})[\.\-:]?(?P<minute>\d{2})[\.\-:]?(?P<second>\d{2})(?:[\.\-:]?(?P<microseconds>\d{0,9}))?(?P<offset>\+\d{2}[\.\-:]\d{2})?',re.IGNORECASE)
DATETIME_ORIGINAL = 'DateTimeOriginal' 
ORIGINAL_SUBSECONDS = 'SubSecTimeOriginal'
CREATED_DATE = 'CreateDate'
FILE_MODIFY_DATE = 'FileModifyDate'
ASF_CREATION_DATE = 'CreationDate'
CREATED_SUBSECONDS = 'SubSecTimeDigitized'

def process_files(start_directory):
    total_files = get_file_count(start_directory, MEDIA_EXTENSIONS, logger)
    progress_bar = tqdm(total=total_files, desc='Processing Files', unit='files')

    for dirpath, dirnames, filenames in os.walk(start_directory):
        dirnames[:] = [d for d in dirnames 
                       if not d.startswith('@') 
                       and not d.startswith('.') 
                       and not d.startswith('$') 
                       and not d.startswith('~')]
        filenames = [f for f in filenames if '.' + f.split('.')[-1].lower() in MEDIA_EXTENSIONS]

        for file in filenames:
            file_path = os.path.join(dirpath, file)
            file_name, extension = os.path.splitext(file)        
            
            if has_been_processed(CONN, DATABASE_TABLE, DATABASE_PRIMARY, os.path.basename(file_path), logger):
                progress_bar.update(1)
                continue

            # Check if the file is a photo or video
            photo = extension.lower() in PHOTO_EXTENSIONS
            video = extension.lower() in VIDEO_EXTENSIONS

            from_fileName = False
            new_file_path = None

            # Attempt to format the new filename based on the existing filename
            if is_desired_media_file_format(file_name):
                year, month, new_filename = format_new_filename(file_name, extension)
                if year and month and new_filename:                     
                    new_file_path = get_new_destination(start_directory, year, month, new_filename)
                    
                    # If the new full path is the same as the current full path, skip the file
                    if (file_path == new_file_path):
                        record_db_update(
                        CONN, 
                        DATABASE_TABLE, 
                        [DATABASE_PRIMARY, DATABASE_COLUMN2], 
                        [os.path.basename(file_path), os.path.basename(file_path)],
                        logger, 
                        [DATABASE_PRIMARY, DATABASE_COLUMN2],
                        progress_bar)
                        continue
                    from_fileName = True
                    
                else:
                    file_path, new_file_path = create_new_filename_from_exif_data(dirpath, file_path, extension, photo, video, progress_bar)                         
            else:
                file_path, new_file_path = create_new_filename_from_exif_data(dirpath, file_path, extension, photo, video, progress_bar)

            # Skip files with invalid dates
            if new_file_path and os.path.basename(new_file_path).startswith("0000-00-00"):                
                continue

            if file_path and new_file_path:
                new_file_path = move_or_rename_file(file_path, new_file_path, logger, progress_bar)
                if new_file_path and not has_been_processed(CONN, DATABASE_TABLE, [DATABASE_PRIMARY, DATABASE_COLUMN2], [os.path.basename(new_file_path), os.path.basename(file_path)], logger):                    
                    record_db_update(
                        CONN, 
                        DATABASE_TABLE, 
                        [DATABASE_PRIMARY, DATABASE_COLUMN2], 
                        [os.path.basename(new_file_path), os.path.basename(file_path)],
                        logger, 
                        [DATABASE_PRIMARY, DATABASE_COLUMN2],
                        progress_bar)

            # Add the name as the Title in the EXIF data for pictures or videos if it was not extracted from the filename
            if new_file_path and file_name and not from_fileName and not DATETIME.search(file_name):
                if add_exif_data(new_file_path, 'Title', file_name, logger):
                    log_info(logger, f"Added \"{file_name}\" to \"Title\" on \"{new_file_path}\".")
    
            progress_bar.refresh()
            progress_bar.update(1)

    progress_bar.close()
    delete_empty_folders(start_directory, logger)

def create_new_filename_from_exif_data(folder, filename, extension, photo, video, progress_bar):
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
        log_debug(logger, "Input parameters are missing.", progress_bar)
        return None, None

    current_full_path = os.path.join(folder, filename)

    exif_datetime = get_exif_datetime(
        current_full_path,
        DATETIME_ORIGINAL if photo else CREATED_DATE,
        ORIGINAL_SUBSECONDS if photo else CREATED_SUBSECONDS,
        logger
    )

    if not exif_datetime:
        log_debug(logger, "Failed to extract initial EXIF datetime, trying alternative tags.", progress_bar)
        exif_datetime = get_exif_datetime(
            current_full_path,
            FILE_MODIFY_DATE if photo else ASF_CREATION_DATE,
            None,
            logger
        )

    if not exif_datetime and video:
        log_debug(logger, "Video file; attempting to extract EXIF using original datetime tag without subseconds.", progress_bar)
        exif_datetime = get_exif_datetime(
            current_full_path,
            DATETIME_ORIGINAL,
            None,
            logger
        )

    if exif_datetime:
        exif_match = NAMED_DATE_PATTERN.match(exif_datetime)
        filename_match = NAMED_DATE_PATTERN.match(filename)

        if exif_match and filename_match and exif_match.group('hour') == '00' and filename_match.group('hour') != '00':
            if exif_match.group('year') == '0000' and filename_match.group('year') != '0000':
                exif_datetime = (filename_match.group('year') +
                                ':' + filename_match.group('month') +
                                ':' + filename_match.group('day') +
                                ' ' + filename_match.group('hour') +
                                ':' + filename_match.group('minute') +
                                ':' + filename_match.group('second'))
            else:
                exif_datetime = (exif_match.group('year') +
                                ':' + exif_match.group('month') +
                                ':' + exif_match.group('day') +
                                ' ' + filename_match.group('hour') +
                                ':' + filename_match.group('minute') +
                                ':' + filename_match.group('second'))

            if add_exif_data(current_full_path, DATETIME_ORIGINAL, exif_datetime, logger):
                log_info(logger, f"Updated \"{DATETIME_ORIGINAL}\" to \"{exif_datetime}\" on \"{filename}\".", progress_bar)

        year, month, new_filename = format_new_filename(exif_datetime, extension)

        if not year or not month or not new_filename:
            log_debug(logger, f"Failed to format new filename based on EXIF datetime: {exif_datetime}", progress_bar)
            return None, None

        new_file_path = get_new_destination(start_directory, year, month, new_filename)
        
        if current_full_path == new_file_path:
            log_debug(logger, "New path is identical to current path.", progress_bar)
            return current_full_path, None

        log_debug(logger, f"File will be moved from \"{current_full_path}\" to \"{new_file_path}\"", progress_bar)
        return current_full_path, new_file_path

    log_warning(logger, f"Failed to extract EXIF datetime from \"{filename}\"", progress_bar)
    return None, None

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
        new_file_path = os.path.join(start_directory, month, new_filename)
    elif base_name == month:
        # This condition seems suspicious because 'month' is unlikely to be the root directory's name alone.
        # Consider revising this based on actual requirements or expected directory structure.
        new_file_path = os.path.join(start_directory, new_filename)
    elif re.match(r'\d{4}', base_name):
        # Assuming the base_name is a year, go up one level and create the expected structure
        parent_dir = os.path.dirname(start_directory)
        new_file_path = os.path.join(parent_dir, year, month, new_filename)
    else:
        # Default case: append year and month to the current start_directory
        new_file_path = os.path.join(start_directory, year, month, new_filename)

    return new_file_path
    
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
    CONN = setup_database(DATABASE_NAME, 
        f'''
            CREATE TABLE IF NOT EXISTS {DATABASE_TABLE} (
                {DATABASE_PRIMARY} TEXT,
                {DATABASE_COLUMN2} TEXT,
                PRIMARY KEY ({DATABASE_PRIMARY}, {DATABASE_COLUMN2})
            )
        ''', logger)
    process_files(start_directory)
