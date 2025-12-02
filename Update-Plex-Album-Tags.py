import os
import argparse
from plexapi.server import PlexServer
from mutagen.easyid3 import EasyID3
from mutagen.flac import FLAC
from mutagen.easymp4 import EasyMP4

# ================= CONFIGURATION =================
PLEX_URL = 'http://192.168.1.5:32400'
PLEX_TOKEN = 'H22FyLAMJ3JzHiGPeZpu'  # Find this in Plex Web > Account > Settings > Authorized Devices
LIBRARY_NAME = "Steve's Music"
# =================================================

def get_audio_handler(filepath):
    """Returns the correct Mutagen handler based on file extension."""
    ext = os.path.splitext(filepath)[1].lower()
    try:
        if ext == '.mp3': return EasyID3(filepath)
        if ext == '.flac': return FLAC(filepath)
        if ext == '.m4a': return EasyMP4(filepath)
    except Exception as e:
        print(f"[ERROR] Opening {filepath}: {e}")
    return None

def sync_track(plex_track, verbose=False, dry_run=False):
    """
    Syncs a single Plex track to its file.
    Returns: Integer (number of files updated)
    """
    
    files_updated_count = 0

    if not hasattr(plex_track, 'media'):
        if verbose:
            print(f"[SKIP] Item '{plex_track.title}' is not a track.")
        return 0

    for media in plex_track.media:
        for part in media.parts:
            filepath = part.file
            if not os.path.exists(filepath):
                continue

            audio = get_audio_handler(filepath)
            if not audio:
                continue

            # --- PREPARE DATA ---
            # Use originalTitle (Track Artist) if exists, otherwise Album Artist
            p_track_artist = plex_track.originalTitle if plex_track.originalTitle else plex_track.grandparentTitle
            
            tags_to_set = {
                'title': plex_track.title,
                'album': plex_track.parentTitle,
                'artist': p_track_artist,                   # Track Artist
                'albumartist': plex_track.grandparentTitle, # Album Artist
                'date': str(plex_track.year) if plex_track.year else None,
                'tracknumber': str(plex_track.index) if plex_track.index else None,
                'discnumber': str(plex_track.parentIndex) if plex_track.parentIndex else None
            }

            changes_made = False
            changes_log = []

            # --- COMPARE & APPLY ---
            for tag_key, desired_val in tags_to_set.items():
                if desired_val is None: 
                    continue

                val_str = str(desired_val).strip()

                current_val_list = audio.get(tag_key, [None])
                current_val = str(current_val_list[0]) if current_val_list[0] is not None else None

                if current_val != val_str:
                    audio[tag_key] = val_str
                    changes_made = True
                    changes_log.append(f"{tag_key}: '{current_val}' -> '{val_str}'")

            # --- SAVE ---
            if changes_made:
                files_updated_count += 1 # Increment local counter
                prefix = "[DRY-RUN]" if dry_run else "[UPDATE]"
                print(f"{prefix} {plex_track.title}")
                for log in changes_log:
                    print(f"   - {log}")

                if not dry_run:
                    try:
                        audio.save()
                    except Exception as e:
                        print(f"[ERROR] Could not save {filepath}: {e}")
                        files_updated_count -= 1 # Revert count if save failed
            else:
                if verbose:
                    print(f"[SKIP] {plex_track.title} - Already synced.")
    
    return files_updated_count

def main():
    parser = argparse.ArgumentParser(description="Sync Plex Metadata to Music File Tags")
    parser.add_argument('-v', '--verbose', action='store_true', help="Print status even when no changes are made.")
    parser.add_argument('--dry-run', action='store_true', help="Show what would be changed without modifying files.")
    args = parser.parse_args()

    if args.verbose:
        print(f"Connecting to Plex at {PLEX_URL}...")
        
    try:
        plex = PlexServer(PLEX_URL, PLEX_TOKEN)
        music_lib = plex.library.section(LIBRARY_NAME)
    except Exception as e:
        print(f"Failed to connect to Plex: {e}")
        return

    if args.verbose:
        print("Fetching all tracks from library...")
    
    all_tracks = music_lib.search(libtype='track')
    
    if args.verbose:
        print(f"Processing {len(all_tracks)} tracks...")

    # Initialize Global Counter
    total_files_updated = 0

    for i, track in enumerate(all_tracks):
        if args.verbose and i > 0 and i % 100 == 0:
            print(f"Progress: {i}/{len(all_tracks)}...")
            
        # Capture the return value (count of files updated for this track)
        total_files_updated += sync_track(track, verbose=args.verbose, dry_run=args.dry_run)

    # --- FINAL REPORT ---
    print("-" * 40)
    print("SYNC COMPLETE")
    print("-" * 40)
    if args.dry_run:
        print(f"Files that WOULD be updated: {total_files_updated}")
    else:
        print(f"Total Files Updated: {total_files_updated}")
    print("-" * 40)

if __name__ == "__main__":
    main()