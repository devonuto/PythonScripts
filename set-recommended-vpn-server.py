import requests
import subprocess
import re
import time
import sys
import json
import os
from datetime import datetime

# Set up logging
from logger_config import setup_custom_logger
logger = setup_custom_logger('Set-Recommended-VPN-Server')

# Function to fetch the recommended servers
def get_recommended_servers():
    url = 'https://nordvpn.com/wp-admin/admin-ajax.php?action=servers_recommendations'
    logger.info("Fetching recommended servers from NordVPN")
    response = requests.get(url)
    response.raise_for_status()
    data = response.json()
    logger.info("Fetched recommended servers successfully")
    return [server['hostname'].replace('.', '_') for server in data]

# Function to execute a shell command and return its output
def execute_command(command):
    logger.debug(f"Executing command: {command}")
    result = subprocess.run(command, shell=True, text=True, capture_output=True)
    
    if result.stderr:
        logger.error(f"Error executing command: {result.stderr.strip()}")
        sys.exit(1)
    
    logger.debug(f"Command executed successfully: {command}")
    return result.stdout.strip()

# Function to get the list of configured VPNs on the server
def get_configured_vpns():
    command = "grep -E '^conf_name=' /usr/syno/etc/synovpnclient/{l2tp,openvpn,pptp}/*client.conf 2>/dev/null"
    logger.info("Fetching configured VPNs from NAS")
    config = execute_command(command)
    
    config_split = config.split('\n')

    vpns = []
    for line in config_split:
        match_name = re.match(r"^.*conf_name=(.*)$", line)
        if match_name:
            vpn_name = match_name.group(1)
            vpns.append(vpn_name)
    
    return vpns

# Function to connect to a VPN
def connect_to_vpn(vpn_name):
    # Create reconnect command file
    execute_command(f"(echo conf_name={vpn_name} && echo proto=openvpn) > /usr/syno/etc/synovpnclient/vpnc_connecting")

    # Give root file permissions
    execute_command("chown devonuto:root /usr/syno/etc/synovpnclient/vpnc_connecting")

    # Call reconnection
    execute_command(f"/usr/syno/bin/synovpnc reconnect --protocol=openvpn --name={vpn_name} --keepfile")

    time.sleep(10)

    # Verify connection
    connection_status = execute_command("/usr/syno/bin/synovpnc get_conn").split('\n')

    if not any("Uptime" in status for status in connection_status):
        msg = f"Failed to establish VPN connection: {connection_status}"
        logger.error(msg)
        sys.exit(1)

def main():
    try:
        configured_vpns = get_configured_vpns()
        if not configured_vpns:
            logger.warning("No VPNs configured on NAS.")
            return

        # Get recommended servers
        recommended_servers = get_recommended_servers()

        # Normalize server names to match the format of configured VPNs
        normalized_recommended_servers = [server.replace('.', '_') for server in recommended_servers]

        track_server_usage(normalized_recommended_servers)

        # Find the highest recommended server that is configured
        for server in normalized_recommended_servers:            
            for vpn_name in configured_vpns:
                # Check if the server is configured
                if re.search(server, vpn_name, re.IGNORECASE):
                    logger.info(f"Connecting to recommended server: {server}")
                    connect_to_vpn(vpn_name)
                    logger.info(f"Successfully connected to {server}")
                    return
            
            # Log warning if server is not configured
            logger.warning(f"{server} is not configured on the NAS")

        logger.warning("No recommended servers are configured on the NAS.")
    except Exception as e:
        logger.error(f"An uncaught error occurred: {e}")
        sys.exit(1)

import os
import json
from datetime import datetime

def track_server_usage(recommended_servers):
    # Return if no recommended servers are provided
    if not recommended_servers:
        return
    
    # Define the path for the JSON file where server counts are stored
    file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'vpn-recommended-servers.json')
    
    # Define the minimum date
    min_date = "2000-01-01T00:00:00"

    # Load existing server usage data from the file if it exists
    if os.path.exists(file_path):
        with open(file_path, 'r') as file:
            server_usage = json.load(file)
            # Ensure each server has a valid last recommended date
            for server in server_usage:
                if 'last recommended' not in server_usage[server] or not server_usage[server]['last recommended']:
                    server_usage[server]['last recommended'] = min_date
    else:
        server_usage = {}
    
    # Get the current date in ISO format
    current_date = datetime.now().isoformat()
    
    # Update the count and last recommended date for each recommended server
    for server in recommended_servers:
        if server in server_usage:
            server_usage[server]['count'] += 1
        else:
            server_usage[server] = {'count': 1}
        server_usage[server]['last recommended'] = current_date

    # Sort the server_usage dictionary by count in descending order
    sorted_server_usage = {k: v for k, v in sorted(server_usage.items(), key=lambda item: item[1]['count'], reverse=True)}

    # Save the updated and sorted server usage data back to the file
    with open(file_path, 'w') as file:
        json.dump(sorted_server_usage, file, indent=4)


if __name__ == "__main__":
    main()
