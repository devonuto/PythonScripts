import os
import csv
from mutagen.easyid3 import EasyID3
from mutagen.mp3 import MP3
from mutagen.flac import FLAC
from mutagen.oggvorbis import OggVorbis
from mutagen.mp4 import MP4
from mutagen.mp4 import MP4FreeForm

def get_acoustid_fingerprint(file_path):
    try:
        if file_path.lower().endswith('.mp3'):
            audio = MP3(file_path, ID3=EasyID3)
        elif file_path.lower().endswith('.flac'):
            audio = FLAC(file_path)
        elif file_path.lower().endswith('.ogg'):
            audio = OggVorbis(file_path)
        elif file_path.lower().endswith(('.m4a', '.aac', '.mp4')):
            audio = MP4(file_path)
        else:
            return None
        
        print(f"Reading {file_path}...")
        fingerprint = audio.get("acoustid_fingerprint", [None])[0]
        if not fingerprint:
            mp4fingerprint = audio.get("----:com.apple.iTunes:Acoustid Fingerprint", [None])[0]
            if isinstance(mp4fingerprint, MP4FreeForm):
                fingerprint = mp4fingerprint.decode("utf-8")

        if not fingerprint:
            print(f"Could not find fingerprint for {file_path}")
            return None

        return fingerprint
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        with open(error_csv, mode='a', newline='', encoding='utf-8') as csv_file:
            writer = csv.writer(csv_file)
            writer.writerow([file_path, str(e)])
        return None

def find_duplicates(music_folder):
    fingerprints = {}
    duplicates = []

    for root, _, files in os.walk(music_folder):
        for file in files:
            file_path = os.path.join(root, file)
            fingerprint = get_acoustid_fingerprint(file_path)
            if fingerprint:
                if fingerprint in fingerprints:
                    duplicates.append((file_path, fingerprints[fingerprint]))
                else:
                    fingerprints[fingerprint] = file_path

    return duplicates

def save_duplicates_to_csv(duplicates, output_path):
    with open(output_path, mode='w', newline='', encoding='utf-8') as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(["Duplicate File", "Original File"])
        for duplicate, original in duplicates:
            writer.writerow([duplicate, original])

if __name__ == "__main__":
    music_folder = "D:\\Music"
    output_csv = os.path.join(os.path.dirname(__file__), "duplicate_songs.csv")
    error_csv = os.path.join(os.path.dirname(__file__), "tag_errors.csv")

    duplicates = find_duplicates(music_folder)
    save_duplicates_to_csv(duplicates, output_csv)

    print(f"Duplicate list saved to {output_csv}")
