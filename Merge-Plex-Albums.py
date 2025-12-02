import argparse
from plexapi.server import PlexServer

# ================= CONFIGURATION =================
PLEX_URL = 'http://192.168.1.5:32400'
PLEX_TOKEN = 'H22FyLAMJ3JzHiGPeZpu'  # Find this in Plex Web > Account > Settings > Authorized Devices
LIBRARY_NAME = "Steve's Music"
# =================================================

def merge_duplicates(dry_run=False, verbose=False):
    if verbose:
        print(f"Connecting to Plex server at {PLEX_URL}...")
    
    try:
        plex = PlexServer(PLEX_URL, PLEX_TOKEN)
    except Exception as e:
        print(f"[ERROR] Connecting to Plex: {e}")
        return

    if verbose:
        print(f"Scanning library: '{LIBRARY_NAME}'...")
    
    try:
        music_lib = plex.library.section(LIBRARY_NAME)
    except Exception as e:
        print(f"[ERROR] Library '{LIBRARY_NAME}' not found: {e}")
        return

    # specific search for albums
    albums = music_lib.albums()
    
    if verbose:
        print(f"Found {len(albums)} total albums. Analyzing...")

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
    duplicates_sets_found = 0
    merges_performed = 0

    for key, album_list in grouped_albums.items():
        if len(album_list) > 1:
            duplicates_sets_found += 1
            
            # Get Names for display
            artist_name = album_list[0].parentTitle
            album_name = album_list[0].title
            
            # Logic: Keep the first one, merge the rest into it
            target_album = album_list[0]
            albums_to_merge = album_list[1:]

            prefix = "[DRY-RUN]" if dry_run else "[MERGE]"
            print(f"{prefix} '{artist_name}' - '{album_name}'")
            print(f"    -> Found {len(album_list)} copies. Merging {len(albums_to_merge)} into 1.")

            if not dry_run:
                try:
                    # The merge method expects a list of ratingKeys (IDs)
                    target_album.merge([a.ratingKey for a in albums_to_merge])
                    print("    -> Success.")
                    merges_performed += 1
                except Exception as e:
                    print(f"    -> [ERROR] Merge failed: {e}")

    # Summary
    print("-" * 40)
    print("MERGE PROCESS COMPLETE")
    print("-" * 40)
    if duplicates_sets_found == 0:
        print("No duplicates found.")
    else:
        print(f"Duplicate sets found: {duplicates_sets_found}")
        if dry_run:
            print(f"Sets that WOULD be merged: {duplicates_sets_found}")
        else:
            print(f"Sets successfully merged: {merges_performed}")
    print("-" * 40)

def main():
    parser = argparse.ArgumentParser(description="Find and Merge Duplicate Plex Albums")
    
    parser.add_argument('-v', '--verbose', action='store_true', 
                        help="Print connection details and scanning progress.")
    
    parser.add_argument('--dry-run', action='store_true', 
                        help="Scan and list duplicates without merging them.")

    args = parser.parse_args()

    merge_duplicates(dry_run=args.dry_run, verbose=args.verbose)

if __name__ == "__main__":
    main()