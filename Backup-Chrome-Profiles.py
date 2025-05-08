import os
import subprocess
import pathlib

def backup_chrome_profiles():
    """
    Backs up Google Chrome user profiles on Windows using robocopy.
    """
    try:
        # Get the Local AppData path
        local_app_data = os.getenv('LOCALAPPDATA')
        if not local_app_data:
            print("Error: LOCALAPPDATA environment variable not found.")
            return

        # Define the source path for Chrome profiles
        chrome_profiles_path = pathlib.Path(local_app_data) / "Google" / "Chrome" / "User Data"

        if not chrome_profiles_path.is_dir():
            print(f"Error: Chrome profiles path not found at {chrome_profiles_path}")
            return

        # Define the backup path in the user's Documents folder
        # os.path.expanduser('~') gets the user's home directory (equivalent to $env:USERPROFILE)
        backup_root_path = pathlib.Path(os.path.expanduser('~')) / "Documents" / "Google Profiles"

        # Create the main backup directory if it doesn't exist
        # os.makedirs with exist_ok=True is similar to `New-Item -ItemType Directory` and checking if it exists
        os.makedirs(backup_root_path, exist_ok=True)
        print(f"Backup directory set to: {backup_root_path}")

        # Get all profile directories (those named 'Default' or starting with 'Profile')
        profile_dirs_to_backup = []
        for item in chrome_profiles_path.iterdir():
            if item.is_dir():
                if item.name == "Default" or item.name.startswith("Profile"):
                    profile_dirs_to_backup.append(item)

        if not profile_dirs_to_backup:
            print(f"No Chrome profiles found in {chrome_profiles_path}")
            return

        # Iterate through the profile directories and back up each one
        for profile_dir in profile_dirs_to_backup:
            source_full_path = str(profile_dir.resolve())
            destination_path = str((backup_root_path / profile_dir.name).resolve())

            print(f"\nBacking up profile from {source_full_path} to {destination_path}...")

            # Use Robocopy to copy the profile to the backup directory
            # /MIR switch mirrors a directory tree (equivalent to /E plus /PURGE).
            # /E copies subdirectories, including empty ones.
            # /PURGE deletes destination files/directories that no longer exist in the source.
            # /R:3 specifies 3 retries on failed copies.
            # /W:5 specifies a wait time of 5 seconds between retries.
            # /NJH suppresses the job header.
            # /NJS suppresses the job summary.
            # /NDL suppresses the directory logging.
            # /NFL suppresses the file logging.
            # We want some output, so we'll use fewer suppression flags than a fully silent script.
            # Using robocopy directly like this is the most straightforward way
            # to replicate the PowerShell script's backup behavior.
            try:
                # Ensure destination directory for the specific profile exists before robocopy,
                # as robocopy might have issues if the immediate parent of the target doesn't exist.
                # However, robocopy usually creates the final destination folder if it doesn't exist.
                # For safety, we can ensure the profile-specific backup folder exists.
                os.makedirs(destination_path, exist_ok=True)

                robocopy_command = [
                    "robocopy",
                    source_full_path,
                    destination_path,
                    "/MIR",  # Mirror - equivalent to /E /PURGE
                    "/R:2",  # Number of Retries on failed copies
                    "/W:5",  # Wait time between retries
                    "/NJH",  # No Job Header
                    "/NJS",  # No Job Summary
                    "/NP"    # No Progress - to avoid too much console clutter from robocopy itself
                ]
                
                # Execute the command
                # capture_output=True and text=True are for Python 3.7+
                # For broader compatibility, can use stdout=subprocess.PIPE, stderr=subprocess.PIPE
                process = subprocess.run(robocopy_command, capture_output=True, text=True, check=False)

                # Robocopy exit codes:
                # 0: No files copied. No failure. No mismatch.
                # 1: One or more files copied successfully.
                # 2: Extra files or directories were detected. No copy errors.
                # 3: Files copied, extra files detected.
                # (Codes < 8 generally indicate success or non-critical issues)
                # 8 and above indicate errors.
                if process.returncode >= 8:
                    print(f"Error during robocopy for {profile_dir.name}.")
                    print(f"Return code: {process.returncode}")
                    if process.stdout:
                        print(f"Robocopy STDOUT:\n{process.stdout}")
                    if process.stderr:
                        print(f"Robocopy STDERR:\n{process.stderr}")
                else:
                    print(f"Successfully backed up {profile_dir.name}.")
                    if process.stdout and process.returncode > 0 : # Print output if files were copied or other info
                         print(f"Robocopy output:\n{process.stdout.strip()}")


            except FileNotFoundError:
                print("Error: robocopy command not found. Ensure it is in your system's PATH.")
            except Exception as e:
                print(f"An unexpected error occurred while backing up {profile_dir.name}: {e}")

        print("\nBackup process completed.")

    except Exception as e:
        print(f"An overall error occurred: {e}")

if __name__ == "__main__":
    backup_chrome_profiles()
    # Keep the console window open until the user presses Enter, if run directly
    # input("Press Enter to exit...")
