import os
import re
import shutil
import sqlite3
import subprocess
import sys
import importlib.util
from datetime import datetime
from importlib import metadata

DATETIME = re.compile(r'^\d{4}[\-\:\.]\d{2}[\-\:\.]\d{2}\s\d{2}[\-\:\.]\d{2}[\-\:\.]\d{2}([\-\:\.]\d{3})?', re.IGNORECASE)
DESIRED_FORMAT = re.compile(r'^(\d{4}-\d{2}-\d{2} \d{2}\.\d{2}\.\d{2}\.\d{3})', re.IGNORECASE)
PHOTO_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif' }
VIDEO_EXTENSIONS = {'.m4v', '.mov', '.mp4', '.mkv', '.wmv', '.webm'}
MEDIA_EXTENSIONS = PHOTO_EXTENSIONS.union(VIDEO_EXTENSIONS)

# Helper function to add EXIF data to the file
def add_exif_data(file_path, exif_tag, exif_data, logger, progress_bar=None):
    """
    Adds or updates EXIF metadata to an image file using exiftool.

    This function runs a command to update the EXIF data for a specified tag on a given image file. 
    If the operation is successful, it returns True; otherwise, it logs the error and returns False.

    Args:
    - file_path (str): The path to the image file where the EXIF data will be added or updated.
    - exif_tag (str): The EXIF tag (e.g., 'Artist', 'GPSLatitude') to be modified or added.
    - exif_data (str): The data to be set for the specified EXIF tag.
    - logger: A logging object used for logging information and errors.
    - progress_bar (optional): An optional progress bar object for visual progress feedback.

    Returns:
    - bool: True if the EXIF data was successfully added or updated, False otherwise.

    Raises:
    - Exception: Propagates any exceptions that occur during the execution, including subprocess errors.
    """
    try:
        # Define the command to run exiftool and parse with awk
        exiftool_path = get_exiftool_path()
        cmd = f'{exiftool_path} -overwrite_original -{exif_tag}="{exif_data}" "{file_path}"'
        # Execute the command
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, text=True)
        # Check if the command was successful
        if result.returncode == 0:        
            return True
        else:
            log_info(logger, f"Error adding {exif_tag} EXIF data to \"{file_path}\": {result.stderr.strip()}", progress_bar)
            return False
    except Exception as e:
        log_error(logger, f"Error adding {exif_tag} EXIF data to \"{file_path}\":", e, progress_bar)
        return False


def check_exiftool():
    try:
        exiftool_path = get_exiftool_path()
        # Attempt to run 'exiftool -ver' to get the version
        result = subprocess.run([exiftool_path, '-ver'], capture_output=True, text=True, check=True)
        # If successful, print the version and return True
        print(f"ExifTool is available, version: {result.stdout.strip()}")
        return True
    except subprocess.CalledProcessError as e:
        # Handle cases where exiftool is not functional
        print("Failed to run ExifTool:", e)
    except FileNotFoundError:
        # Handle the case where exiftool is not found in the system path
        print("ExifTool is not installed or not found in the system path.")
    return False

def check_requirements():
    """
    Checks if all required system tools and Python packages are available.

    Raises:
        Exception: If any of the required tools or packages are missing.
    """
    # System tools expected to be available (e.g., exiftool)
    system_tools = ['exiftool']

    # Python packages and modules to check (as a dictionary with None if no version check is needed)
    python_packages = {
        'sqlite3': None,  # Standard library module, no version required
        'tqdm': '4.46.0'  # Minimum version requirement for tqdm
    }

    # Check for system tools
    for tool in system_tools:
        if not shutil.which(tool):
            raise Exception(f"Required system tool missing: {tool}")

    # Check for Python packages
    for package, required_version in python_packages.items():
        if required_version is None:
            # Check by trying to import the module
            if importlib.util.find_spec(package) is None:
                raise Exception(f"Required Python module not installed: {package}")
        else:
            # Check using importlib.metadata for external packages
            try:
                version = metadata.version(package)
                if version < required_version:
                    raise Exception(f"Package '{package}' version '{version}' is below required version '{required_version}'")
            except metadata.PackageNotFoundError:
                raise Exception(f"Required Python package not installed: {package}")

    print("All system requirements are satisfied.")


