from plexapi.server import PlexServer

# ================= CONFIGURATION =================
PLEX_URL = 'http://192.168.1.5:32400'
PLEX_TOKEN = 'H22FyLAMJ3JzHiGPeZpu'  # Find this in Plex Web > Account > Settings > Authorized Devices
LIBRARY_NAME = "Steve's Music"
DRY_RUN = False  # Set to False to actually apply changes
# =================================================

def merge_duplicates():
    print(f"Connecting to Plex server at {PLEX_URL}...")
    try:
        plex = PlexServer(PLEX_URL, PLEX_TOKEN)
    except Exception as e:
        print(f"Error connecting to Plex: {e}")
        return

    print(f"Scanning library: '{LIBRARY_NAME}'...")
    try:
        music_lib = plex.library.section(LIBRARY_NAME)
    except Exception as e:
        print(f"Library '{LIBRARY_NAME}' not found: {e}")
        return

    # specific search for albums
    albums = music_lib.albums()
    print(f"Found {len(albums)} total albums. Checking for duplicates...")

    # Dictionary to group albums by a unique key
    # Key format: (Artist Name, Album Title)
    grouped_albums = {}

    for album in albums:
        # We use parentTitle for Artist and title for Album Name
        artist = album.parentTitle
        title = album.title

        if artist and title:
            # Normalize strings: lowercase and strip whitespace to ensure accurate matching
            key = (artist.strip().lower(), title.strip().lower())
            
            if key not in grouped_albums:
                grouped_albums[key] = []
            grouped_albums[key].append(album)

    # Process duplicates
    duplicates_found = 0
    for key, album_list in grouped_albums.items():
        if len(album_list) > 1:
            duplicates_found += 1
            artist_name = album_list[0].parentTitle
            album_name = album_list[0].title
            
            print(f"\nDuplicate found: '{artist_name}' - '{album_name}'")
            print(f" -> Found {len(album_list)} copies.")

            # Logic: Keep the first one, merge the rest into it
            # You could add logic here to pick the 'best' one (e.g., highest track count)
            target_album = album_list[0]
            albums_to_merge = album_list[1:]

            if DRY_RUN:
                print(f"    [DRY RUN] Would merge {len(albums_to_merge)} items into main album (ID: {target_album.ratingKey}).")
            else:
                print(f"    [ACTION] Merging {len(albums_to_merge)} items into main album...")
                try:
                    # The merge method expects a list of ratingKeys (IDs)
                    target_album.merge([a.ratingKey for a in albums_to_merge])
                    print("    Success: Merge complete.")
                except Exception as e:
                    print(f"    Error merging: {e}")

    if duplicates_found == 0:
        print("\nNo duplicates found!")
    else:
        print(f"\nProcess complete. Found {duplicates_found} sets of duplicates.")

if __name__ == "__main__":
    merge_duplicates()