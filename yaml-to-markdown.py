import os
import subprocess
import argparse

def run_conversion(file_path, output_dir):
    """Run the yaml-to-markdown command for a given file."""
    file_name = os.path.splitext(os.path.basename(file_path))[0]
    output_file = os.path.join(output_dir, f"{file_name}.md")

    cmd = ["C:\\Users\\devon\\AppData\\Local\\Packages\\PythonSoftwareFoundation.Python.3.11_qbz5n2kfra8p0\\LocalCache\\local-packages\\Python311\\Scripts\\yaml-to-markdown.exe", '-o', output_file, '-y', file_path]
    
    try:
        subprocess.run(cmd, check=True)
        print(f"Converted {file_path} to {output_file}")
        os.remove(file_path)
    except subprocess.CalledProcessError as e:
        print(f"Error converting {file_path}: {e}")

def find_and_convert_files(path):
    """Find and convert all YAML and JSON files in the given directory."""
    for root, _, files in os.walk(path):
        for file in files:
            if file.endswith(('.yml', '.yaml')):
                file_path = os.path.join(root, file)
                run_conversion(file_path, root)

def main():
    parser = argparse.ArgumentParser(description='Convert JSON or YAML to Markdown.')
    parser.add_argument('path', type=str, help='Path to the directory to search for files')
    args = parser.parse_args()

    find_and_convert_files(args.path)

if __name__ == "__main__":
    main()
