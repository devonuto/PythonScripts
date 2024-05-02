import os

from logger_config import setup_custom_logger
logger = setup_custom_logger('Quick-Rename')

def rename_files(root_directory):
    for dirpath, dirnames, filenames in os.walk(root_directory):
        # Modify dirs in-place to skip hidden directories starting with '@'
        dirnames[:] = [d for d in dirnames if not d.startswith('@')]

        for filename in filenames:
            if filename.endswith(".jpg"):
                # Full path of the current file
                full_path = os.path.join(dirpath, filename)
                # Split the filename to avoid changing the file extension
                base, extension = os.path.splitext(filename)
                # Replace colons and dots as specified
                new_base = base[:10].replace(':', '-') + ' ' + base[11:].replace(':', '.')
                new_filename = new_base + extension
                # Full path of the new file
                new_full_path = os.path.join(dirpath, new_filename)

                if (full_path == new_full_path):
                    logger.info(f"Skipping '{full_path}'")
                    continue

                # Rename the file
                os.rename(full_path, new_full_path)
                logger.info(f"Renamed '{full_path}' to '{new_full_path}'")

# Specify the root directory containing the files
root_directory_path = '/volume2/Media/My Photos'
rename_files(root_directory_path)
