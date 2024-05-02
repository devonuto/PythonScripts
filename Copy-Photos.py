import os
import shutil
from pathlib import Path

def sync_images(src_dir, dst_dir):
    src_dir = Path(src_dir)
    dst_dir = Path(dst_dir)

    # Iterate over all files in the source directory
    for src_path in src_dir.rglob('*'):
        if src_path.is_file() and src_path.suffix.lower() in ['.jpg', '.jpeg', '.png', '.gif', '.bmp']:
            # Determine the relative path to the source file
            rel_path = src_path.relative_to(src_dir)
            # Determine the destination path
            dst_path = dst_dir / rel_path
            
            # Check if this file already exists at the destination
            if not dst_path.exists():
                # Create the directory if it does not exist
                dst_path.parent.mkdir(parents=True, exist_ok=True)
                # Copy the file to the destination
                shutil.copy2(src_path, dst_path)
                print(f"Copied {src_path} to {dst_path}")
            else:
                print(f"File {src_path} already exists at {dst_path}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Usage: python sync_script.py <source_directory> <destination_directory>")
        sys.exit(1)

    source_directory = sys.argv[1]
    destination_directory = sys.argv[2]

    # Check if directories exist
    if not os.path.exists(source_directory):
        print(f"Error: Source directory {source_directory} does not exist.")
        sys.exit(1)
    if not os.path.exists(destination_directory):
        print(f"Error: Destination directory {destination_directory} does not exist.")
        sys.exit(1)

    # Call the sync function
    sync_images(source_directory, destination_directory)
