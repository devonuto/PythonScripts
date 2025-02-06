import os
import argparse

def log_file(file_path, root, output_file):
    """Log the file path in Markdown format."""
    # Get relative file_path to the initial root
    relative_path = os.path.relpath(file_path, root)
    # Add the filename to a filelist.txt file in the specified root
    with open(output_file, 'a') as f:
        f.write(f"{relative_path}\n")

def find_and_log_files(root_path):
    """Find and log all Markdown files in the given directory."""
    output_file = os.path.join(root_path, 'filelist.txt')
    for root, _, files in os.walk(root_path):
        for file in files:
            if file.endswith('.md'):
                file_path = os.path.join(root, file)
                log_file(file_path, root_path, output_file)

def main():
    parser = argparse.ArgumentParser(description='Create a Markdown filelist.')
    parser.add_argument('path', type=str, help='Path to the directory to search for files')
    args = parser.parse_args()

    find_and_log_files(args.path)

if __name__ == "__main__":
    main()
