import os
import pyodbc
import shutil
import subprocess
import json
import time
from datetime import datetime

# =================================================================================================
#  Configuration
# =================================================================================================

# --- !! UPDATE THESE VALUES !! ---

# The name of the SQL Server instance to connect to.
SERVER_NAME = r".\SQLEXPRESS"

# The FINAL destination folder for your backups on the network share.
# Example: r'\\YourNAS\SQLBackups'
BACKUP_PATH = r"\\devomedia\media\Backups\SQLBackups"

# A TEMPORARY folder on the LOCAL machine where SQL Server will write the backup file first.
# This folder must exist. Example: r'C:\SQLTemp'
LOCAL_TEMP_PATH = r"C:\SQL_Temp_Backups"

# The number of recent backups to keep for each database in the final network location.
BACKUPS_TO_KEEP = 3

# --- Path to the configuration file for network credentials ---
CONFIG_FILE = "config.json"

# =================================================================================================
#      Do not edit below this line unless you know what you are doing.
# =================================================================================================


def load_network_credentials():
    """
    Loads network credentials from the config.json file.
    Returns (username, password) or (None, None) if not found or an error occurs.
    """
    if not os.path.exists(CONFIG_FILE):
        print(
            f"Info: Credentials file '{CONFIG_FILE}' not found. Proceeding without network authentication."
        )
        return None, None

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)
            user = config.get("NETWORK_USER")
            password = config.get("NETWORK_PASSWORD")
            if not user or not password:
                print(
                    f"Warning: '{CONFIG_FILE}' is missing 'NETWORK_USER' or 'NETWORK_PASSWORD'."
                )
                return None, None
            return user, password
    except (json.JSONDecodeError, IOError) as e:
        print(f"Error reading or parsing '{CONFIG_FILE}': {e}")
        return None, None


def cleanup_old_backups(db_name):
    """
    Deletes the oldest backup files for a given database from the final network destination.
    """
    print(f"  -> Cleaning up old backups for '{db_name}' from {BACKUP_PATH}...")
    try:
        backup_files = [
            f
            for f in os.listdir(BACKUP_PATH)
            if f.startswith(f"{db_name}_") and f.endswith(".bak")
        ]

        if len(backup_files) <= BACKUPS_TO_KEEP:
            print(
                f"  -> No old backups to delete for '{db_name}'. Kept {len(backup_files)} of {BACKUPS_TO_KEEP}."
            )
            return

        files_with_dates = [
            (
                os.path.join(BACKUP_PATH, f),
                os.path.getmtime(os.path.join(BACKUP_PATH, f)),
            )
            for f in backup_files
        ]
        files_with_dates.sort(key=lambda x: x[1])

        files_to_delete_count = len(files_with_dates) - BACKUPS_TO_KEEP
        files_to_delete = files_with_dates[:files_to_delete_count]

        print(
            f"  -> Found {len(files_with_dates)} backups. Deleting {len(files_to_delete)} oldest backups..."
        )
        for file_path, _ in files_to_delete:
            try:
                os.remove(file_path)
                print(f"  -> Deleted old backup: {os.path.basename(file_path)}")
            except OSError as e:
                print(f"  -> Error deleting file {file_path}: {e}")

    except (OSError, FileNotFoundError) as e:
        print(f"  -> An error occurred during cleanup for '{db_name}': {e}")


def establish_network_connection(unc_share, network_user, network_password):
    """
    Establishes a network connection to the UNC share if credentials are provided.
    Returns True if connection was established, False otherwise.
    """
    if network_user and network_password:
        print(
            f"Attempting to connect to network share '{unc_share}' with user '{network_user}'..."
        )
        connect_command = [
            "net",
            "use",
            unc_share,
            f"/user:{network_user}",
            network_password,
        ]
        try:
            subprocess.run(connect_command, check=True, capture_output=True, text=True)
            print("  -> Network connection successful.")
            return True
        except subprocess.CalledProcessError as e:
            print(f"  -> ERROR: Failed to connect to network share '{unc_share}'.")
            print(f"  -> 'net use' command failed with error: {e.stderr}")
            return False
    return False


def ensure_directories(paths):
    """
    Ensures that the given directories exist.
    """
    for path in paths:
        if not os.path.exists(path):
            os.makedirs(path)
            print(f"Created directory: {path}")