# Helper function to close the database connection
def close_connection(conn, logger, progress_bar=None):
    """
    Safely closes a database connection and logs the operation.

    This function attempts to close an open database connection. If the connection is successfully closed,
    it logs this action. If an error occurs during the closure process, it logs the error.

    Args:
    - conn: The database connection object to be closed. Can be any connection object that supports the .close() method.
    - logger: A logging object used for logging information and errors.
    - progress_bar (optional): An optional progress bar object for visual progress feedback during the operation.

    Returns:
    - None: This function does not return a value but will modify the conn variable to None after closing it.

    Raises:
    - Exception: Captures and logs any exceptions that occur during the closing of the database connection.
    """
    try:
        if conn:
            conn.close()
            log_info(logger, "Closed database connection.", progress_bar)
            conn = None
    except Exception as e:
        log_error(logger, f"Error closing database connection:", e, progress_bar)

def convert_exif_date(exif_date):
    """
    Converts an EXIF date string from the format 'YYYY:MM:DD HH:MM:SS' to 'YYYY-MM-DD HH.MM.SS'.

    This function takes an EXIF date string and reformats it, changing the date separator from colon to dash
    and the time separator from colon to period. If the input is improperly formatted or None, the function
    returns None.

    Args:
    - exif_date (str): The EXIF date string to be converted.

    Returns:
    - str or None: The reformatted date string, or None if there was an error in processing or the input was None.

    Note:
    - The function is designed to handle the standard EXIF date format and may not work correctly with non-standard formats.
    """
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
    except Exception:
        return None        

def delete_empty_folders(directory, logger, progress_bar=None):
    """
    Recursively deletes all empty folders in a specified directory.

    This function traverses the specified directory from bottom to top, identifying and deleting
    any subdirectories that are empty. Each deletion attempt is logged. Errors encountered during
    deletion are also logged.

    Args:
    - directory (str): The path of the directory to check for empty subdirectories.
    - logger: A logging object used for logging information and errors during the operation.
    - progress_bar (optional): An optional progress bar object that can be used to show progress of the operation.

    Note:
    - The function uses os.walk with topdown=False to ensure that it checks subdirectories before their parents.
    - Deletion is attempted only on directories that are completely empty (no files or subdirectories).
    """
    for dirpath, dirnames, filenames in os.walk(directory, topdown=False):
        dirnames[:] = [d for d in dirnames 
                       if not d.startswith('@') 
                       and not d.startswith('.') 
                       and not d.startswith('$') 
                       and not d.startswith('~')]
        
        # Check if directory is empty
        if not dirnames and not filenames:
            try:
                shutil.rmtree(dirpath, ignore_errors=True)
                log_info(logger, f"Deleted empty folder: {dirpath}", progress_bar)
            except OSError as e:
                log_error(logger, f"Failed to delete {dirpath}:", e, progress_bar)

def get_date_object(date_str):
    """
    Converts a date string into a datetime.date object using a specific format.

    This function takes a string representation of a date, potentially included in a larger string
    with time or other data, and converts just the date part to a datetime.date object. The function
    assumes the date is in the format 'YYYY-MM-DD', 'YYYY:MM:DD', or 'YYYY.MM.DD', even if additional
    time or text information is included in the string.

    Args:
    - date_str (str): A string containing the date, which may also include time or other text.

    Returns:
    - datetime.date: A date object representing just the date part of the input string.

    Raises:
    - ValueError: If the date_str is in an incorrect format or cannot be parsed into a date.

    Example:
    - Input: '2023-06-01 12:00:00'
    - Output: datetime.date(2023, 6, 1)
    """
    # Define the date-only format
    date_format = '%Y-%m-%d'
    # Split the string to extract the date part only
    date_part = date_str.split(' ')[0]
    # Sanitize the date part to ensure it uses '-' as the separator
    sanitized_date_part = date_part.replace(':', '-').replace('.', '-')    
    # Parse the date part
    return datetime.strptime(sanitized_date_part, date_format)

def get_exiftool_path():
    # Check if running on Windows
    if sys.platform.startswith('win'):
        # Windows specific path, adjust as necessary
        return r"exiftool"
    else:
        # Linux and other unix-like OSs
        return "/usr/share/applications/ExifTool/exiftool"

