import os
import re
import sys

from logger_config import setup_custom_logger
from tqdm import tqdm
from shared_methods import (get_exif_data, setup_database, has_been_processed, move_or_rename_file, close_connection, 
                            record_db_update, get_file_count, log_info, log_error, PHOTO_EXTENSIONS)

logger = setup_custom_logger('Find-PNGs-as-JPGs')
DATABASE_NAME = 'mislabled_images.db'
DATABASE_TABLE = 'file_updates'
DATABASE_PRIMARY = 'file_name'
DATABASE_COLUMN2 = 'extension'
DATABASE_COLUMN3 = 'file_type'
DATABASE_COLUMN4 = 'new_file_name'
CONN = None

# Process images in the start_directory
def process_images(start_directory):
    """
    Processes image files within the specified directory, updating filenames based on EXIF data.

    This function traverses all subdirectories of the given start directory, checking each image file for its type 
    via EXIF data and renaming the file if its extension does not match the EXIF file type. It also updates a database 
    with the new filenames and logs the actions performed. Progress is tracked and displayed using a progress bar.

    Args:
    - start_directory (str): The directory from which the image processing will begin.

    Note:
    - Assumes the existence of global constants for photo extensions, database connections, and logger configurations.
    - This function will skip non-standard directories and only process files that match defined photo extensions.
    - Incorporates logging, database updates, and conditional renaming based on file type verification.
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
            if has_been_processed(CONN, DATABASE_TABLE, [DATABASE_PRIMARY, DATABASE_COLUMN4], os.path.basename(file_path), logger):
                progress_bar.update(1)
                continue
            
            _, file_extension = os.path.splitext(file)
            file_type = None
            file_type = get_exif_data(file_path, 'FileType', logger, progress_bar)
            
            # if file_extension doesn't match file_type, rename the file
            if ((file_extension.lower() in ['.jpg', '.jpeg'] and file_type.lower() == 'png') or 
                (file_extension.lower() == '.png' and file_type.lower() == 'jpeg')):
                new_file_path = file_path.replace(file_extension, f".{file_type.lower()}")
                new_file_path = move_or_rename_file(file_path, new_file_path, logger, progress_bar)
                if new_file_path:
                    record_db_update(
                        CONN, 
                        DATABASE_TABLE, 
                        [DATABASE_PRIMARY, DATABASE_COLUMN2, DATABASE_COLUMN3, DATABASE_COLUMN4], 
                        [os.path.basename(file_path), file_extension, file_type, os.path.basename(new_file_path)], 
                        logger, 
                        progress_bar)

            else:
                log_info(logger, f"\"{file_path}\" is correctly labeled as a \"{file_type}\" file.", progress_bar)
                record_db_update(
                    CONN, 
                    DATABASE_TABLE, 
                    [DATABASE_PRIMARY, DATABASE_COLUMN2, DATABASE_COLUMN3, DATABASE_COLUMN4], 
                    [os.path.basename(file_path), file_extension, file_type, os.path.basename(file_path)], 
                    logger,
                    progress_bar)
            progress_bar.refresh()
            progress_bar.update(1)
    progress_bar.close()
    

# Command line interaction
if __name__ == '__main__':
    if len(sys.argv) > 1:
        start_directory = sys.argv[1]
    if not os.path.isdir(start_directory):
        log_error(logger, f"\"{start_directory}\" is not a valid directory.")
        sys.exit(1)
    CONN = setup_database(DATABASE_NAME, f'''
            CREATE TABLE IF NOT EXISTS {DATABASE_TABLE} (
                {DATABASE_PRIMARY} TEXT PRIMARY KEY,
                {DATABASE_COLUMN2} TEXT,
                {DATABASE_COLUMN3} TEXT,
                {DATABASE_COLUMN4} TEXT
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