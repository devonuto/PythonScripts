import os
import csv
import datetime
import winreg

# Note: This script requires the WMI package.
# Install it using: pip install WMI
try:
    import wmi
except ImportError:
    print("Error: The 'WMI' package is not installed.")
    print("Please install it by running: pip install WMI")
    exit()

def get_installed_software():
    """
    Retrieves a list of traditionally installed software (Win32) by querying the Windows Registry.

    It checks the standard 32-bit and 64-bit Uninstall registry keys for
    both the local machine and the current user.

    Returns:
        A list of dictionaries, where each dictionary represents an
        installed application.
    """
    software_list = []
    # Registry keys to check for installed software information.
    registry_paths = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    ]

    for hkey, path in registry_paths:
        try:
            with winreg.OpenKey(hkey, path) as reg_key:
                for i in range(winreg.QueryInfoKey(reg_key)[0]):
                    try:
                        subkey_name = winreg.EnumKey(reg_key, i)
                        with winreg.OpenKey(reg_key, subkey_name) as sub_key:
                            app_info = {}
                            try:
                                app_info['DisplayName'] = winreg.QueryValueEx(sub_key, "DisplayName")[0]
                            except OSError:
                                continue # Skip if no display name

                            # Filter out system components and updates
                            if winreg.QueryValueEx(sub_key, "SystemComponent")[0] == 1:
                                continue
                            if "ParentKeyName" in [winreg.EnumValue(sub_key, j)[0] for j in range(winreg.QueryInfoKey(sub_key)[1])]:
                                continue

                            app_info['DisplayVersion'] = winreg.QueryValueEx(sub_key, "DisplayVersion")[0] if "DisplayVersion" in [winreg.EnumValue(sub_key, j)[0] for j in range(winreg.QueryInfoKey(sub_key)[1])] else 'N/A'
                            app_info['Publisher'] = winreg.QueryValueEx(sub_key, "Publisher")[0] if "Publisher" in [winreg.EnumValue(sub_key, j)[0] for j in range(winreg.QueryInfoKey(sub_key)[1])] else 'N/A'
                            app_info['InstallDate'] = winreg.QueryValueEx(sub_key, "InstallDate")[0] if "InstallDate" in [winreg.EnumValue(sub_key, j)[0] for j in range(winreg.QueryInfoKey(sub_key)[1])] else 'N/A'
                            app_info['InstallLocation'] = winreg.QueryValueEx(sub_key, "InstallLocation")[0] if "InstallLocation" in [winreg.EnumValue(sub_key, j)[0] for j in range(winreg.QueryInfoKey(sub_key)[1])] else ''

                            if app_info.get('DisplayName') and not any(d.get('DisplayName') == app_info['DisplayName'] for d in software_list):
                                software_list.append(app_info)
                    except OSError:
                        continue
        except FileNotFoundError:
            continue
            
    return software_list

def get_store_apps():
    """
    Retrieves a list of installed Microsoft Store apps (UWP) using WMI.

    Returns:
        A list of dictionaries, where each dictionary represents an
        installed Store application.
    """
    store_apps_list = []
    try:
        c = wmi.WMI()
        # Query for installed Store applications
        for app in c.Win32_InstalledStoreProgram():
            app_info = {
                'DisplayName': app.Name,
                'DisplayVersion': app.Version if app.Version else 'N/A',
                'Publisher': app.Vendor if app.Vendor else 'N/A',
                # Store apps don't have a traditional install date or location
                'InstallDate': 'N/A',
                'InstallLocation': '' 
            }
            if app_info.get('DisplayName') and not any(d.get('DisplayName') == app_info['DisplayName'] for d in store_apps_list):
                store_apps_list.append(app_info)
    except Exception as e:
        print(f"Could not retrieve Store apps. WMI query failed: {e}")
    return store_apps_list


def get_executable_timestamps(install_location):
    """
    Finds the primary executable in an installation directory and gets its timestamps.

    Args:
        install_location (str): The path to the application's installation directory.

    Returns:
        A tuple containing the last access time, last modification time, and creation time.
    """
    if not install_location or not os.path.isdir(install_location):
        return 'N/A', 'N/A', 'N/A'

    executables = []
    try:
        for filename in os.listdir(install_location):
            if filename.lower().endswith(".exe"):
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

    main_executable = max(executables, key=lambda item: item[1])[0]

    try:
        stats = os.stat(main_executable)
        last_access_time = datetime.datetime.fromtimestamp(stats.st_atime).strftime('%Y-%m-%d %H:%M:%S')
        last_modified_time = datetime.datetime.fromtimestamp(stats.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
        creation_time = datetime.datetime.fromtimestamp(stats.st_ctime).strftime('%Y-%m-%d %H:%M:%S')
        return last_access_time, last_modified_time, creation_time
    except OSError:
        return 'N/A', 'N/A', 'N/A'

if __name__ == "__main__":
    # Get both lists of applications
    installed_apps = get_installed_software()
    store_apps = get_store_apps()
    
    # Combine the lists
    all_apps = installed_apps + store_apps
    
    # Sort the combined list alphabetically by display name
    all_apps.sort(key=lambda x: x.get('DisplayName', '').lower())

    output_filename = 'installed_software.csv'
    header = [
        'Application Name', 
        'Version', 
        'Publisher', 
        'Last Accessed (Unreliable)', 
        'Last Modified', 
        'Install Date'
    ]

    try:
        with open(output_filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(header)
            
            for app in all_apps:
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
        print(f"Found {len(installed_apps)} traditional apps and {len(store_apps)} store apps.")

    except IOError:
        print(f"Error: Could not write to file '{output_filename}'. Please check permissions.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
