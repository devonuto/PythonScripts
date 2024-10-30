import os
import re
import sys


from logger_config import setup_custom_logger
from tqdm import tqdm
from shared_methods import (get_exif_data, add_exif_data, setup_database, has_been_processed, record_db_update,
                            close_connection, get_file_count, log_info, log_error, is_first_date_more_recent, 
                            check_requirements, DATETIME, PHOTO_EXTENSIONS)

logger = setup_custom_logger('Add-Missing-EXIF')
script_directory = os.path.dirname(os.path.abspath(__file__))
DATABASE_NAME = os.path.join(script_directory, 'exif_updates.db')
DATABASE_TABLE = 'file_updates'
DATABASE_PRIMARY = 'file_name'
DATABASE_COLUMN2 = 'exif_tag'
DATABASE_COLUMN3 = 'exif_data'
CONN = None

# Process images in the start_directory    
def process_images(start_directory):
    """
    Processes image files within the specified directory, verifying and updating EXIF data.

    This function traverses all subdirectories starting from the given directory, identifying image files that meet
    specific criteria based on photo extensions. It checks if the image files have been processed before, updates their
    EXIF data if necessary, and logs the operations. Progress is monitored and displayed using a progress bar.

    Args:
    - start_directory (str): The directory from which image processing will begin.

    Note:
    - Assumes global constants for photo extensions, database connections, logger configurations, and EXIF data patterns.
    - The function skips non-standard directories and processes only files matching the defined photo extensions.
    - Incorporates detailed logging, database updates, and EXIF data verification and correction based on filename patterns.
    """
    total_files = get_file_count(start_directory, PHOTO_EXTENSIONS, logger)
    progress_bar = tqdm(total=total_files, desc='Processing Files', unit='files')
    # Find image files anywhere within the start_directory that match DATETIME format
    for root, dirs, files in os.walk(start_directory):
        # Modify dirs in-place to skip non-standard directories
        dirs[:] = [d for d in dirs if re.match(r'^[a-zA-Z0-9]', d)]
        files = [f for f in files if '.' + f.split('.')[-1].lower() in PHOTO_EXTENSIONS]
        for file in files:
            file_path = os.path.join(root, file)
            file_name, _ = os.path.splitext(file)        
            
            if has_been_processed(CONN, DATABASE_TABLE, DATABASE_PRIMARY, os.path.basename(file_path), logger):
                progress_bar.update(1)
                continue

            # Check if the file has a DATETIME in the filename
            match = DATETIME.match(file)
            if match:
                # Get the date and time from the file's EXIF data
                exif_date = get_exif_data(file_path, 'DateTimeOriginal', logger, progress_bar)
                # if not exif_date or exif_date is more recent than date_time in filename, update exif data with date_time
                if is_first_date_more_recent(exif_date, file_name):
                    # Add the date and time to the file's EXIF data from filename
                    try:
                        if add_exif_data(file_path, 'DateTimeOriginal', file_name, progress_bar):
                            log_info(logger, f"Updated DateTimeOriginal from \"{exif_date}\" to \"{file_name}\" on \"{file_path}\".", progress_bar)
                            record_db_update(CONN, DATABASE_TABLE, [DATABASE_PRIMARY, DATABASE_COLUMN2, DATABASE_COLUMN3], 
                                             [os.path.basename(file_path), 'DateTimeOriginal', file_name], logger, [DATABASE_PRIMARY], progress_bar)

                    # Catch exceptions and log them
                    except Exception as e:
                        msg = f"Error updating DateTimeOriginal EXIF data for \"{file_path}\""
                        log_error(logger, msg, e, progress_bar)
                else:
                    log_info(logger, f"\"{file_path}\" already has correct EXIF data.", progress_bar)
                    record_db_update(CONN, DATABASE_TABLE, [DATABASE_PRIMARY, DATABASE_COLUMN2, DATABASE_COLUMN3], 
                                     [os.path.basename(file_path), 'DateTimeOriginal', file_name], logger, [DATABASE_PRIMARY], progress_bar)
                progress_bar.refresh()
            progress_bar.update(1)
    progress_bar.close()    

# Command line interaction
if __name__ == '__main__':
    check_requirements()
    log_info(logger, f"Current working directory: {os.getcwd()}")
    if len(sys.argv) > 1:
        start_directory = sys.argv[1]
    if not os.path.isdir(start_directory):
        log_error(logger, f"\"{start_directory}\" is not a valid directory.")
        sys.exit(1)
    CONN = setup_database(DATABASE_NAME, 
        f'''
            CREATE TABLE IF NOT EXISTS {DATABASE_TABLE} (
                {DATABASE_PRIMARY} TEXT PRIMARY KEY,
                {DATABASE_COLUMN2} TEXT,
                {DATABASE_COLUMN3} TEXT
            )
        ''', logger)
    try:
        process_images(start_directory)
    except Exception as e:
        log_error(logger, "An error occurred.", e)
        sys.exit(1)
    finally:
        close_connection(CONN, logger)
        log_info(logger, "Processing complete.")