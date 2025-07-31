import winreg
import os
import datetime
import csv

def get_installed_software():
    """
    Retrieves a list of installed software by querying the Windows Registry.

    It checks the standard 32-bit and 64-bit Uninstall registry keys for
    both the local machine and the current user.

    Returns:
        A list of dictionaries, where each dictionary represents an
        installed application and contains details like name, version,
        publisher, and installation path.
    """
    software_list = []
    # Registry keys to check for installed software information.
    # This covers 64-bit and 32-bit applications for the local machine and current user.
    registry_paths = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    ]

    for hkey, path in registry_paths:
        try:
            # Open the main registry key
            with winreg.OpenKey(hkey, path) as reg_key:
                # Enumerate over the subkeys, each representing an installed program
                for i in range(winreg.QueryInfoKey(reg_key)[0]):
                    try:
                        subkey_name = winreg.EnumKey(reg_key, i)
                        with winreg.OpenKey(reg_key, subkey_name) as sub_key:
                            app_info = {}
                            try:
                                # Attempt to read the DisplayName value
                                app_info['DisplayName'] = winreg.QueryValueEx(sub_key, "DisplayName")[0]
                            except OSError:
                                # If DisplayName is not found, skip this entry as it's likely not a standard application entry.
                                continue

                            # Get other optional details if they exist
                            try:
                                app_info['DisplayVersion'] = winreg.QueryValueEx(sub_key, "DisplayVersion")[0]
                            except OSError:
                                app_info['DisplayVersion'] = 'N/A'
                            try:
                                app_info['Publisher'] = winreg.QueryValueEx(sub_key, "Publisher")[0]
                            except OSError:
                                app_info['Publisher'] = 'N/A'
                            try:
                                app_info['InstallDate'] = winreg.QueryValueEx(sub_key, "InstallDate")[0]
                            except OSError:
                                app_info['InstallDate'] = 'N/A'
                            try:
                                app_info['InstallLocation'] = winreg.QueryValueEx(sub_key, "InstallLocation")[0]
                            except OSError:
                                app_info['InstallLocation'] = '' # Use empty string if not found

                            # Avoid adding duplicates by checking the display name
                            if app_info.get('DisplayName') and not any(d.get('DisplayName') == app_info['DisplayName'] for d in software_list):
                                software_list.append(app_info)
                    except OSError:
                        # Handle cases where a subkey cannot be opened or read
                        continue
        except FileNotFoundError:
            # This can happen if a registry path doesn't exist (e.g., on a 32-bit system)
            continue
            
    return software_list

def get_executable_timestamps(install_location):
    """
    Finds the primary executable in an installation directory and gets its timestamps.

    Args:
        install_location (str): The path to the application's installation directory.

    Returns:
        A tuple containing the last access time, last modification time, and creation time.
        Returns ('N/A', 'N/A', 'N/A') if the path is invalid or no executable is found.
    """
    if not install_location or not os.path.isdir(install_location):
        return 'N/A', 'N/A', 'N/A'

    executables = []
    try:
        for filename in os.listdir(install_location):
            if filename.lower().endswith(".exe"):
                # Get full path and size of the executable
                filepath = os.path.join(install_location, filename)
                try:
                    size = os.path.getsize(filepath)
                    executables.append((filepath, size))
                except OSError:
                    continue
    except OSError:
        return 'N/A', 'N/A', 'N/A'

    if not executables:
        return 'N/A', 'N/A', 'N/A'

    # Assume the largest executable is the main application file
    main_executable = max(executables, key=lambda item: item[1])[0]

    try:
        # Get file stats
        stats = os.stat(main_executable)
        last_access_time = datetime.datetime.fromtimestamp(stats.st_atime).strftime('%Y-%m-%d %H:%M:%S')
        last_modified_time = datetime.datetime.fromtimestamp(stats.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
        creation_time = datetime.datetime.fromtimestamp(stats.st_ctime).strftime('%Y-%m-%d %H:%M:%S')
        return last_access_time, last_modified_time, creation_time
    except OSError:
        return 'N/A', 'N/A', 'N/A'

if __name__ == "__main__":
    installed_apps = get_installed_software()
    
    # Sort the list alphabetically by display name
    installed_apps.sort(key=lambda x: x.get('DisplayName', ''))

    # Define the output filename
    output_filename = 'installed_software.csv'

    # Define the header for the CSV file
    header = [
        'Application Name', 
        'Version', 
        'Publisher', 
        'Last Accessed (Unreliable)', 
        'Last Modified', 
        'Install Date'
    ]

    try:
        # Write the data to a CSV file
        with open(output_filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            
            # Write the header row
            writer.writerow(header)
            
            # Write the data for each application
            for app in installed_apps:
                access_time, modified_time, _ = get_executable_timestamps(app.get('InstallLocation'))
                row = [
                    app.get('DisplayName', 'N/A'),
                    app.get('DisplayVersion', 'N/A'),
                    app.get('Publisher', 'N/A'),
                    access_time,
                    modified_time,
                    app.get('InstallDate', 'N/A')
                ]
                writer.writerow(row)
        
        print(f"Successfully saved the list of installed software to '{output_filename}'")

    except IOError:
        print(f"Error: Could not write to file '{output_filename}'. Please check permissions.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
