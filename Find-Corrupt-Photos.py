import os
from PIL import Image
import time  # Import the time module for the sleep function
import shutil # for moving files

def is_corrupted(filepath, max_attempts=3):
    attempt = 0
    while attempt < max_attempts:
        try:
            # Verify the image
            with Image.open(filepath) as img:
                img.verify()  # Verify the integrity
            # Reopen the image for further operations
            with Image.open(filepath) as img:
                img.transpose(Image.FLIP_LEFT_RIGHT)  # Simple operation to force image reading
            return False  # If no exception, image is OK
        except Exception as e:
            print(f"Attempt {attempt+1}: Error checking {filepath}: {str(e)}")
            attempt += 1
            time.sleep(1)  # Wait a bit before retrying
    return True  # If all attempts fail, image is corrupted

# Resolve the full path of the current directory
directory = os.path.abspath("./")
corrupted_dir = os.path.join(directory, "corrupted")

# Ensure the corrupted directory exists
if not os.path.exists(corrupted_dir):
    os.makedirs(corrupted_dir)

# Path to the output file
output_file = directory + "\\corrupted_photos.txt"

# Read existing corrupted file entries to prevent duplicates
existing_entries = set()
if os.path.exists(output_file):
    with open(output_file, 'r') as file:
        existing_entries = {line.strip() for line in file}

# Open the output file in append mode only if needed
file = open(output_file, 'a') if existing_entries else open(output_file, 'w')

# Walk through the directory and subdirectories
total_files = 0
corrupted_files = 0
# Open the output file properly once
with open(output_file, 'a' if existing_entries else 'w') as file:
    for root, dirs, files in os.walk(directory):
          # Modify dirs in-place to skip the corrupted directory 
        if corrupted_dir in dirs:
            dirs.remove(corrupted_dir)  # This prevents os.walk from walking into corrupted directory

        for filename in files:
            if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.tiff', '.bmp', '.gif')):
                total_files += 1
                file_path = os.path.join(root, filename)
                corrupted_file_path = os.path.join(corrupted_dir, filename)
                if file_path not in existing_entries:       
                    if is_corrupted(file_path):                    
                        corrupted_files += 1
                        try:
                            existing_entries.add(file_path)                            
                            shutil.move(file_path, corrupted_file_path)  # Move the corrupted file
                            print(f"Moved: {file_path} to {corrupted_file_path}")
                            file.write(f"{corrupted_file_path}\n")
                            file.flush()                            
                        except Exception as e:
                            print(f"Failed to write to file: {e}")
                    else:
                        print(f"File checked and OK: {file_path}")
                elif  file_path != corrupted_file_path:
                    shutil.move(file_path, corrupted_file_path)  # Move the corrupted file
                    print(f"Moved: {file_path} to {corrupted_file_path}")
                else:
                    print(f"File already checked: {file_path}")
                
# Close the file
file.close()

# Output the total number of image files and corrupted files
print(f"Total image files checked: {total_files}")
print(f"Total corrupted files found: {corrupted_files}")

print(f"Analysis complete. Corrupted files are listed in {output_file}.")
