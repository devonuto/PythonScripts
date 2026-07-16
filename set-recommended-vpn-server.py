# ==============================================================================
# NordVPN recommended-server switcher for Synology DSM
# ==============================================================================
# Connects the NAS to NordVPN's currently recommended server, and keeps a pool
# of OpenVPN profiles synced to the most-frequently-recommended servers by
# cloning an existing, working profile.
#
# SETTING THIS UP ON A NEW MACHINE (Synology NAS, DSM 7):
#
# 1. Import ONE working NordVPN OpenVPN profile through the DSM UI first.
#    This is the non-negotiable prerequisite: the script cannot create a
#    profile from scratch. It clones this "template" profile, inheriting its
#    CA certificate and -- critically -- its user=/pass= entries verbatim.
#    DSM stores pass= in an obfuscated form that only the DSM UI can write,
#    so there is no way to supply credentials via this script or config file.
#      a. Get your NordVPN *service credentials* (NOT your account login):
#         https://my.nordaccount.com -> NordVPN -> Manual setup -> Service credentials
#      b. Download a UDP .ovpn file for any server from NordVPN's site.
#      c. DSM: Control Panel -> Network -> Network Interface -> Create ->
#         Create VPN profile -> OpenVPN (via importing a .ovpn file), enter
#         the service credentials from (a).
#      d. Test-connect it once from the DSM UI so you know it works.
#    The profile name must contain "nordvpn" (it will if imported from a
#    standard .ovpn, e.g. au731_nordvpn_com_udp).
#
# 2. Put this folder on a NAS share, e.g. /volume2/Media/Python Scripts.
#    Required alongside this script: logger_config.py, local.config
#    (copy local.config.example and review it; keep dry_run=true for the
#    first run or two). vpn-recommended-servers.json builds up over time --
#    without it, only today's #1 recommendation is used for profile sync.
#
# 3. Make sure python3 with the "requests" package is available on the NAS
#    (e.g. install Python from Package Center, then:  python3 -m pip install requests).
#
# 4. Schedule it as root: DSM Control Panel -> Task Scheduler -> Create ->
#    Scheduled Task -> User-defined script, user "root", every ~2 hours:
#      cd "/volume2/Media/Python Scripts" && python3 set-recommended-vpn-server.py
#    Root is required: the script writes /usr/syno/etc/synovpnclient/* and
#    calls /usr/syno/bin/synovpnc.
#
# IF NORDVPN SERVICE CREDENTIALS ARE EVER REGENERATED: every profile breaks
# at once (AUTH_FAILED). Fix by re-doing step 1 (re-import/edit one profile
# in the DSM UI with the new credentials); clones inherit from it on the
# next sync.
#
# DEBUGGING NOTES (hard-won):
# - OpenVPN output does NOT go to /var/log/messages; each profile logs to
#   /var/log/<server>_NordVPN.log (the log-append line in its client_ file).
#   synovpnc itself only logs "CreateOVPNConnection(...) failed" to messages.
# - synovpnc has no "disconnect" command; teardown is "kill_client".
# - Dialing requires /usr/syno/etc/synovpnclient/vpnc_connecting to contain
#   conf_id=/conf_name=/proto= before calling "synovpnc reconnect".
# - Cloned configs must have verify-x509-name rewritten to the new server's
#   hostname or TLS fails with VERIFY X509NAME ERROR.
# ==============================================================================

import requests
import subprocess
import re
import time
import sys
import json
import os
import shutil
import configparser
from datetime import datetime

# Set up logging
from logger_config import setup_custom_logger
logger = setup_custom_logger('Set-Recommended-VPN-Server')

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOCAL_CONFIG_PATH = os.path.join(SCRIPT_DIR, 'local.config')
USAGE_FILE_PATH = os.path.join(SCRIPT_DIR, 'vpn-recommended-servers.json')

# Synology DSM OpenVPN profile store
SYNO_OPENVPN_DIR = '/usr/syno/etc/synovpnclient/openvpn'
OVPNCLIENT_CONF = SYNO_OPENVPN_DIR + '/ovpnclient.conf'


def load_local_config():
    settings = {
        'max_profiles': None,
        'sync_profiles': False,  # profile add/remove stays off until local.config exists
        'dry_run': False,
    }

    if not os.path.exists(LOCAL_CONFIG_PATH):
        logger.info("No local.config found; profile sync disabled (connect-only mode)")
        return settings

    parser = configparser.ConfigParser()
    parser.read(LOCAL_CONFIG_PATH)

    max_profiles = parser.get('settings', 'max_profiles', fallback='').strip()
    if max_profiles.isdigit() and int(max_profiles) > 0:
        settings['max_profiles'] = int(max_profiles)

    settings['sync_profiles'] = parser.getboolean('settings', 'sync_profiles', fallback=True)
    settings['dry_run'] = parser.getboolean('settings', 'dry_run', fallback=False)
    return settings


