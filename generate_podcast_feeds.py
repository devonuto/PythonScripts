import os
import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime, timezone, timedelta
import re
from pathlib import Path
import mimetypes # For determining audio file MIME types
import mutagen # For reading ID3 tags
import time # Added for pausing

# --- Configuration ---
# Base directory where author folders are located
AUDIOBOOKS_BASE_DIR = Path("/volume2/web/audiobooks")
# Base directory where generated feeds and HTML index will be saved
OUTPUT_WEB_DIR = Path("/volume2/web")
# Subdirectory within OUTPUT_WEB_DIR for feed XML files
FEEDS_SUBDIR = "feeds"
# Name of the HTML index file
HTML_INDEX_FILENAME = "audiobook_feeds.html"

# Public base URL for accessing audio files and cover images
# IMPORTANT: This MUST match how your files are served by Web Station
PUBLIC_AUDIO_BASE_URL = "https://audiobooks.devo-media.synology.me/audiobooks"
# Public base URL for accessing the generated feed XML files
PUBLIC_FEEDS_BASE_URL = f"https://audiobooks.devo-media.synology.me/{FEEDS_SUBDIR}"

# Default podcast settings (can be customized)
PODCAST_LANGUAGE = "en-us"
PODCAST_EXPLICIT = "no" # "yes" or "no"
PODCAST_DESCRIPTION_DEFAULT = "An audiobook."
PODCAST_CATEGORY = "Books" # iTunes category

# Supported audio file extensions
SUPPORTED_AUDIO_EXTENSIONS = ['.mp3', '.m4a', '.ogg', '.aac', '.wav'] # Mutagen supports these well

# --- Helper Functions ---

def create_safe_filename(name):
    """Creates a filesystem-safe filename from a string."""
    name = re.sub(r'[^\w\s-]', '', name).strip() # Remove non-alphanumeric (except underscore, whitespace, hyphen)
    name = re.sub(r'[-\s]+', '-', name) # Replace spaces and multiple hyphens with single hyphen
    return name

