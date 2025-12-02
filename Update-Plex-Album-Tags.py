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
    """Syncs a single Plex track to its file."""
    for media in plex_track.media:
        for part in media.parts:
            filepath = part.file
            if not os.path.exists(filepath):
                continue

            audio = get_audio_handler(filepath)
            if not audio:
                continue

            tag_map = {
                'title': 'title',
                'grandparentTitle': 'artist',
                'parentTitle': 'album',
                'year': 'date',
                'index': 'tracknumber',
                'parentIndex': 'discnumber'
            }

            changes_made = False
            changes_log = []

            for plex_attr, tag_key in tag_map.items():
                plex_val = getattr(plex_track, plex_attr, None)
                if plex_val is None: continue

                val_str = str(plex_val)
                current_val_list = audio.get(tag_key, [None])
                current_val = current_val_list[0] if current_val_list else None

                if current_val != val_str:
                    audio[tag_key] = val_str
                    changes_made = True
                    changes_log.append(f"{tag_key}: '{current_val}' -> '{val_str}'")

            if changes_made:
                prefix = "[DRY-RUN]" if dry_run else "[UPDATE]"
                print(f"{prefix} {plex_track.title}")
                for log in changes_log:
                    print(f"   - {log}")

                if not dry_run:
                    try:
                        audio.save()
                    except Exception as e:
                        print(f"[ERROR] Could not save {filepath}: {e}")
            else:
                if verbose:
                    print(f"[SKIP] {plex_track.title} - Already synced.")

def main():
    # 1. Setup Argument Parser
    parser = argparse.ArgumentParser(description="Sync Plex Metadata to Music File Tags")
    
    parser.add_argument('-v', '--verbose', action='store_true', 
                        help="Print status even when no changes are made.")
    
    parser.add_argument('--dry-run', action='store_true', 
                        help="Show what would be changed without modifying files.")

    args = parser.parse_args()

    # 2. Connect to Plex
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
        
    all_tracks = music_lib.all()
    
    if args.verbose:
        print(f"Processing {len(all_tracks)} tracks...")

    # 3. Iterate
    for i, track in enumerate(all_tracks):
        # Progress indicator for verbose mode
        if args.verbose and i > 0 and i % 100 == 0:
            print(f"Progress: {i}/{len(all_tracks)}...")
            
        sync_track(track, verbose=args.verbose, dry_run=args.dry_run)

    print("Sync Complete.")

if __name__ == "__main__":
    main()