# Function to fetch the recommended servers
def get_recommended_servers():
    url = 'https://api.nordvpn.com/v1/servers/recommendations'
    logger.info("Fetching recommended servers from NordVPN")
    response = requests.get(url)
    response.raise_for_status()
    data = response.json()
    logger.info("Fetched recommended servers successfully")
    return [{'hostname': server['hostname'], 'ip': server.get('station')} for server in data]


def normalize_server_name(hostname):
    return hostname.replace('.', '_')


def denormalize_server_name(normalized):
    return normalized.replace('_', '.')


# Function to execute a shell command and return its output
def execute_command(command, check=True):
    logger.debug(f"Executing command: {command}")
    result = subprocess.run(command, shell=True, text=True, capture_output=True)

    if check and result.returncode != 0:
        error_message = result.stderr.strip() or result.stdout.strip() or "Unknown error"
        logger.error(f"Error executing command: {error_message}")
        sys.exit(1)

    logger.debug(f"Command executed successfully: {command}")
    return result.stdout.strip()


# Function to get the list of configured VPNs on the server
def get_configured_vpns():
    logger.info("Fetching configured VPNs from NAS")
    vpns = [profile['name'] for profile in parse_openvpn_profiles()]

    for directory in ('l2tp', 'openvpn', 'pptp'):
        dir_path = f"/usr/syno/etc/synovpnclient/{directory}"
        if not os.path.isdir(dir_path):
            continue

        for filename in os.listdir(dir_path):
            if not filename.endswith('client.conf'):
                continue

            full_path = os.path.join(dir_path, filename)
            try:
                with open(full_path, 'r') as file:
                    for line in file:
                        if line.startswith('conf_name='):
                            vpn_name = line.partition('=')[2].strip()
                            if vpn_name and vpn_name not in vpns:
                                vpns.append(vpn_name)
                            break
            except Exception as e:
                logger.warning(f"Unable to read VPN config file {full_path}: {e}")

    return vpns


def check_external_connectivity(host='1.1.1.1', timeout_seconds=5):
    if os.name == 'nt':
        ping_command = f"ping -n 1 -w {timeout_seconds * 1000} {host}"
    else:
        ping_command = f"ping -c 1 -W {timeout_seconds} {host}"

    logger.info(f"Checking external connectivity to {host}")
    result = subprocess.run(ping_command, shell=True, text=True, capture_output=True, timeout=timeout_seconds + 10)

    if result.returncode != 0:
        logger.warning(f"External connectivity check failed for {host}: {result.stderr.strip() or result.stdout.strip()}")
        return False

    return True


def get_current_vpn_connection():
    connection_status = execute_command("/usr/syno/bin/synovpnc get_conn", check=False)
    logger.debug(f"Current VPN connection status:\n{connection_status}")

    if not connection_status:
        return None

    for line in connection_status.splitlines():
        lowered = line.lower()
        if 'conf_name=' in lowered:
            return line.split('=', 1)[1].strip()
        if 'name=' in lowered:
            return line.split('=', 1)[1].strip()

    fallback = re.search(r'([a-z0-9_]+_nordvpn_com(?:_(?:udp|tcp|vpn))?)', connection_status, re.IGNORECASE)
    return fallback.group(1).strip() if fallback else None


def disconnect_vpn(vpn_name=None):
    if vpn_name:
        logger.warning(f"Forcing disconnect for VPN {vpn_name}")
    else:
        logger.warning("Forcing disconnect of current VPN connection")

    # synovpnc has no "disconnect" subcommand; kill_client tears down the
    # currently active connection regardless of profile.
    result = subprocess.run("/usr/syno/bin/synovpnc kill_client", shell=True, text=True, capture_output=True)
    if result.returncode != 0:
        logger.warning(f"kill_client failed: {result.stderr.strip() or result.stdout.strip()}")

    # Give the system a moment to tear down the interface.
    time.sleep(8)


def verify_vpn_connection(vpn_name=None):
    connection_status = execute_command("/usr/syno/bin/synovpnc get_conn", check=False)
    if vpn_name and vpn_name not in connection_status:
        logger.warning(f"Expected VPN {vpn_name} not active. Current status:\n{connection_status}")
        return False
    return "Uptime" in connection_status