def is_desired_media_file_format(filename):
    return bool(DESIRED_FORMAT.match(filename))

def is_first_date_more_recent(date_str1, date_str2):
    """
    Determines if the first date string represents a more recent date compared to the second date string.

    Parameters:
    date_str1 (str): The first date string to compare.
    date_str2 (str): The second date string to compare.

    Returns:
    bool: True if the first date is more recent than the second date, False otherwise or if any date string is empty or invalid.

    Assumptions:
    - `date_str1` and `date_str2` should be in a format recognizable by the `get_date_object` function.
    - This function assumes that the `get_date_object` can parse the date strings and return date objects.
    - A global `DATETIME` regex pattern is used to validate date strings before parsing.
    """

    if (not date_str1) or (not date_str2):
        return True
    
    if not DATETIME.search(date_str1) or not DATETIME.search(date_str2):
        return True

    date1 = get_date_object(date_str1)
    date2 = get_date_object(date_str2)

    # Compare the dates and return True if date1 is more recent, False otherwise
    result = date1 > date2
    return result

def get_exif_data(file_path, exif_tag, logger, progress_bar=None):
    """
    Retrieves a specific EXIF data value from an image file using exiftool.

    This function runs the 'exiftool' command to extract the value of a specified EXIF tag from the provided
    image file. It processes the command's output to find the relevant tag and return its value. If the command
    fails or the tag is not found, the function logs an error and returns None.

    Args:
    - file_path (str): The path to the image file from which to extract EXIF data.
    - exif_tag (str): The specific EXIF tag (e.g., 'DateTimeOriginal', 'GPSLatitude') for which the value is requested.
    - logger: A logging object used for logging information and errors.
    - progress_bar (optional): An optional progress bar object that can be used to indicate progress.

    Returns:
    - str or None: The value of the specified EXIF tag, or None if the tag could not be found or an error occurred.

    Raises:
    - Exception: Raises and logs an exception if there is an error in executing the exiftool command or processing the output.
    """
    try:
        exiftool_path = get_exiftool_path()        
        cmd = f'{exiftool_path} -{exif_tag} "{file_path}"'
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, text=True)

        if result.returncode == 0:
            # Assuming the output is "Tag Name: Value"
            output = result.stdout.strip()
            # Split the output into lines and then extract the value after the colon
            value = None
            for line in output.split('\n'):
                parts = line.split(': ', 1)  # Split on the first colon only
                if len(parts) == 2:
                    _, value = parts
            
            return value.strip() if value else None
        else:
            raise Exception(f"Error reading EXIF data: {result.stderr}")
    except Exception as e:
        log_error(logger, f"Error getting {exif_tag} EXIF data from \"{file_path}\":", e, progress_bar)
        return None
    
def get_exif_datetime(file_path, date_exif_tag, micro_exif_tag, logger, progress_bar=None):
    """
    Retrieves and constructs a complete datetime string from EXIF data, optionally including microseconds.

    This function extracts the datetime and microseconds (if specified) from an image file's EXIF data and combines them
    into a single datetime string. If the datetime data is not found, or if there are issues retrieving it, the function returns None.

    Args:
    - file_path (str): The path to the image file from which to extract EXIF data.
    - date_exif_tag (str): The EXIF tag for the date and time component (e.g., 'DateTimeOriginal').
    - micro_exif_tag (str): The optional EXIF tag for the microseconds component.
    - logger: A logging object used for logging information and errors.
    - progress_bar (optional): An optional progress bar object for visual progress feedback.

    Returns:
    - str or None: A string representing the full datetime with microseconds, or None if essential data couldn't be retrieved.

    Note:
    - Microsecond data is formatted to ensure exactly three digits are used, padding with zeros if necessary.
    """
    micro = '000'    
    datetime_str = get_exif_data(file_path, date_exif_tag, logger, progress_bar)
    if not datetime_str:
        return None

    if micro_exif_tag:
        microseconds = get_exif_data(file_path, micro_exif_tag, logger, progress_bar)
        # Check and format micro, even if it hasn't changed from '000'
        if microseconds and microseconds.isdigit():
            # Ensure micro has exactly three digits
            micro = (microseconds.ljust(3, '0') if len(microseconds) < 3 else str(round(float('0.' + microseconds), 3))[2:].ljust(3, '0'))
    
    # Build the final datetime string
    datetime_str += '.' + micro
    return datetime_str        

