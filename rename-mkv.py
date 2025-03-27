import sys
import os
import re

from logger_config import setup_custom_logger
from shared_methods import (log_info, log_error)

logger = setup_custom_logger('rename-mkv')

def rename_mkv_if_needed(original_full_path):
    """
    Renames an MKV file if its name ends with '(\d+).mkv' and the target name doesn't exist.

    Args:
        original_full_path (str): The full path to the MKV file created by MKVToolNix.
    """
    log_info(logger, f"Processing file: '{original_full_path}'")

    if not os.path.isfile(original_full_path):
        log_error(logger, f"Input path is not a valid file: '{original_full_path}'")
        return  # Exit function if the file doesn't exist

    # Define the pattern to match: e.g., (1).mkv, (12).mkv at the end of the filename
    # \(\d+\)  - Matches one or more digits inside literal parentheses
    # \.mkv$   - Matches '.mkv' at the very end of the string ($)
    # re.IGNORECASE - Makes the '.mkv' match case-insensitive (.MKV, .mKv etc.)
    pattern = r"\s\(\d+\)\.mkv$"

    # Extract the base filename from the full path
    original_basename = os.path.basename(original_full_path)

    # Search for the pattern at the end of the base filename
    match = re.search(pattern, original_basename, re.IGNORECASE)

    if match:
        matched_part = match.group(0)  # This is the ' (\d+).mkv' part
        log_info(logger,
            f"Filename '{original_basename}' matches pattern '{matched_part}'."
        )

        # Construct the potential new base filename by removing the matched part
        # We find the start index of the match and take the substring before it, then add '.mkv'
        # This is slightly more robust than simple replacement if the pattern appeared elsewhere.
        # Or simply use re.sub which is designed for this:
        new_basename = re.sub(pattern, ".mkv", original_basename, flags=re.IGNORECASE)

        # Get the directory path
        directory_path = os.path.dirname(original_full_path)

        # Construct the full path for the potential new filename
        new_full_path = os.path.join(directory_path, new_basename)

        log_info(logger, f"Potential new filename: '{new_full_path}'")

        # --- CRITICAL CHECK: Ensure we are not renaming to the *same* filename ---
        # This can happen if the only difference was case, e.g. (1).MKV -> .mkv
        if os.path.normcase(original_full_path) == os.path.normcase(new_full_path):
            log_info(logger, 
                "Original and target filenames are effectively the same (ignoring case). No rename needed."
            )
            return

        # Check if the target file already exists
        if not os.path.exists(new_full_path):
            try:
                log_info(logger, 
                    f"Target '{new_full_path}' does not exist. Attempting rename..."
                )
                os.rename(original_full_path, new_full_path)
                log_info(logger, 
                    f"Successfully renamed '{original_basename}' to '{new_basename}'"
                )
            except OSError as e:
                log_error(logger,
                    f"Error renaming file from '{original_full_path}' to '{new_full_path}': {e}"
                )
            except Exception as e:
                log_error(logger,f"An unexpected error occurred during renaming: {e}")
        else:
            log_info(logger, 
                f"Target file '{new_full_path}' already exists. No rename performed."
            )
    else:
        log_info(logger, 
            f"Filename '{original_basename}' does not end with the pattern '(\\d+).mkv'. No action needed."
        )


# --- Main execution block ---
if __name__ == "__main__":
    log_info(logger, "Script execution started.")
    log_info(logger, f"Arguments received: {sys.argv}")

    # Expecting exactly one argument from MKVToolNix (the script name itself is sys.argv[0])
    if len(sys.argv) != 2:
        log_error(logger,
            f"Incorrect number of arguments. Expected 1 (the destination file path), but received {len(sys.argv) - 1}."
        )
        log_error(logger,
            'Usage within MKVToolNix: execute python C:\\path\\to\\your\\script.py "<MTX_DESTINATION_FILE_NAME>"'
        )
        sys.exit(1)  # Exit with an error code

    # Get the filename from the command line argument passed by MKVToolNix
    mkv_file_path = sys.argv[1]

    rename_mkv_if_needed(mkv_file_path)

    log_info(logger, "Script execution finished.")
    sys.exit(0)  # Exit successfully