def get_openvpn_profile_id(vpn_name):
    for profile in parse_openvpn_profiles():
        if profile['name'] == vpn_name:
            return profile['id']
    return None


def dial_vpn(vpn_name, profile_id):
    # Reconnect resolves the profile via conf_id in vpnc_connecting; conf_name
    # alone is not enough for it to find the client_<id> config to dial.
    execute_command(
        f"(echo conf_id={profile_id} && echo conf_name={vpn_name} && echo proto=openvpn)"
        " > /usr/syno/etc/synovpnclient/vpnc_connecting"
    )
    execute_command("chown devonuto:root /usr/syno/etc/synovpnclient/vpnc_connecting")
    execute_command(f"/usr/syno/bin/synovpnc reconnect --protocol=openvpn --name={vpn_name} --keepfile")
    time.sleep(12)


# Function to connect to a VPN
def connect_to_vpn(vpn_name):
    current_vpn = get_current_vpn_connection()
    if current_vpn == vpn_name:
        logger.info(f"VPN {vpn_name} is already active")
        return

    profile_id = get_openvpn_profile_id(vpn_name)
    if not profile_id:
        logger.error(f"No OpenVPN profile id found for {vpn_name} in {OVPNCLIENT_CONF}")
        sys.exit(1)

    if current_vpn and current_vpn != vpn_name:
        logger.info(f"Disconnecting currently active VPN {current_vpn} before connecting to {vpn_name}")
        disconnect_vpn(current_vpn)

    dial_vpn(vpn_name, profile_id)

    # Verify connection
    if not verify_vpn_connection(vpn_name):
        logger.warning(f"VPN {vpn_name} did not become active after first reconnect")
        disconnect_vpn(vpn_name)
        dial_vpn(vpn_name, profile_id)

        if not verify_vpn_connection(vpn_name):
            msg = f"VPN connection did not recover after reconnect for {vpn_name}"
            logger.error(msg)
            sys.exit(1)

    if not check_external_connectivity():
        logger.warning(f"External connectivity check failed for {vpn_name}; forcing VPN reset")
        disconnect_vpn(vpn_name)
        dial_vpn(vpn_name, profile_id)

        if not verify_vpn_connection(vpn_name) or not check_external_connectivity():
            msg = f"VPN connection did not recover after reconnect for {vpn_name}"
            logger.error(msg)
            sys.exit(1)


# --- Synology OpenVPN profile management -------------------------------------
# DSM stores one section per profile in ovpnclient.conf:
#   [o1234567890]
#   conf_name=au747_nordvpn_com
#   user=...
#   pass=...
# plus a client_o1234567890 OpenVPN config file (and sometimes ca_/key_ files).
# New profiles are created by cloning an existing, working NordVPN profile and
# rewriting the "remote" host, so certificates and options carry over verbatim.

def parse_openvpn_profiles():
    if not os.path.exists(OVPNCLIENT_CONF):
        return []

    with open(OVPNCLIENT_CONF, 'r') as file:
        content = file.read()

    profiles = []
    for match in re.finditer(r'(?ms)^\[([^\]]+)\].*?(?=^\[|\Z)', content):
        section = match.group(0)
        name_match = re.search(r'(?m)^conf_name=(.*)$', section)
        profiles.append({
            'id': match.group(1),
            'name': name_match.group(1).strip() if name_match else '',
            'section': section,
        })
    return profiles


def generate_conf_id(existing_ids):
    conf_id = int(time.time())
    while f'o{conf_id}' in existing_ids:
        conf_id += 1
    return f'o{conf_id}'


