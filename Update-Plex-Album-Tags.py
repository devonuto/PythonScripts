import os
import argparse
import subprocess
import shutil
from plexapi.server import PlexServer
from mutagen.easyid3 import EasyID3
from mutagen.flac import FLAC
from mutagen.easymp4 import EasyMP4

# ================= CONFIGURATION =================
PLEX_URL = 'http://192.168.1.5:32400'
PLEX_TOKEN = 'H22FyLAMJ3JzHiGPeZpu'  # Find this in Plex Web > Account > Settings > Authorized Devices
LIBRARY_NAME = "Steve's Music"
FFMPEG_PATH = '/usr/local/bin/ffmpeg'
# =================================================

def get_audio_handler(filepath):
    """Returns the correct Mutagen handler based on file extension."""
    ext = os.path.splitext(filepath)[1].lower()
    
    # Helper to pick the class
    handler_class = None
    if ext == '.mp3': handler_class = EasyID3
    elif ext == '.flac': handler_class = FLAC
    elif ext == '.m4a': handler_class = EasyMP4
    
    if not handler_class:
        return None

    try:
        return handler_class(filepath)
    except Exception as e:
        error_msg = str(e)
        
        # Check specifically for the M4A header error or encoding error
        if ext == '.m4a' and ("unpack requires a buffer of 8 bytes" in error_msg or "codec can't decode byte" in error_msg):
            # Attempt Repair
            if repair_m4a(filepath):
                # RETRY: Try to open the file again now that it is fixed
                try:
                    return handler_class(filepath)
                except Exception as retry_e:
                    print(f"[ERROR] Repaired file still failed to open: {retry_e}")
                    return None
            else:
                # Repair failed, return None so we skip this file
                return None

        # Print other errors normally
        print(f"[ERROR] Opening {filepath}: {e}")
        return None

def repair_m4a(filepath):
    """
    Uses ffmpeg to copy audio streams to a new container to fix malformed headers.
    Overwrites the original file ONLY if successful.
    """
    print(f"[REPAIR] Attempting to fix headers for: {filepath}")
    
    # Create a temp filename
    temp_path = filepath + ".fixed.m4a"
    
    # ffmpeg command: 
    # -i input, -c copy (no encoding), -y (overwrite temp), -v error (quiet)
    cmd = [FFMPEG_PATH, '-i', filepath, '-c', 'copy', '-y', '-v', 'error', temp_path]
    
    try:
        # Run FFmpeg
        subprocess.run(cmd, check=True)
        
        # Verify temp file exists and has size
        if os.path.exists(temp_path) and os.path.getsize(temp_path) > 0:
            # Overwrite the original file with the fixed temp file
            shutil.move(temp_path, filepath)
            print(f"   -> Success: File repaired and original replaced.")
            return True
        else:
            print("   -> Failed: Output file was empty.")
            return False
            
    except subprocess.CalledProcessError:
        print(f"   -> Failed: FFmpeg encountered an error.")
        # Cleanup temp file if it was created
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return False
    except FileNotFoundError:
        print(f"   -> Failed: 'ffmpeg' command not found. Is it installed?")
        return False
    except Exception as e:
        print(f"   -> Failed: {e}")
        return False

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

            # — PREPARE DATA —
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

            # — COMPARE & APPLY —
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

            # — SAVE —
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

def process_one_star_tracks(music_lib, dry_run=False):
    """
    Finds and processes 1-star tracks (userRating between 0 and 2.0).
    Deletes them if dry_run is False.
    """
    print("-" * 40)
    if dry_run:
        print("SEARCHING FOR 1-STAR TRACKS (DRY-RUN: NO DELETION)")
    else:
        print("SEARCHING FOR AND DELETING 1-STAR TRACKS")
    print("-" * 40)
    
    # We want tracks where 0 < userRating <= 2.0
    print("Fetching all tracks to check ratings...")
    all_tracks = music_lib.search(libtype='track')
    
    found_count = 0
    deleted_count = 0
    
    for track in all_tracks:
        # Check if userRating exists and is in range
        if hasattr(track, 'userRating') and track.userRating is not None:
            rating = float(track.userRating)
            if 0.0 < rating <= 2.0:
                found_count += 1
                prefix = "[DRY-RUN] [DELETE]" if dry_run else "[DELETING]"
                print(f"{prefix} {rating}/10 - {track.title} - {track.originalTitle or track.grandparentTitle} ({track.parentTitle})")
                
                if not dry_run:
                    try:
                        track.delete()
                        print("    -> Successfully deleted from Plex and filesystem.")
                        deleted_count += 1
                    except Exception as e:
                        print(f"    -> [ERROR] Failed to delete: {e}")
                else:
                    for media in track.media:
                        for part in media.parts:
                            print(f"        File: {part.file}")

    print("-" * 40)
    if dry_run:
        print(f"Found {found_count} 1-star tracks that WOULD be deleted.")
    else:
        print(f"Found {found_count} 1-star tracks. Successfully deleted {deleted_count}.")
    print("-" * 40)
    
    return found_count

def main():
    parser = argparse.ArgumentParser(description="Sync Plex Metadata to Music File Tags")
    parser.add_argument('-v', '--verbose', action='store_true', help="Print status even when no changes are made.")
    parser.add_argument('--dry-run', action='store_true', help="Show what would be changed without modifying files.")
    parser.add_argument('--delete-one-star', action='store_true', help="Delete tracks with 1-star rating (0 < rating <= 2.0).")
    args = parser.parse_args()

    if args.verbose:
        print(f"Connecting to Plex at {PLEX_URL}...")
        
    try:
        plex = PlexServer(PLEX_URL, PLEX_TOKEN)
        music_lib = plex.library.section(LIBRARY_NAME)
    except Exception as e:
        print(f"Failed to connect to Plex: {e}")
        return

    # — 1-STAR CHECK —
    if args.delete_one_star:
        process_one_star_tracks(music_lib, dry_run=args.dry_run)
        # We continue to normal sync as requested ("As well as")
        print("\nStarting Normal Sync Process...")

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

    # — FINAL REPORT —
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