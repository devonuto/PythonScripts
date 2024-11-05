import os
import sys
import shutil
import datetime
from pathlib import Path
from logger_config import setup_custom_logger
from shared_methods import log_error, log_info

logger = setup_custom_logger('Move-Videos')

def find_and_move_videos(source_path, destination_root):
    video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.m4v'}

    for root, _, files in os.walk(source_path, followlinks=True):
        for file in files:
            file_path = Path(root) / file

            if file_path.suffix.lower() in video_extensions:
                try:
                    creation_time = datetime.datetime.fromtimestamp(file_path.stat().st_ctime)
                    year_folder = creation_time.strftime('%Y')
                except Exception as e:
                    log_error(logger, f"Error retrieving creation date for {file_path}", e)
                    year_folder = 'Unknown'

                destination_path = Path(destination_root) / year_folder
                destination_path.mkdir(parents=True, exist_ok=True)

                try:
                    shutil.move(str(file_path), str(destination_path / file))
                    log_info(logger, f'Moved: {file_path} to {destination_path}')
                except Exception as e:
                    log_error(logger, f"Error moving {file_path}", e)

if __name__ == "__main__":
    log_info(logger, f"Current working directory: {os.getcwd()}")
    if len(sys.argv) < 3:
        log_error(logger, "No directory path provided.")
        sys.exit(1)
    start_directory = sys.argv[1]
    if not os.path.isdir(start_directory):
        log_error(logger, f"\"{start_directory}\" is not a valid directory.")
        sys.exit(1)        
    destination_directory = sys.argv[2]
    if not os.path.isdir(destination_directory):
        log_error(logger, f"\"{destination_directory}\" is not a valid directory.")
        sys.exit(1)    
    find_and_move_videos(start_directory, destination_directory)

    