def clone_profile(template, server, existing_ids, dry_run):
    new_name = server['name']
    # Prefer the station IP (no DNS dependency at connect time, matches
    # NordVPN's own .ovpn files); fall back to the hostname
    remote_host = server.get('ip') or server['hostname']
    if dry_run:
        logger.info(f"[DRY RUN] Would add profile {new_name} (remote {remote_host}, cloned from {template['name']})")
        return

    new_id = generate_conf_id(existing_ids)
    template_stat = os.stat(OVPNCLIENT_CONF)

    # Copy every file belonging to the template profile (client_oXXX, ca_oXXX, ...)
    copied_any = False
    for filename in os.listdir(SYNO_OPENVPN_DIR):
        if template['id'] in filename:
            source = os.path.join(SYNO_OPENVPN_DIR, filename)
            target = os.path.join(SYNO_OPENVPN_DIR, filename.replace(template['id'], new_id))
            shutil.copy2(source, target)
            source_stat = os.stat(source)
            os.chown(target, source_stat.st_uid, source_stat.st_gid)
            copied_any = True

    if not copied_any:
        logger.error(f"No config files found for template profile {template['name']} ({template['id']}); cannot add {new_name}")
        return

    # Point the cloned OpenVPN config at the new server and fix internal references
    client_path = os.path.join(SYNO_OPENVPN_DIR, f'client_{new_id}')
    with open(client_path, 'r') as file:
        client_config = file.read()
    client_config = client_config.replace(template['id'], new_id)
    client_config = re.sub(r'(?m)^(remote\s+)\S+(.*)$', rf'\g<1>{remote_host}\g<2>', client_config)
    # The template pins its own hostname for certificate verification; without
    # this rewrite every clone fails TLS with VERIFY X509NAME ERROR.
    client_config = re.sub(r'(?m)^(verify-x509-name\s+CN=)\S+$', rf'\g<1>{server["hostname"]}', client_config)
    server_short_name = server['hostname'].split('.')[0]
    client_config = re.sub(r'(?m)^(log-append\s+/var/log/)\S+$', rf'\g<1>{server_short_name}_NordVPN.log', client_config)
    with open(client_path, 'w') as file:
        file.write(client_config)

    # Build the new ovpnclient.conf section from the template's. user/pass are
    # inherited verbatim: DSM stores pass= obfuscated, so writing plaintext
    # service credentials there fails auth (AUTH_FAILED).
    new_section = template['section'].replace(f"[{template['id']}]", f"[{new_id}]")
    new_section = re.sub(r'(?m)^conf_name=.*$', f'conf_name={new_name}', new_section)
    new_section = re.sub(r'(?m)^remote=.*$', f'remote={remote_host}', new_section)
    if not new_section.endswith('\n'):
        new_section += '\n'

    with open(OVPNCLIENT_CONF, 'a') as file:
        file.write(new_section)
    os.chown(OVPNCLIENT_CONF, template_stat.st_uid, template_stat.st_gid)

    existing_ids.add(new_id)
    logger.info(f"Added profile {new_name} ({new_id}, remote {remote_host}), cloned from {template['name']}")


def remove_profile(profile, dry_run):
    if dry_run:
        logger.info(f"[DRY RUN] Would remove profile {profile['name']} ({profile['id']})")
        return

    with open(OVPNCLIENT_CONF, 'r') as file:
        content = file.read()
    conf_stat = os.stat(OVPNCLIENT_CONF)

    content = content.replace(profile['section'], '')
    with open(OVPNCLIENT_CONF, 'w') as file:
        file.write(content)
    os.chown(OVPNCLIENT_CONF, conf_stat.st_uid, conf_stat.st_gid)

    for filename in os.listdir(SYNO_OPENVPN_DIR):
        if profile['id'] in filename:
            os.remove(os.path.join(SYNO_OPENVPN_DIR, filename))

    logger.info(f"Removed profile {profile['name']} ({profile['id']})")


def build_desired_servers(recommended_servers, max_profiles):
    """Top servers by all-time recommendation count, with today's #1
    recommendation always included so the connect step can use it.
    Returns dicts of {name (normalized), hostname, ip}."""
    desired = []
    if recommended_servers:
        top = recommended_servers[0]
        desired.append({
            'name': normalize_server_name(top['hostname']),
            'hostname': top['hostname'],
            'ip': top.get('ip'),
        })

    if os.path.exists(USAGE_FILE_PATH):
        with open(USAGE_FILE_PATH, 'r') as file:
            server_usage = json.load(file)
        # Once IPs have been collected, an entry without one means the server
        # is no longer in NordVPN's fleet -- don't waste a profile slot on it
        have_ip_data = any('ip' in details for details in server_usage.values())
        ranked = sorted(
            server_usage.items(),
            key=lambda item: (item[1].get('count', 0), item[1].get('last recommended', '')),
            reverse=True,
        )
        for name, details in ranked:
            if len(desired) >= max_profiles:
                break
            if any(entry['name'] == name for entry in desired):
                continue
            if have_ip_data and not details.get('ip'):
                logger.debug(f"Skipping {name}: no known IP (server likely retired)")
                continue
            desired.append({
                'name': name,
                'hostname': denormalize_server_name(name),
                'ip': details.get('ip'),
            })

    return desired


