import qbittorrentapi
import time

# https://qbittorrent-api.readthedocs.io/en/latest/apidoc/torrents.html

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
            print("Logged into qBittorrent")
        except qbittorrentapi.LoginFailed as e:
            raise Exception(f"Failed to log in: {e}")

    def log_out_of_qbittorrent(self):
        self.client.auth_log_out()
        print("Logged out of qBittorrent")

    def get_torrents(self):
        print("Getting torrent tasks")
        return self.client.torrents_info()

    def delete_torrent(self, torrent_hash):
        self.client.torrents_delete(delete_files=True, torrent_hashes=torrent_hash)
        print(f"Deleted torrent with hash: {torrent_hash}")

    def clean_up_torrents(self):
        torrents = self.get_torrents()
        for torrent in torrents:
            added_on = torrent.added_on
            downloaded = torrent.downloaded
            print(f"Added: {added_on}. \"{torrent.name}\", Status: {torrent.state}. Downloaded: {downloaded}")
            if torrent.state == 'error' or (added_on < self.two_weeks_ago and downloaded == 0):
                self.delete_torrent(torrent.hash)

if __name__ == "__main__":
    host = "localhost"
    port = 9865
    username = "devonuto"
    password = "adminadmin"

    qb_manager = QbittorrentManager(host, port, username, password)
    try:
        qb_manager.log_into_qbittorrent()
        qb_manager.clean_up_torrents()
    finally:
        qb_manager.log_out_of_qbittorrent()
