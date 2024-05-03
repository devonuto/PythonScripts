import os
import re
import sys

from datetime import datetime
from logger_config import setup_custom_logger
from shared_methods import get_exif_data, add_exif_data, setup_database, has_been_processed, record_db_update

logger = setup_custom_logger('Add-Missing-EXIF')

DATETIME = re.compile(r'^\d{4}[\-\:\.]\d{2}[\-\:\.]\d{2}\s\d{2}[\-\:\.]\d{2}[\-\:\.]\d{2}([\-\:\.]\d{3})?', re.IGNORECASE)
PHOTO_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.tiff', '.bmp', '.gif'}
VIDEO_EXTENSIONS = {'.m4v', '.mov', '.mp4', '.avi', '.mkv', '.wmv', '.flv', '.webm'}
DATABASE_NAME = 'exif_updates.db'
DATABASE_TABLE = 'file_updates'
DATABASE_PRIMARY = 'file_path'
DATABASE_COLUMN2 = 'exif_tag'
DATABASE_COLUMN3 = 'exif_data'

# Helper function to sanitize and extract the date part only
def get_date_object(date_str):
    # Define the date-only format
    date_format = '%Y-%m-%d'
    # Split the string to extract the date part only
    date_part = date_str.split(' ')[0]
    # Sanitize the date part to ensure it uses '-' as the separator
    sanitized_date_part = date_part.replace(':', '-').replace('.', '-')
    logger.debug(f"Date string: {date_str} Date part: {date_part}, Sanitized Date part: {sanitized_date_part}")
    # Parse the date part
    return datetime.strptime(sanitized_date_part, date_format)

# Compare two date strings and return True if the first date is more recent than the second date
def is_first_date_more_recent(date_str1, date_str2):
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
                if has_been_processed(DATABASE_NAME, DATABASE_TABLE, DATABASE_PRIMARY, file_path, logger):
                    logger.info(f"\"{file_path}\" has already been processed.")
                    continue

                # Check if the file has a DATETIME in the filename
                match = DATETIME.match(file)
                if match:
                    # Get the date and time from the file's EXIF data
                    exif_date = get_exif_data(file_path, 'DateTimeOriginal', logger)
                    # if not exif_date or exif_date is more recent than date_time in filename, update exif data with date_time
                    if not exif_date or is_first_date_more_recent(exif_date, file_name):
                        # Add the date and time to the file's EXIF data from filename
                        try:
                            if add_exif_data(file_path, 'DateTimeOriginal', file_name):
                                logger.info(f"Updated DateTimeOriginal from \"{exif_date}\" to \"{file_name}\" on \"{file_path}\".")
                                record_db_update(DATABASE_NAME, DATABASE_TABLE, [DATABASE_PRIMARY, DATABASE_COLUMN2, DATABASE_COLUMN3], [file_path, 'DateTimeOriginal', file_name], logger)

                        # Catch exceptions and log them
                        except Exception as e:
                            logger.error(f"Error updating DateTimeOriginal EXIF data for \"{file_path}\": {e}")
                    else:
                        logger.info(f"\"{file_path}\" already has correct EXIF data.")
                        record_db_update(DATABASE_NAME, DATABASE_TABLE, [DATABASE_PRIMARY, DATABASE_COLUMN2, DATABASE_COLUMN3], [file_path, 'DateTimeOriginal', file_name], logger)

# Command line interaction
if len(sys.argv) > 1:
    start_directory = sys.argv[1]
if not os.path.isdir(start_directory):
    logger.error(f"\"{start_directory}\" is not a valid directory.")
    sys.exit(1)
setup_database(DATABASE_NAME, 
    f'''
        CREATE TABLE IF NOT EXISTS {DATABASE_TABLE} (
            {DATABASE_PRIMARY} TEXT PRIMARY KEY,
            {DATABASE_COLUMN2} TEXT,
            {DATABASE_COLUMN3} TEXT
        )
    ''', logger)

process_images(start_directory)