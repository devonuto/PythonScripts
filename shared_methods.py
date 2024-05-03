import os
import re
import sqlite3
import subprocess

DATETIME = re.compile(r'^\d{4}[\-\:\.]\d{2}[\-\:\.]\d{2}\s\d{2}[\-\:\.]\d{2}[\-\:\.]\d{2}([\-\:\.]\d{3})?', re.IGNORECASE)

# Helper function to add EXIF data to the file
def add_exif_data(file_path, exif_tag, exif_data, logger):
    try:
        # Define the command to run exiftool and parse with awk
        cmd = f'exiftool -overwrite_original -{exif_tag}="{exif_data}" "{file_path}"'
        # Execute the command
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, text=True)
        # Check if the command was successful
        if result.returncode == 0:        
            return True
        else:
            logger.error(f"Error adding {exif_tag} EXIF data to \"{file_path}\": {result.stderr.strip()}")
            return False
    except Exception as e:
        logger.error(f"Error adding {exif_tag} EXIF data to \"{file_path}\": {e}")
        return False

# Helper function to get the EXIF data from the file
def get_exif_data(file_path, exif_tag, logger):
    try:
        # Define the command to run exiftool and parse with awk
        cmd = f"exiftool -{exif_tag} \"{file_path}\"" + " | awk -F': ' 'BEGIN {OFS=\":\"} {for (i=2; i<=NF; i++) printf \"%s%s\", $i, (i==NF ? \"\\n\" : OFS)}'"
        # Execute the command
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, text=True)
        # Check if the command was successful
        if result.returncode == 0 and result.stdout.strip():
            exif_date = result.stdout.strip()
            if not  DATETIME.match(exif_date):
                return None
            
            return exif_date
        elif result.returncode == 1 or result.stderr.strip():
            return Exception(result.stderr.strip())
        else:
            return None
    except Exception as e:
        logger.error(f"Error getting {exif_tag} EXIF data from \"{file_path}\": {e}")
        return None
    
# Get a unique filename by appending an index to the filename if a conflict exists
def get_unique_filename(destination_item):    
    if not os.path.exists(destination_item):
        return destination_item  # Return the original name if there is no conflict

    base, extension = os.path.splitext(destination_item)
    index = 1
    # Create a new filename with an index
    new_destination_item = f"{base} ({index}){extension}"
    # Increment the index until a unique filename is found
    while os.path.exists(new_destination_item):
        index += 1
        new_destination_item = f"{base} ({index}){extension}"

    return new_destination_item

def has_been_processed(database_name, table, columns, value, logger):
    try:
        conn = sqlite3.connect(database_name)
        c = conn.cursor()

        # Ensure columns is a list even if a single column name is provided as a string
        if isinstance(columns, str):
            columns = [columns]  # Convert single string to list

        # Construct the WHERE clause dynamically to compare multiple columns using OR
        where_clause = ' OR '.join([f"{col} = ?" for col in columns])
        query = f"SELECT 1 FROM {table} WHERE {where_clause}"
        params = tuple([value] * len(columns))

        c.execute(query, params)
        exists = c.fetchone() is not None
        conn.close()
        return exists
    except Exception as e:
        logger.error(f"Error checking if \"{value}\" has been processed in any of {columns}: {e}")
        return False
    
def move_or_rename_file(source, destination, logger):
    if source == destination:
        logger.info(f"Source and destination are the same: \"{source}\".")
        return 
    try:
        # Check if the destination folder exists, if not, create it
        destination_folder = os.path.dirname(destination)
        if not os.path.exists(destination_folder):
            os.makedirs(destination_folder)

        # Get a unique filename if a conflict exists
        destination = get_unique_filename(destination)

        os.rename(source, destination)
        # Log moved if file name is same, but destination folder is different
        if os.path.basename(source) == os.path.basename(destination):
            logger.info(f"Moved \"{source}\" to \"{destination}\".")
        # destination folder is different and file name is different
        elif os.path.basename(source) != os.path.basename(destination) and os.path.dirname(source) != os.path.dirname(destination):
            logger.info(f"Moved and Renamed \"{source}\" to \"{destination}\".")
        # destination folder is different and file name is same
        else: 
            logger.info(f"Renamed \"{source}\" to \"{destination}\".")
    except Exception as e:
        logger.error(f"Error moving \"{source}\" to \"{destination}\": {e}")

def record_db_update(database_name, table_name, columns, values, logger):
    """
    Record an update in the database.
    
    :param database_name: Name of the SQLite database file.
    :param table_name: Name of the table to insert data into.
    :param columns: List of column names.
    :param values: List of values corresponding to the column names.
    """    
    try:
        # Connect to the specified SQLite database
        conn = sqlite3.connect(database_name)
        c = conn.cursor()

        # Prepare the SQL query
        columns_str = ', '.join(columns)
        placeholders = ', '.join(['?' for _ in values])  # Create placeholders based on the number of values
        sql = f'INSERT INTO {table_name} ({columns_str}) VALUES ({placeholders})'

        # Execute the SQL command
        c.execute(sql, values)

        # Commit the changes and close the connection
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Error recording update in database: {e}")

# Helper function to setup the database
def setup_database(database_name, sql, logger):
    try:
        conn = sqlite3.connect(database_name)
        c = conn.cursor()
        c.execute(sql)
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Error setting up database: {e}")