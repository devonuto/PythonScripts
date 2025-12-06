import subprocess
import sys
import importlib
import qbittorrentapi
import time

# Set up logging
from logger_config import setup_custom_logger
logger = setup_custom_logger('Cleanup-qBittorrent')

class QbittorrentManager:
    def __init__(self, host, port, username, password):
        self.client = qbittorrentapi.Client(
            host=host,
            port=port,
            username=username,
            password=password
        )
        self.two_weeks_ago = time.time() - 2 * 7 * 24 * 60 * 60  # Two weeks in seconds

    def log_into_qbittorrent(self):
        try:
            self.client.auth_log_in()
            logger.info("Successfully logged in to qBittorrent.")
        except qbittorrentapi.LoginFailed as e:
            logger.error(f"Login failed. Check your username and password. Error Details: {e}")
            return
        except qbittorrentapi.APIError as e:
            logger.error(f"Could not connect to qBittorrent. Error Details: {e}")
            return
        except Exception as e:
            logger.error(f"An unexpected error occurred during login: {e}")
            return
        
    def process_errored_torrents(self, torrents):
        errored_states = ['error', 'unknown', 'missingFiles']
        errored_torrents = [t for t in torrents if t.state in errored_states]
        if errored_torrents:
            logger.info(f"Found {len(errored_torrents)} errored torrent(s):")
            for torrent in errored_torrents:
                logger.info(f"  - Name: {torrent.name}, Hash: {torrent.hash}, State: {torrent.state}")

            for torrent in errored_torrents:
                logger.info(f"Handling errored torrent: {torrent.name}")
                try:
                    self.client.torrents_recheck(torrent_hashes=torrent.hash)
                    time.sleep(10)  # Wait for recheck to complete
                    updated_torrent_info = self.client.torrents_info(torrent_hashes=torrent.hash)
                    if updated_torrent_info and updated_torrent_info[0].state not in errored_states:
                        logger.info("  - Recheck successful, torrent is no longer errored.")
                        continue
                    else:
                        logger.info("  - Recheck did not resolve the issue. Deleting torrent...")
                        self.delete_torrent(torrent.hash)

                except qbittorrentapi.TorrentFileNotFoundError:
                    logger.error(f"  - Error: Torrent not found: {torrent.name}")
                except qbittorrentapi.APIError as e:
                    logger.error(f"  - Error: qBittorrent API error: {e}")
                except Exception as e:
                    logger.error(f"  - An unexpected error occurred: {e}")
        else:
            logger.info("No errored torrents found.")

        # Return the original list of torrents with errored torrents removed.
        return [t for t in torrents if t.state not in errored_states]
        
    def process_stalled_torrents(self, torrents):    
        # Check if any torrents are stalled
        stalled_torrents = [t for t in torrents if 'stalled' in t.state.lower()]
        if stalled_torrents:
            logger.info(f"Found {len(stalled_torrents)} stalled torrent(s):")
            for torrent in stalled_torrents:
                logger.info(f"  - Name: {torrent.name}, Hash: {torrent.hash}, State: {torrent.state}")

            # Attempt to handle each stalled torrent.
            for torrent in stalled_torrents:
                logger.info(f"Handling stalled torrent: {torrent.name}")
                try:
                    # 1. Try a force resume.  This is the first, least disruptive thing to try.
                    logger.info("  - Attempting force start...")
                    self.client.torrents_set_force_start(torrent_hashes=torrent.hash)
                    time.sleep(2)  # Give qBittorrent a moment to try resuming.
                    updated_torrent_info = self.client.torrents_info(torrent_hashes=torrent.hash)  #get the updated info
                    if updated_torrent_info and updated_torrent_info[0].state != 'stalled':
                        logger.info("  - Force resume successful.")
                        continue  # Move on to the next torrent if force resume worked

                    # 2. If force resume didn't work, try rechecking.
                    logger.info("  - Force resume failed. Attempting recheck...")
                    self.client.torrents_recheck(torrent_hashes=torrent.hash)
                    time.sleep(10)  # Rechecking can take a while, so we wait longer.
                    updated_torrent_info = self.client.torrents_info(torrent_hashes=torrent.hash)
                    if updated_torrent_info and updated_torrent_info[0].state != 'stalled':
                        logger.info("  - Recheck successful, torrent is no longer stalled.")
                        continue

                    # 3. As a last resort, stop and restart the torrent.
                    logger.info("  - Recheck did not resolve the issue. Stopping and restarting torrent...")
                    self.client.torrents_stop(torrent_hashes=torrent.hash)
                    time.sleep(5)
                    self.client.torrents_start(torrent_hashes=torrent.hash)
                    time.sleep(5)
                    updated_torrent_info = self.client.torrents_info(torrent_hashes=torrent.hash)
                    if updated_torrent_info and updated_torrent_info[0].state != 'stalled':
                        logger.info("  - Torrent successfully stopped and started.")
                        continue
                    else:
                        logger.info("  - Stopping and starting the torrent did not resolve the issue.  Deleting torrent...")
                        self.delete_torrent(torrent.hash)

                except qbittorrentapi.TorrentFileNotFoundError:
                    logger.error(f"  - Error: Torrent not found: {torrent.name}")
                except qbittorrentapi.APIError as e:
                    logger.error(f"  - Error: qBittorrent API error: {e}")
                except Exception as e:
                    logger.error(f"  - An unexpected error occurred: {e}")
        else:
            logger.info("No stalled torrents found.")
        
        # Return the original list of torrents with stalled torrents removed.
        return [t for t in torrents if 'stalled' not in t.state.lower()]
        
    def process_completed_torrents(self, torrents):
        completed_states = ['uploading', 'completed', 'seeding', 'queuedUP', 'stoppedUP']
        completed_torrents = [t for t in torrents if t.state in completed_states]
        if completed_torrents:
            logger.info(f"Found {len(completed_torrents)} completed torrent(s):")
            for torrent in completed_torrents:
                logger.info(f"  - Name: {torrent.name}, Hash: {torrent.hash}, State: {torrent.state}")

            for torrent in completed_torrents:
                logger.info("  - Torrent is completed. Deleting...")
                self.delete_torrent(torrent.hash)
        else:
            logger.info("No completed torrents found.")

    def log_out_of_qbittorrent(self):
        self.client.auth_log_out()
        logger.info("Logged out of qBittorrent")

    def get_torrents(self):
        logger.info(f"Getting torrent tasks")
        torrents = self.client.torrents_info()
        return [t for t in torrents if t.category is not None]

    def delete_torrent(self, torrent_hash):
        self.client.torrents_delete(delete_files=True, torrent_hashes=torrent_hash)
        logger.info(f"Deleted torrent with hash: {torrent_hash}")

    def clean_up_torrents(self):
        torrents = self.get_torrents()
        torrents = self.process_stalled_torrents(torrents)
        torrents = self.process_errored_torrents(torrents)
        self.process_completed_torrents(torrents)

if __name__ == "__main__":
    host = "https://qbittorrent.devonuto.com/"
    port = 443
    username = "devonuto"
    password = "adminadmin"

    qb_manager = QbittorrentManager(host, port, username, password)
    try:
        qb_manager.log_into_qbittorrent()
        qb_manager.clean_up_torrents()
    finally:
        qb_manager.log_out_of_qbittorrent()