def sync_vpn_profiles(recommended_servers, config):
    """Add profiles for the most-requested servers and return the list of
    lower-ranked NordVPN profiles to remove after a successful connect."""
    dry_run = config['dry_run']
    profiles = parse_openvpn_profiles()
    nord_profiles = [p for p in profiles if 'nordvpn' in p['name'].lower()]
    if not nord_profiles:
        logger.warning("No existing NordVPN profile found to use as a template; skipping profile sync")
        return []

    max_profiles = config['max_profiles'] or len(nord_profiles)
    desired = build_desired_servers(recommended_servers, max_profiles)
    logger.info(f"Desired top {max_profiles} servers: {', '.join(entry['name'] for entry in desired)}")

    to_remove = [
        profile for profile in nord_profiles
        if not any(re.search(entry['name'], profile['name'], re.IGNORECASE) for entry in desired)
    ]

    missing = [
        entry for entry in desired
        if not any(re.search(entry['name'], profile['name'], re.IGNORECASE) for profile in nord_profiles)
    ]

    if not missing and not to_remove:
        logger.info("Configured profiles already match the most-requested servers")
        return []

    template = nord_profiles[0]
    existing_ids = {profile['id'] for profile in profiles}
    for entry in missing:
        clone_profile(template, entry, existing_ids, dry_run)

    return to_remove


# ------------------------------------------------------------------------------

def main():
    try:
        config = load_local_config()

        configured_vpns = get_configured_vpns()
        if not configured_vpns:
            logger.warning("No VPNs configured on NAS.")
            return

        # Get recommended servers
        recommended_servers = get_recommended_servers()

        # Normalize server names to match the format of configured VPNs
        normalized_recommended_servers = [normalize_server_name(server['hostname']) for server in recommended_servers]

        track_server_usage(recommended_servers)

        # Reshape the configured profiles around the most-requested servers
        profiles_to_remove = []
        if config['sync_profiles'] and os.path.isdir(SYNO_OPENVPN_DIR):
            profiles_to_remove = sync_vpn_profiles(recommended_servers, config)
            if not config['dry_run']:
                configured_vpns = get_configured_vpns()

        # Find the highest recommended server that is configured
        connected_vpn = None
        for server in normalized_recommended_servers:
            for vpn_name in configured_vpns:
                # Check if the server is configured
                if re.search(server, vpn_name, re.IGNORECASE):
                    logger.info(f"Connecting to recommended server: {server}")
                    connect_to_vpn(vpn_name)
                    logger.info(f"Successfully connected to {server}")
                    connected_vpn = vpn_name
                    break
            if connected_vpn:
                break

            # Log warning if server is not configured
            logger.warning(f"{server} is not configured on the NAS")

        if not connected_vpn:
            logger.warning("No recommended servers are configured on the NAS.")
            return

        # Only drop lower-ranked profiles once a connection is confirmed, and
        # never the profile we are connected through
        for profile in profiles_to_remove:
            if profile['name'] == connected_vpn:
                logger.info(f"Keeping {profile['name']}: it is the active connection")
                continue
            remove_profile(profile, config['dry_run'])
    except Exception as e:
        logger.error(f"An uncaught error occurred: {e}")
        sys.exit(1)


def track_server_usage(recommended_servers):
    # Return if no recommended servers are provided
    if not recommended_servers:
        return

    # Define the minimum date
    min_date = "2000-01-01T00:00:00"

    # Load existing server usage data from the file if it exists
    if os.path.exists(USAGE_FILE_PATH):
        with open(USAGE_FILE_PATH, 'r') as file:
            server_usage = json.load(file)
            # Ensure each server has a valid last recommended date
            for server in server_usage:
                if 'last recommended' not in server_usage[server] or not server_usage[server]['last recommended']:
                    server_usage[server]['last recommended'] = min_date
    else:
        server_usage = {}

    # Get the current date in ISO format
    current_date = datetime.now().isoformat()

    # Update the count, last recommended date and station IP for each recommended server
    for server in recommended_servers:
        name = normalize_server_name(server['hostname'])
        if name in server_usage:
            server_usage[name]['count'] += 1
        else:
            server_usage[name] = {'count': 1}
        server_usage[name]['last recommended'] = current_date
        if server.get('ip'):
            server_usage[name]['ip'] = server['ip']

    # Sort the server_usage dictionary by count in descending order and then by last recommended date in descending order
    sorted_server_usage = {k: v for k, v in sorted(server_usage.items(), key=lambda item: (item[1]['count'], item[1]['last recommended']), reverse=True)}

    # Save the updated and sorted server usage data back to the file
    with open(USAGE_FILE_PATH, 'w') as file:
        json.dump(sorted_server_usage, file, indent=4)


if __name__ == "__main__":
    main()