# Get the count of files in a directory based on the filter
def get_file_count(directory, filter, logger, progress_bar=None):
    """
    Counts the number of files in a directory that match a given filter.

    This function recursively searches through the specified directory and its subdirectories,
    counting all files that match the specified filter. The filter should be a list of file extensions,
    including the dot (e.g., ['.jpg', '.png']). It logs the process and any errors encountered.

    Args:
    - directory (str): The path to the directory where files are to be counted.
    - filter (list): A list of string extensions to include in the count.
    - logger: A logging object used for logging information and errors.
    - progress_bar (optional): An optional progress bar object for visual progress feedback.

    Returns:
    - int: The total number of files matching the filter in the specified directory.

    Raises:
    - Exception: Captures and logs any exceptions that occur during the file counting process.
    """
    try:
        log_info(logger, f"Counting {filter} files in directory: {directory}", progress_bar)
        total_files = 0
        for root, dirs, files in os.walk(directory):
            dirs[:] = [d for d in dirs if re.match(r'^[a-zA-Z0-9]', d)]
            files = [f for f in files if '.' + f.split('.')[-1].lower() in filter]
            total_files += len(files)
    except Exception as e:
        log_error(logger, f"Error counting files in directory: {e}", progress_bar)
        total_files = 0
    finally:
        return total_files

# Get a unique filename by appending an index to the filename if a conflict exists
def get_unique_filename(source_item, destination_item):    
    """
    Generates a unique filename by appending an index if the provided filename already exists.

    This function checks if the given file path exists. If it does, it appends an index in parentheses
    to the base name of the file before the extension, incrementing the index until a unique filename is found.
    This ensures that files are not overwritten by new files with the same name.

    Args:
    - destination_item (str): The original file path for which a unique version is needed.

    Returns:
    - str: A unique filename path where no file already exists.

    Example:
    - Input: '/path/to/file.txt'
    - Output: '/path/to/file (1).txt'  # if '/path/to/file.txt' already exists
    """

    # Return the original name if there is no conflict
    if (source_item == destination_item):
        return destination_item

    if not os.path.exists(destination_item):
        return destination_item  # Return the original name if there is no conflict

    base, extension = os.path.splitext(destination_item)
    index = 1
    # Create a new filename with an index
    new_destination_item = f"{base} ({index}){extension}"
    # Increment the index until a unique filename is found
    while os.path.exists(new_destination_item):
        # Return the new destination name if there is no conflict
        if (source_item == new_destination_item):
            return new_destination_item
        
        index += 1
        new_destination_item = f"{base} ({index}){extension}"        

    return new_destination_item

def has_been_processed(conn, table, columns, value, logger, progress_bar=None):
    """
    Checks if a given value or set of values have already been processed by searching for them in specified columns of a database table.

    This function queries a SQLite database to determine if a specific value or a set of values exist in specified columns
    of a given table. It constructs a dynamic SQL query using the column names provided, searching for the value using an OR
    condition across those columns for a single value, or an AND condition for multiple values corresponding to each column.

    Args:
    - conn: The SQLite database connection object.
    - table (str): The name of the table to query.
    - columns (str or list): The column or list of columns to check for the value.
    - value: The value or list of values to check in the specified columns. If a list, must match the number of columns.
    - logger: A logging object used for logging information and errors.
    - progress_bar (optional): An optional progress bar object for visual progress feedback.

    Returns:
    - bool: True if the value(s) is found in the specified columns, False otherwise.

    Raises:
    - Exception: Logs and raises any exceptions encountered during database access or query execution.
    """
    try:
        # Connect to the specified SQLite database
        c = conn.cursor()

        # Ensure columns is a list even if a single column name is provided as a string
        if isinstance(columns, str):
            columns = [columns]  # Convert single string to list

        if isinstance(value, list) and len(value) == len(columns):
            # Construct the WHERE clause dynamically for multiple values using AND
            where_clause = ' AND '.join([f"{col} = ?" for col in columns])
            params = tuple(value)
        elif isinstance(value, list) and len(value) != len(columns):
            log_error(logger, "The number of values does not match the number of columns.", progress_bar=progress_bar)
            return False
        else:
            # Construct the WHERE clause dynamically to compare multiple columns using OR
            where_clause = ' OR '.join([f"{col} = ?" for col in columns])
            params = tuple([value] * len(columns))

        query = f"SELECT 1 FROM {table} WHERE {where_clause}"
        c.execute(query, params)
        exists = c.fetchone() is not None
        return exists
    except Exception as e:
        log_error(logger, f"Error checking if \"{value}\" has been processed in any of {columns}:", e, progress_bar)
        return False
    