def get_rfc822_date(dt=None):
    """Returns a date string in RFC 822 format.
    Accepts a datetime object or a string that can be parsed.
    """
    if isinstance(dt, str):
        try:
            # Attempt to parse common date formats, including just year
            if len(dt) == 4 and dt.isdigit(): # Just a year
                 dt_obj = datetime.strptime(dt, "%Y").replace(tzinfo=timezone.utc)
            elif len(dt) == 10 and dt.count('-') == 2 : # YYYY-MM-DD
                 dt_obj = datetime.strptime(dt, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            else: # Try to parse more complex date/time strings (this might need refinement)
                from dateutil import parser
                dt_obj = parser.parse(dt)
                if dt_obj.tzinfo is None: # Make timezone-aware if it's naive
                    dt_obj = dt_obj.replace(tzinfo=timezone.utc)
        except ImportError:
            print("    NOTICE: dateutil library not found. Please install it (`pip3 install python-dateutil`) for advanced date parsing from ID3 tags. Falling back to current time for this episode.")
            time.sleep(2) # Pause after notice
            dt_obj = datetime.now(timezone.utc)
        except ValueError:
            print(f"    WARNING: Could not parse date string '{dt}' from ID3 tag. Falling back to current time for this episode.")
            time.sleep(2) # Pause after warning
            dt_obj = datetime.now(timezone.utc)
    elif isinstance(dt, datetime):
        dt_obj = dt
        if dt_obj.tzinfo is None: # Ensure datetime is timezone-aware
            dt_obj = dt_obj.replace(tzinfo=timezone.utc)
    else: # Default to now if no valid date provided
        dt_obj = datetime.now(timezone.utc)
    return dt_obj.strftime("%a, %d %b %Y %H:%M:%S %z")


def get_file_mime_type(filepath):
    """Gets the MIME type of a file."""
    mime_type, _ = mimetypes.guess_type(filepath)
    return mime_type or 'application/octet-stream' # Default if not guessable

# --- Main Script Logic ---

def generate_feeds():
    """Scans directories and generates podcast feeds and an HTML index."""
    print("Starting podcast feed generation...")
    print("Ensure 'mutagen' and 'python-dateutil' are installed (`pip3 install mutagen python-dateutil`)")


    # Ensure output directories exist
    feeds_output_dir = OUTPUT_WEB_DIR / FEEDS_SUBDIR
    feeds_output_dir.mkdir(parents=True, exist_ok=True)

    all_feeds_info = [] # To store info for the HTML index

    if not AUDIOBOOKS_BASE_DIR.is_dir():
        print(f"ERROR: Audiobooks base directory not found: {AUDIOBOOKS_BASE_DIR}")
        time.sleep(2) # Pause after error
        return

    # Iterate through author directories
    for author_dir in AUDIOBOOKS_BASE_DIR.iterdir():
        if not author_dir.is_dir():
            continue
        author_name = author_dir.name
        print(f"\nProcessing Author: {author_name}")

        # Iterate through book directories for this author
        for book_dir in author_dir.iterdir():
            if not book_dir.is_dir():
                continue
            book_title_folder_name = book_dir.name # Keep original folder name for messages
            print(f"  Processing Book: {book_title_folder_name}")

            podcast_title = f"{author_name} - {book_title_folder_name}"
            feed_filename_base = create_safe_filename(podcast_title)
            feed_xml_filename = f"{feed_filename_base}.xml"
            feed_xml_path = feeds_output_dir / feed_xml_filename

            # Find cover image
            cover_image_path = book_dir / "folder.jpg"
            if not cover_image_path.is_file():
                print(f"    WARNING: Cover image 'folder.jpg' not found for {book_title_folder_name}. Skipping this book.")
                time.sleep(2) # Pause after warning
                continue

            relative_image_path = cover_image_path.relative_to(AUDIOBOOKS_BASE_DIR)
            public_cover_image_url = f"{PUBLIC_AUDIO_BASE_URL}/{'/'.join(relative_image_path.parts)}"

            audio_files = sorted([
                f for f in book_dir.iterdir()
                if f.is_file() and f.suffix.lower() in SUPPORTED_AUDIO_EXTENSIONS
            ])

            if not audio_files:
                print(f"    WARNING: No audio files found for {book_title_folder_name}. Skipping this book.")
                time.sleep(2) # Pause after warning
                continue

            print(f"    Found {len(audio_files)} audio files (episodes).")

            rss = ET.Element("rss", version="2.0", attrib={"xmlns:itunes": "http://www.itunes.com/dtds/podcast-1.0.dtd", "xmlns:content": "http://purl.org/rss/1.0/modules/content/"})
            channel = ET.SubElement(rss, "channel")

            ET.SubElement(channel, "title").text = podcast_title
            ET.SubElement(channel, "link").text = PUBLIC_AUDIO_BASE_URL
            ET.SubElement(channel, "description").text = PODCAST_DESCRIPTION_DEFAULT
            ET.SubElement(channel, "language").text = PODCAST_LANGUAGE
            ET.SubElement(channel, "pubDate").text = get_rfc822_date()
            ET.SubElement(channel, "lastBuildDate").text = get_rfc822_date()

            ET.SubElement(channel, "itunes:author").text = author_name
            ET.SubElement(channel, "itunes:summary").text = PODCAST_DESCRIPTION_DEFAULT
            ET.SubElement(channel, "itunes:image", href=public_cover_image_url)
            ET.SubElement(channel, "itunes:explicit").text = PODCAST_EXPLICIT
            ET.SubElement(channel, "itunes:category", text=PODCAST_CATEGORY)

            # Use file modification time as a fallback for episode pubDate to maintain some order
            # This will be overridden if ID3 date is found
            # Stagger slightly to ensure unique times if many files have same mod time.
            fallback_episode_pubdate_base = datetime.fromtimestamp(book_dir.stat().st_mtime, timezone.utc)


            for index, audio_file_path in enumerate(audio_files):
                item = ET.SubElement(channel, "item")

                # Defaults
                episode_title = audio_file_path.stem
                episode_description = f"Chapter: {episode_title}"
                # Fallback pubDate: use file's modification time, slightly staggered for uniqueness
                episode_pub_date_obj = datetime.fromtimestamp(audio_file_path.stat().st_mtime, timezone.utc) - timedelta(seconds=index)


                try:
                    audio_tags = mutagen.File(audio_file_path, easy=True)
                    if audio_tags:
                        if 'title' in audio_tags and audio_tags['title']:
                            episode_title = audio_tags['title'][0]
                        # For description, try common comment/description tags
                        if 'comment' in audio_tags and audio_tags['comment']: # EasyID3 often uses 'comment'
                            episode_description = audio_tags['comment'][0]
                        elif 'description' in audio_tags and audio_tags['description']:
                             episode_description = audio_tags['description'][0]
                        # For iTunes summary, could also try 'TIT3' (subtitle/description refinement) or 'COMM' directly if not using easy=True
                        # For pubDate, try 'date', 'originaldate', 'year'
                        id3_date_str = None
                        if 'date' in audio_tags and audio_tags['date']:
                            id3_date_str = audio_tags['date'][0]
                        elif 'originaldate' in audio_tags and audio_tags['originaldate']: # Often YYYY-MM-DD
                            id3_date_str = audio_tags['originaldate'][0]
                        elif 'year' in audio_tags and audio_tags['year']: # Just YYYY
                            id3_date_str = audio_tags['year'][0]

                        if id3_date_str:
                            # get_rfc822_date will attempt to parse it
                            # For more robust parsing, especially of partial dates, get_rfc822_date was updated
                            # We pass the string directly to our updated get_rfc822_date
                            episode_pub_date_obj = id3_date_str # Pass string for parsing

                    else:
                        print(f"      INFO: No ID3 tags found or readable for {audio_file_path.name} (using easy=True).")
                        # time.sleep(1) # Optional shorter pause for info messages

                except mutagen.MutagenError as e:
                    print(f"      WARNING: Mutagen error reading {audio_file_path.name}: {e}. Using filename as title.")
                    time.sleep(2) # Pause after warning
                except Exception as e:
                    print(f"      WARNING: Unexpected error reading ID3 for {audio_file_path.name}: {e}. Using defaults.")
                    time.sleep(2) # Pause after warning


                ET.SubElement(item, "title").text = episode_title
                ET.SubElement(item, "description").text = episode_description # For general RSS description
                ET.SubElement(item, "content:encoded").text = f"<![CDATA[{episode_description}]]>" # For HTML in description

                relative_audio_path = audio_file_path.relative_to(AUDIOBOOKS_BASE_DIR)
                public_audio_file_url = f"{PUBLIC_AUDIO_BASE_URL}/{'/'.join(relative_audio_path.parts)}"

                ET.SubElement(item, "guid", isPermaLink="true").text = public_audio_file_url
                ET.SubElement(item, "pubDate").text = get_rfc822_date(episode_pub_date_obj)


                file_size = str(audio_file_path.stat().st_size)
                mime_type = get_file_mime_type(audio_file_path)
                ET.SubElement(item, "enclosure", url=public_audio_file_url, length=file_size, type=mime_type)

                ET.SubElement(item, "itunes:author").text = author_name
                ET.SubElement(item, "itunes:summary").text = episode_description # iTunes summary can be same as description
                ET.SubElement(item, "itunes:explicit").text = PODCAST_EXPLICIT
                # itunes:duration - still omitted for simplicity, would require more from mutagen

            try:
                xml_str = ET.tostring(rss, encoding='utf-8')
                parsed_xml = minidom.parseString(xml_str)
                pretty_xml_str = parsed_xml.toprettyxml(indent="  ", encoding="utf-8")

                with open(feed_xml_path, "wb") as f:
                    f.write(pretty_xml_str)
                print(f"    SUCCESS: Feed generated: {feed_xml_path}")
                all_feeds_info.append({
                    "title": podcast_title,
                    "url": f"{PUBLIC_FEEDS_BASE_URL}/{feed_xml_filename}"
                })
            except Exception as e:
                print(f"    ERROR: Could not write XML feed for {podcast_title}: {e}")
                time.sleep(2) # Pause after error

    if all_feeds_info:
        html_content = "<html><head><title>Audiobook Podcast Feeds</title>"
        html_content += "<style>body { font-family: sans-serif; margin: 20px; } h1 { color: #333; } ul { list-style-type: none; padding: 0; } li { margin-bottom: 10px; } a { text-decoration: none; color: #007bff; } a:hover { text-decoration: underline; }</style>"
        html_content += "</head><body>"
        html_content += "<h1>Available Audiobook Podcast Feeds</h1><ul>"
        all_feeds_info.sort(key=lambda x: x['title'])
        for feed_info in all_feeds_info:
            html_content += f"<li><a href='{feed_info['url']}'>{feed_info['title']}</a></li>"
        html_content += "</ul></body></html>"
        html_index_path = OUTPUT_WEB_DIR / HTML_INDEX_FILENAME
        try:
            with open(html_index_path, "w", encoding="utf-8") as f:
                f.write(html_content)
            print(f"\nSUCCESS: HTML index page generated: {html_index_path}")
            print(f"Access it at: https://audiobooks.devo-media.synology.me/{HTML_INDEX_FILENAME}")
        except Exception as e:
            print(f"\nERROR: Could not write HTML index page: {e}")
            time.sleep(2) # Pause after error
    else:
        print("\nNo feeds were generated, so no HTML index page was created.")
        time.sleep(2) # Pause after this message
    print("\nPodcast feed generation finished.")

if __name__ == "__main__":
    mimetypes.init()
    mimetypes.add_type("audio/aac", ".aac")
    mimetypes.add_type("audio/mp4", ".m4a")
    generate_feeds()