def connect_to_sql_server():
    """
    Connects to the SQL Server and returns the connection and cursor.
    """
    conn_str = (
        f"DRIVER={{ODBC Driver 17 for SQL Server}};"
        f"SERVER={SERVER_NAME};"
        f"DATABASE=master;"
        f"Trusted_Connection=yes;"
    )
    db_connection = pyodbc.connect(conn_str, autocommit=True)
    cursor = db_connection.cursor()
    print(f"Successfully connected to SQL Server: {SERVER_NAME}")
    return db_connection, cursor


def get_user_databases(cursor):
    """
    Retrieves the list of user databases.
    """
    get_db_query = "SELECT name FROM sys.databases WHERE name NOT IN ('master', 'model', 'msdb', 'tempdb') AND state = 0;"
    cursor.execute(get_db_query)
    databases = [row.name for row in cursor.fetchall()]
    return databases


def backup_database(cursor, db_name, local_backup_path):
    """
    Performs the backup of a single database to the local path.
    """
    print(f"\n  -> Backing up '{db_name}' to local temp path: '{local_backup_path}'...")
    backup_sql = f"BACKUP DATABASE [{db_name}] TO DISK = N'{local_backup_path}' WITH NOFORMAT, NOINIT, SKIP, NOREWIND, NOUNLOAD, STATS = 10"
    cursor.execute(backup_sql)
    # Wait for a moment to ensure SQL Server releases the file lock before we try to move it.
    time.sleep(2)
    print(f"  -> Local backup for '{db_name}' completed successfully.")


def move_backup_file(local_backup_path, final_network_path):
    """
    Moves the backup file from local to network path.
    """
    try:
        print(f"  -> Moving '{local_backup_path}' to '{final_network_path}'...")
        shutil.move(local_backup_path, final_network_path)
        print("  -> Move successful.")
        return True
    except (OSError, shutil.Error) as e:
        print(f"  -> CRITICAL ERROR: Failed to move backup to network share: {e}")
        print(
            f"  -> The backup file remains in the local temp folder: {local_backup_path}"
        )
        return False


def disconnect_network_share(unc_share):
    """
    Disconnects from the network share.
    """
    print(f"Disconnecting from network share '{unc_share}'...")
    disconnect_command = ["net", "use", unc_share, "/delete"]
    subprocess.run(disconnect_command, check=False, capture_output=True)
    print("  -> Network connection closed.")


def backup_all_databases():
    """
    Backs up all user databases to a local temporary folder, then moves them to a network share.
    """
    print("Starting SQL Server backup process...")

    network_connection_established = False
    db_connection = None

    network_user, network_password = load_network_credentials()

    # Correctly construct the UNC path for the share (e.g., \\server\share)
    try:
        path_parts = BACKUP_PATH.split(os.sep)
        unc_share = f"\\\\{path_parts[2]}\\{path_parts[3]}"
    except IndexError:
        print(f"CRITICAL ERROR: The BACKUP_PATH '{BACKUP_PATH}' is not a valid UNC path.")
        return

    try:
        # STEP 1: Establish network connection (if credentials were loaded)
        network_connection_established = establish_network_connection(
            unc_share, network_user, network_password
        )

        # STEP 2: Ensure directories exist
        ensure_directories([LOCAL_TEMP_PATH, BACKUP_PATH])

        # STEP 3: Connect to SQL Server
        db_connection, cursor = connect_to_sql_server()

        # STEP 4: Get user databases
        databases = get_user_databases(cursor)

        if not databases:
            print("No user databases found to back up.")
            return

        print(f"Found databases to back up: {', '.join(databases)}")

        # STEP 5: Loop through databases for backup, move, and cleanup
        for db_name in databases:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file_name = f"{db_name}_{timestamp}.bak"
            local_backup_path = os.path.join(LOCAL_TEMP_PATH, backup_file_name)
            final_network_path = os.path.join(BACKUP_PATH, backup_file_name)

            backup_database(cursor, db_name, local_backup_path)

            if move_backup_file(local_backup_path, final_network_path):
                cleanup_old_backups(db_name)

        print("\nAll database backups and cleanup operations completed.")

    except pyodbc.Error as ex:
        sqlstate = ex.args[0]
        print("CRITICAL ERROR: An error occurred with the SQL Server connection or backup process.")
        print(f"  -> SQLSTATE: {sqlstate}")
        print(f"  -> {ex}")
    except (OSError, shutil.Error) as e:
        print(f"An unexpected file or OS error occurred: {e}")

    finally:
        # --- FINAL STEP: Disconnect from network and database ---
        if network_connection_established:
            disconnect_network_share(unc_share)

        if db_connection:
            db_connection.close()
            print("Database connection closed.")


if __name__ == "__main__":
    backup_all_databases()