def move_or_rename_file(source, destination, logger, progress_bar=None):
    """
    Moves or renames a file from a source path to a destination path, handling directory creation and filename conflicts.

    This function checks if the source and destination are the same, and if not, it attempts to move or rename the file.
    It ensures the destination directory exists and checks for filename conflicts, generating a unique filename if necessary.
    The function logs different actions based on whether the file was just moved or also renamed.

    Args:
    - source (str): The current path of the file to be moved or renamed.
    - destination (str): The target path for the file, which may include a new name for the file.
    - logger: A logging object used for logging information and errors.
    - progress_bar (optional): A progress bar object for visual feedback (optional).

    Returns:
    - str or None: The new file path if the operation was successful, or None if an error occurred.

    Raises:
    - Exception: Captures and logs any exceptions that occur during the file move or rename process.
    """
    if source == destination:
        log_info(logger, f"Source and destination are the same: \"{source}\".", progress_bar)
        return None
    try:
        # Check if the destination folder exists, if not, create it
        destination_folder = os.path.dirname(destination)
        if not os.path.exists(destination_folder):
            os.makedirs(destination_folder)

        # Get a unique filename if a conflict exists
        destination = get_unique_filename(source, destination)

        os.rename(source, destination)
        # Log moved if file name is same, but destination folder is different
        if os.path.basename(source) == os.path.basename(destination):
            log_info(logger, f"Moved \"{source}\" to \"{destination}\".", progress_bar)
        # destination folder is different and file name is different
        elif os.path.basename(source) != os.path.basename(destination) and os.path.dirname(source) != os.path.dirname(destination):
            log_info(logger, f"Moved and Renamed \"{source}\" to \"{destination}\".", progress_bar)
        # destination folder is different and file name is same
        else: 
            msg = f"Renamed \"{source}\" to \"{destination}\"."
            if progress_bar:
                progress_bar.set_description(msg)
            logger.info(msg)

        return destination
            
    except Exception as e:
        log_error(logger, f"Error moving \"{source}\" to \"{destination}\":", e, progress_bar)
        return None

def log_debug(logger, message, progress_bar=None):
    """
    Logs an informational message and optionally updates a progress bar with the message.

    This function logs a given message using the provided logger and, if a progress bar is provided, 
    updates the progress bar's description with the same message. This is useful for providing visual 
    feedback to the user along with logging the progress or status.

    Args:
    - logger: The logging object used to log the message.
    - message (str): The message to be logged.
    - progress_bar (optional): A progress bar object that can be updated with the message (optional).

    Note:
    - This function does not return a value; its purpose is purely to log information and update UI elements.
    """
    if progress_bar:
        progress_bar.set_description(message)
    if logger:
        logger.debug(message)

def log_info(logger, message, progress_bar=None):
    """
    Logs an informational message and optionally updates a progress bar with the message.

    This function logs a given message using the provided logger and, if a progress bar is provided, 
    updates the progress bar's description with the same message. This is useful for providing visual 
    feedback to the user along with logging the progress or status.

    Args:
    - logger: The logging object used to log the message.
    - message (str): The message to be logged.
    - progress_bar (optional): A progress bar object that can be updated with the message (optional).

    Note:
    - This function does not return a value; its purpose is purely to log information and update UI elements.
    """
    if progress_bar:
        progress_bar.set_description(message)
    if logger:
        logger.info(message)

