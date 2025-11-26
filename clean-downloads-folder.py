import os
import datetime
import pathlib
import stat # For changing file permissions
import errno # For error codes like EACCES
import traceback

# --- Configuration ---
DEFAULT_DAYS_TO_KEEP = 30  # Items older than this number of days will be deleted.

# --- Configuration ---
DEFAULT_DAYS_TO_KEEP = 30  # Items older than this number of days will be deleted.

def clean_downloads_folder(days_to_keep=DEFAULT_DAYS_TO_KEEP):
    """
    Deletes files and folders from the user's Downloads folder older than
    a specified number of days. This is a permanent deletion.
    """
    print("--- Downloads Folder Cleaner ---")
    # The PowerShell script has extensive comments warning the user.
    # This print serves as an initial runtime warning.
    print("INFO: This script will attempt to PERMANENTLY DELETE items.")
    print("      It does not use the Recycle Bin.")
    print("      Please ensure you understand the consequences.")
    print("---------------------------------------------------------")

    try:
        # Get the path to the user's Downloads folder
        user_profile = os.getenv('USERPROFILE')
        if not user_profile:
            print("Error: USERPROFILE environment variable not found. Exiting.")
            return

        downloads_path = pathlib.Path(user_profile) / "Downloads"

        # Verify the Downloads path exists
        if not downloads_path.is_dir():
            print(f"Error: Downloads folder not found at '{downloads_path}'. Please verify the path. Exiting.")
            return

        print(f"Targeting Downloads folder: {downloads_path}")

        # Calculate the cutoff date
        # datetime.now() gives current local time.
        # timedelta calculates the difference.
        cutoff_datetime = datetime.datetime.now() - datetime.timedelta(days=days_to_keep)
        # Convert cutoff_datetime to a timestamp for comparison with os.path.getmtime()
        cutoff_timestamp = cutoff_datetime.timestamp()
        print(f"Will delete items last modified before: {cutoff_datetime.strftime('%Y-%m-%d %H:%M:%S')}")

        # --- Scanning for items ---
        # This list will store Path objects of all items (files and folders)
        # whose own LastWriteTime is older than the cutoff.
        items_flagged_for_deletion = []

        print(f"Scanning for items older than {days_to_keep} days...")

        # os.walk traverses the directory tree.
        # topdown=True allows processing directories before their contents if needed,
        # but here we just collect all paths first.
        for root, dirs, files in os.walk(downloads_path, topdown=True):
            # Check files in the current root
            for name in files:
                item_path = pathlib.Path(root) / name
                try:
                    # os.path.getmtime returns the timestamp of last modification
                    if item_path.exists() and item_path.stat().st_mtime < cutoff_timestamp:
                        items_flagged_for_deletion.append(item_path)
                except FileNotFoundError:
                    # This can happen if a file is deleted while the script is scanning
                    print(f"Warning: File not found during scan (possibly deleted concurrently): {item_path}")
                except PermissionError:
                    print(f"Warning: Permission denied while accessing stats for file: {item_path}")
                except (OSError, IOError) as e:
                    # Handle OS-related errors from stat and other filesystem operations
                    print(f"Warning: Could not get stats for file {item_path}: {e}")

            # Check directories in the current root
            for name in dirs:
                item_path = pathlib.Path(root) / name
                try:
                    if item_path.exists() and item_path.stat().st_mtime < cutoff_timestamp:
                        items_flagged_for_deletion.append(item_path)
                except FileNotFoundError:
                    print(f"Warning: Directory not found during scan (possibly deleted concurrently): {item_path}")
                except PermissionError:
                    print(f"Warning: Permission denied while accessing stats for directory: {item_path}")
                except (OSError, IOError) as e:
                    print(f"Warning: Could not get stats for directory {item_path}: {e}")
        
        # Separate into files and folders
        old_files = [p for p in items_flagged_for_deletion if p.is_file()]
        old_folders = [p for p in items_flagged_for_deletion if p.is_dir()]

        # Sort folders by path length (depth) in descending order.
        # This is crucial for shutil.rmtree if old_folders contains nested directories
        # that are both independently marked as old. It ensures child directories are
        # processed (or would be if deleting one-by-one) before their parents.
        # For shutil.rmtree, it means if "parent/child" and "parent" are both old,
        # "parent/child" might be attempted first if it appears earlier in a naive list.
        # Sorting ensures that if we were to iterate and call rmtree, deeper paths are handled.
        # When rmtree is called on a parent, it handles children anyway. This sort primarily
        # helps avoid FileNotFoundError if a child was listed after a parent that got deleted.
        old_folders.sort(key=lambda p: len(str(p.resolve())), reverse=True)

        if not old_files and not old_folders:
            print(f"No items found older than {days_to_keep} days. No action taken.")
            return

        print(f"Found {len(old_files)} files and {len(old_folders)} folders (whose own mod date is old) to be deleted.")
        print("Attempting PERMANENT removal (Files first, then Folders)...")

        # --- Deletion Step ---
        # 1. Delete Files
        deleted_files_count = 0
        if old_files:
            print(f"\n--- Deleting {len(old_files)} files ---")
            for file_path in old_files:
                try:
                    if file_path.exists() and file_path.is_file(): # Check it's still there and is a file
                        print(f"  - Deleting File: {file_path}")
                        os.remove(file_path)
                        deleted_files_count += 1
                except PermissionError:
                    print(f"  - PermissionError for file {file_path}. Attempting to change permissions...")
                    try:
                        os.chmod(file_path, stat.S_IWUSR | stat.S_IWRITE) # Make writable
                        os.remove(file_path) # Retry deletion
                        deleted_files_count += 1
                        print(f"    Successfully deleted after changing permissions: {file_path}")
                    except (OSError, IOError) as e_chmod:
                        print(f"    Failed to delete file {file_path} even after attempting chmod: {e_chmod}")
                except FileNotFoundError:
                    print(f"  - File not found (already deleted or moved): {file_path}")
                except (OSError, IOError) as e:
                    print(f"  - Error deleting file {file_path}: {e}")
            print(f"File deletion phase complete. Deleted {deleted_files_count} files.")
        else:
            print("\nNo old files found to delete.")

        # 2. Delete Folders
        # These are folders that themselves had a LastWriteTime older than the cutoff.
        # However, we should NOT use shutil.rmtree() as it would delete newer files within old folders.
        # Instead, we only delete empty directories (after files are deleted, some dirs may become empty).
        # We'll attempt to remove empty directories by traversing bottom-up.
        deleted_folders_count = 0
        
        # Attempt to delete empty directories throughout the Downloads folder
        # Walk bottom-up (topdown=False) so we encounter leaf directories first
        print("--- Removing empty directories ---")
        for root, dirs, files in os.walk(downloads_path, topdown=False):
            for dir_name in dirs:
                folder_path = pathlib.Path(root) / dir_name
                try:
                    if folder_path.exists() and folder_path.is_dir():
                        # Check if the directory is empty
                        if not any(folder_path.iterdir()):
                            print(f"  - Deleting empty folder: {folder_path}")
                            folder_path.rmdir()
                            deleted_folders_count += 1
                except FileNotFoundError:
                    print(f"  - Folder not found (possibly already deleted): {folder_path}")
                except OSError as oe:
                    # Directory not empty or permission denied
                    if oe.errno == errno.ENOTEMPTY or oe.errno == errno.EACCES:
                        print(f"  - Skipping non-empty or inaccessible folder: {folder_path}")
                    else:
                        print(f"  - OSError deleting folder {folder_path}: {oe}")
        
        print(f"Empty directory removal phase complete. Deleted {deleted_folders_count} empty directories.")

        print("\nDeletion process finished.")

    except (OSError, IOError, PermissionError, RuntimeError) as e:
        print(f"A critical error occurred in the script: {e}")
        print("Traceback:")
        traceback.print_exc() # For debugging unexpected issues

    print("\nScript finished overall.")

if __name__ == "__main__":
    # --- WARNING AND EXECUTION ---
    # The main warning is printed when clean_downloads_folder() is called.
    # You can customize DAYS_TO_KEEP here or by adding command-line argument parsing (e.g., using argparse).
    
    # Example: To use a different number of days:
    # clean_downloads_folder(days_to_keep=60) 
    
    clean_downloads_folder(days_to_keep=DEFAULT_DAYS_TO_KEEP)