def log_error(logger, message, e=None, progress_bar=None):
    """
    Logs an error message along with exception details and optionally updates a progress bar with the message.

    This function logs an error message using the provided logger, appending the exception information to provide
    a detailed error context. If a progress bar is provided, it updates the progress bar's description with the 
    error message. This aids in providing both visual feedback and detailed logs for error handling and diagnostics.

    Args:
    - logger: The logging object used to log the error.
    - message (str): The error message to be logged.
    - e (Exception): The exception object containing details of the error encountered.
    - progress_bar (optional): A progress bar object that can be updated with the error message (optional).

    Note:
    - This function does not return a value; its purpose is to log errors and update UI elements accordingly.
    """
    if progress_bar:
        progress_bar.set_description(message)

    if logger:
        logger.error(f"{message} {e if not None else ''}")

def log_warning(logger, message, progress_bar=None):
    """
    Logs a warning message and optionally updates a progress bar with the message.

    This function logs a given warning message using the provided logger and, if a progress bar is provided,
    updates the progress bar's description with the same message. This is useful for alerting users to potential
    issues while providing visual feedback alongside logging.

    Args:
    - logger: The logging object used to log the warning.
    - message (str): The warning message to be logged.
    - progress_bar (optional): A progress bar object that can be updated with the warning message (optional).

    Note:
    - This function does not return a value; its purpose is to log warnings and update UI elements.
    """
    if progress_bar:
        progress_bar.set_description(message)
    if logger:
        logger.warning(message)

import sys

def record_db_update(conn, table_name: str, columns: list, values: list, logger, unique_columns: list, progress_bar=None):
    """
    Records an update to a specified table in the database by inserting a new row
    or updating an existing row if it already exists.

    Args:
    - conn: The database connection object.
    - table_name (str): The name of the table where the new row will be inserted/updated.
    - columns (list): A list of column names into which the values will be inserted.
    - values (list): A list of values corresponding to the columns that will be inserted.
    - logger: A logging object used for logging information and errors.
    - unique_columns (list): A list of unique column names for conflict resolution.
    - progress_bar (optional): A progress bar object for visual feedback (optional).

    Raises:
    - Exception: Captures and logs any exceptions that occur during the database update, then exits the program.
    """
    try:
        with conn.cursor() as c:
            # Prepare the SQL query
            columns_str = ', '.join(columns)
            placeholders = ', '.join(['?' for _ in values])  # Create placeholders for values
            
            # Update clause
            update_str = ', '.join([f"{col} = ?" for col in columns])  
            
            # Prepare the ON CONFLICT clause for composite primary key
            unique_columns_str = ', '.join(unique_columns)
            
            sql = f'''
                INSERT INTO {table_name} ({columns_str}) 
                VALUES ({placeholders}) 
                ON CONFLICT({unique_columns_str}) 
                DO UPDATE SET {update_str}
            '''

            # Execute the SQL command
            c.execute(sql, values + values)  # Pass values for both insert and update

            # Commit the changes
            conn.commit()
    except Exception as e:
        log_error(logger, f"Error recording update in database:", e, progress_bar)
        sys.exit(1)

# Helper function to setup the database, and connection
def setup_database(database_name, sql, logger, progress_bar=None):
    """
    Sets up a database connection, executes a SQL command, and handles initialization.

    This function establishes a connection to a SQLite database, executes a provided SQL command for setup or configuration,
    and commits the changes. It logs the connection status and any errors encountered during the execution of the SQL command.
    If an error occurs, it logs the error, closes the connection, and exits the program.

    Args:
    - database_name (str): The name or path of the database file.
    - sql (str): The SQL command to be executed for setting up the database.
    - logger: A logging object used for logging information and errors.
    - progress_bar (optional): A progress bar object that can be updated with the status (optional).

    Returns:
    - sqlite3.Connection: The connection object to the database if setup is successful.

    Raises:
    - Exception: Captures and logs any exceptions that occur, then closes the connection and exits the application.
    """
    try:
        database_dir = os.path.dirname(os.path.abspath(__file__))
        database_name = os.path.join(database_dir, database_name)
        conn = sqlite3.connect(database_name)
        if not conn:
            raise Exception(f"Error connecting to database: {database_name}")
        log_info(logger, f"Connected to database: {database_name}", progress_bar)
        c = conn.cursor()
        c.execute(sql)
        conn.commit()
        return conn
    except Exception as e:
        log_error(logger, "Error setting up database", e, progress_bar)
        close_connection(logger)
        sys.exit(1)

