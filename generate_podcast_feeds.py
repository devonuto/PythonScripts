import os
import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime, timezone, timedelta
import re
from pathlib import Path
import mimetypes # For determining audio file MIME types
import mutagen # For reading ID3 tags
import time # Added for pausing
import platform # To suggest path configurations

# --- Configuration ---

# Dynamically set base paths based on Operating System
current_os = platform.system()
if current_os == "Linux":
    # Configuration for Synology NAS (Linux-style paths)
    AUDIOBOOKS_BASE_DIR = Path("/volume2/web/audiobooks")
    OUTPUT_WEB_DIR = Path("/volume2/web")
elif current_os == "Windows":
    # Configuration for Windows (UNC paths to NAS share)
    # Replace '\\DEVOMEDIA\web' with the correct UNC path to your NAS's '/volume2/web' directory
    # For example, if 'web' is a share name pointing to /volume2/web:
    AUDIOBOOKS_BASE_DIR = Path(r"\\DEVOMEDIA\web\audiobooks") # Use 'r' for raw string to handle backslashes
    OUTPUT_WEB_DIR = Path(r"\\DEVOMEDIA\web")
else:
    # Fallback or error for other OSes
    print(f"ERROR: Unsupported Operating System '{current_os}'. Please configure paths manually.")
    # You might want to exit here or set default paths if appropriate
    # For now, we'll let it proceed and likely fail at directory checks if paths are not valid.
    # Setting to a dummy path to avoid NameError, but script will likely fail.
    AUDIOBOOKS_BASE_DIR = Path("./audiobooks_unknown_os")
    OUTPUT_WEB_DIR = Path("./output_unknown_os")


# --- Common Configuration (adjust if needed) ---
FEEDS_SUBDIR = "feeds" # Subdirectory for feed XML files (relative to OUTPUT_WEB_DIR)
HTML_INDEX_FILENAME = "audiobook_feeds.html" # Name of the HTML index file (in OUTPUT_WEB_DIR)

# Public base URL for accessing audio files and cover images FROM THE INTERNET
# These URLs DO NOT CHANGE based on where you run the script. They reflect how
# the files are served by your NAS's Web Station.
PUBLIC_AUDIO_BASE_URL = "https://audiobooks.devo-media.synology.me/audiobooks"
PUBLIC_FEEDS_BASE_URL = f"https://audiobooks.devo-media.synology.me/{FEEDS_SUBDIR}"

# Default podcast settings
PODCAST_LANGUAGE = "en-us"
PODCAST_EXPLICIT = "no"
PODCAST_DESCRIPTION_DEFAULT = "An audiobook."
PODCAST_CATEGORY = "Books"

SUPPORTED_AUDIO_EXTENSIONS = ['.mp3', '.m4a', '.ogg', '.aac', '.wav']

# --- Helper Functions ---

def create_safe_filename(name):
    name = re.sub(r'[^\w\s-]', '', name).strip()
    name = re.sub(r'[-\s]+', '-', name)
    return name

def get_rfc822_date(dt=None):
    if isinstance(dt, str):
        try:
            if len(dt) == 4 and dt.isdigit():
                 dt_obj = datetime.strptime(dt, "%Y").replace(tzinfo=timezone.utc)
            elif len(dt) == 10 and dt.count('-') == 2 :
                 dt_obj = datetime.strptime(dt, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            else:
                from dateutil import parser
                dt_obj = parser.parse(dt)
                if dt_obj.tzinfo is None:
                    dt_obj = dt_obj.replace(tzinfo=timezone.utc)
        except ImportError:
            print("    NOTICE: dateutil library not found. Please install it (`pip install python-dateutil` or `pip3 install python-dateutil`) for advanced date parsing from ID3 tags. Falling back to current time for this episode.")
            time.sleep(2)
            dt_obj = datetime.now(timezone.utc)
        except ValueError:
            print(f"    WARNING: Could not parse date string '{dt}' from ID3 tag. Falling back to current time for this episode.")
            time.sleep(2)
            dt_obj = datetime.now(timezone.utc)
    elif isinstance(dt, datetime):
        dt_obj = dt
        if dt_obj.tzinfo is None:
            dt_obj = dt_obj.replace(tzinfo=timezone.utc)
    else:
        dt_obj = datetime.now(timezone.utc)
    return dt_obj.strftime("%a, %d %b %Y %H:%M:%S %z")

def get_file_mime_type(filepath):
    mime_type, _ = mimetypes.guess_type(filepath)
    return mime_type or 'application/octet-stream'

# --- Main Script Logic ---

def generate_feeds():
    print("Starting podcast feed generation...")
    # current_os is already defined globally in the configuration section
    print(f"Running on: {current_os}")
    if current_os == "Windows":
        print("Using Windows paths (e.g., UNC paths like \\\\SERVER\\share\\folder).")
        print(f"  Audiobooks Base: {AUDIOBOOKS_BASE_DIR}")
        print(f"  Output Web Dir:  {OUTPUT_WEB_DIR}")
    elif current_os == "Linux":
        print("Using Linux/NAS paths (e.g., /volumeX/path/to/folder).")
        print(f"  Audiobooks Base: {AUDIOBOOKS_BASE_DIR}")
        print(f"  Output Web Dir:  {OUTPUT_WEB_DIR}")
    else:
        print(f"WARNING: Paths for '{current_os}' might not be correctly configured. Proceeding with potentially dummy paths.")
        print(f"  Audiobooks Base: {AUDIOBOOKS_BASE_DIR}")
        print(f"  Output Web Dir:  {OUTPUT_WEB_DIR}")
        time.sleep(3)


    print("Ensure 'mutagen' and 'python-dateutil' are installed (`pip install mutagen python-dateutil`)")
    time.sleep(1) # Short pause to read the above

    feeds_output_dir = OUTPUT_WEB_DIR / FEEDS_SUBDIR
    try:
        feeds_output_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        print(f"ERROR: Could not create output directory {feeds_output_dir}: {e}")
        print(f"       Please check permissions and if the base path '{OUTPUT_WEB_DIR}' is accessible.")
        time.sleep(2)
        return


    all_feeds_info = []

    if not AUDIOBOOKS_BASE_DIR.is_dir():
        print(f"ERROR: Audiobooks base directory not found or not accessible: {AUDIOBOOKS_BASE_DIR}")
        print(f"       Please check the path and network share permissions if running on Windows.")
        time.sleep(2)
        return

    for author_dir in AUDIOBOOKS_BASE_DIR.iterdir():
        if not author_dir.is_dir():
            continue
        author_name = author_dir.name
        print(f"\nProcessing Author: {author_name}")

        for book_dir in author_dir.iterdir():
            if not book_dir.is_dir():
                continue
            book_title_folder_name = book_dir.name
            print(f"  Processing Book: {book_title_folder_name}")

            podcast_title = f"{author_name} - {book_title_folder_name}"
            feed_filename_base = create_safe_filename(podcast_title)
            feed_xml_filename = f"{feed_filename_base}.xml"
            feed_xml_path = feeds_output_dir / feed_xml_filename

            cover_image_path = book_dir / "folder.jpg"
            if not cover_image_path.is_file():
                print(f"    WARNING: Cover image 'folder.jpg' not found for {book_title_folder_name}. Skipping this book.")
                time.sleep(2)
                continue

            try:
                # Pathlib handles joining paths correctly across OS
                relative_image_path_parts = cover_image_path.relative_to(AUDIOBOOKS_BASE_DIR).parts
                public_cover_image_url = f"{PUBLIC_AUDIO_BASE_URL}/{'/'.join(relative_image_path_parts)}" # URLs always use forward slashes
            except ValueError: # Happens if cover_image_path is not inside AUDIOBOOKS_BASE_DIR (should not happen with current logic)
                 print(f"    ERROR: Could not determine relative path for cover image: {cover_image_path}")
                 time.sleep(2)
                 continue


            audio_files = sorted([
                f for f in book_dir.iterdir()
                if f.is_file() and f.suffix.lower() in SUPPORTED_AUDIO_EXTENSIONS
            ])

            if not audio_files:
                print(f"    WARNING: No audio files found for {book_title_folder_name}. Skipping this book.")
                time.sleep(2)
                continue

            print(f"    Found {len(audio_files)} audio files (episodes).")

            rss = ET.Element("rss", version="2.0", attrib={"xmlns:itunes": "http://www.itunes.com/dtds/podcast-1.0.dtd", "xmlns:content": "http://purl.org/rss/1.0/modules/content/"})
            channel = ET.SubElement(rss, "channel")

            ET.SubElement(channel, "title").text = podcast_title
            ET.SubElement(channel, "link").text = PUBLIC_AUDIO_BASE_URL # This should be the link to your main podcast page
            ET.SubElement(channel, "description").text = PODCAST_DESCRIPTION_DEFAULT
            ET.SubElement(channel, "language").text = PODCAST_LANGUAGE
            ET.SubElement(channel, "pubDate").text = get_rfc822_date()
            ET.SubElement(channel, "lastBuildDate").text = get_rfc822_date()

            ET.SubElement(channel, "itunes:author").text = author_name
            ET.SubElement(channel, "itunes:summary").text = PODCAST_DESCRIPTION_DEFAULT
            ET.SubElement(channel, "itunes:image", href=public_cover_image_url)
            ET.SubElement(channel, "itunes:explicit").text = PODCAST_EXPLICIT
            ET.SubElement(channel, "itunes:category", text=PODCAST_CATEGORY)

            for index, audio_file_path in enumerate(audio_files):
                item = ET.SubElement(channel, "item")
                episode_title = audio_file_path.stem
                episode_description = f"Chapter: {episode_title}"
                episode_pub_date_obj = datetime.fromtimestamp(audio_file_path.stat().st_mtime, timezone.utc) - timedelta(seconds=index)

                try:
                    audio_tags = mutagen.File(audio_file_path, easy=True)
                    if audio_tags:
                        if 'title' in audio_tags and audio_tags['title']:
                            episode_title = audio_tags['title'][0]
                        if 'comment' in audio_tags and audio_tags['comment']:
                            episode_description = audio_tags['comment'][0]
                        elif 'description' in audio_tags and audio_tags['description']:
                             episode_description = audio_tags['description'][0]
                        
                        id3_date_str = None
                        if 'date' in audio_tags and audio_tags['date']:
                            id3_date_str = audio_tags['date'][0]
                        elif 'originaldate' in audio_tags and audio_tags['originaldate']:
                            id3_date_str = audio_tags['originaldate'][0]
                        elif 'year' in audio_tags and audio_tags['year']:
                            id3_date_str = audio_tags['year'][0]

                        if id3_date_str:
                            episode_pub_date_obj = id3_date_str
                    else:
                        print(f"      INFO: No ID3 tags found or readable for {audio_file_path.name} (using easy=True).")
                except mutagen.MutagenError as e:
                    print(f"      WARNING: Mutagen error reading {audio_file_path.name}: {e}. Using filename as title.")
                    time.sleep(2)
                except Exception as e:
                    print(f"      WARNING: Unexpected error reading ID3 for {audio_file_path.name}: {e}. Using defaults.")
                    time.sleep(2)

                ET.SubElement(item, "title").text = episode_title
                ET.SubElement(item, "description").text = episode_description
                ET.SubElement(item, "content:encoded").text = f"<![CDATA[{episode_description}]]>"

                try:
                    relative_audio_path_parts = audio_file_path.relative_to(AUDIOBOOKS_BASE_DIR).parts
                    public_audio_file_url = f"{PUBLIC_AUDIO_BASE_URL}/{'/'.join(relative_audio_path_parts)}" # URLs always use forward slashes
                except ValueError:
                     print(f"    ERROR: Could not determine relative path for audio file: {audio_file_path}")
                     time.sleep(2)
                     continue # Skip this episode if URL can't be formed


                ET.SubElement(item, "guid", isPermaLink="true").text = public_audio_file_url
                ET.SubElement(item, "pubDate").text = get_rfc822_date(episode_pub_date_obj)

                file_size = str(audio_file_path.stat().st_size)
                mime_type = get_file_mime_type(audio_file_path)
                ET.SubElement(item, "enclosure", url=public_audio_file_url, length=file_size, type=mime_type)

                ET.SubElement(item, "itunes:author").text = author_name
                ET.SubElement(item, "itunes:summary").text = episode_description
                ET.SubElement(item, "itunes:explicit").text = PODCAST_EXPLICIT

            try:
                xml_str = ET.tostring(rss, encoding='utf-8')
                parsed_xml = minidom.parseString(xml_str)
                pretty_xml_str = parsed_xml.toprettyxml(indent="  ", encoding="utf-8")

                with open(feed_xml_path, "wb") as f:
                    f.write(pretty_xml_str)
                print(f"    SUCCESS: Feed generated: {feed_xml_path}")
                all_feeds_info.append({
                    "title": podcast_title,
                    "url": f"{PUBLIC_FEEDS_BASE_URL}/{feed_xml_filename.replace(os.sep, '/')}" # Ensure feed URL uses forward slashes
                })
            except Exception as e:
                print(f"    ERROR: Could not write XML feed for {podcast_title}: {e}")
                time.sleep(2)

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
            # Construct the public URL for the HTML index
            public_html_index_url = f"{PUBLIC_FEEDS_BASE_URL.rsplit('/', 1)[0]}/{HTML_INDEX_FILENAME}" # Assumes FEEDS_BASE_URL is like .../feeds
            print(f"Access it at: {public_html_index_url}")

        except Exception as e:
            print(f"\nERROR: Could not write HTML index page: {e}")
            time.sleep(2)
    else:
        print("\nNo feeds were generated, so no HTML index page was created.")
        time.sleep(2)
    print("\nPodcast feed generation finished.")

if __name__ == "__main__":
    mimetypes.init()
    mimetypes.add_type("audio/aac", ".aac")
    mimetypes.add_type("audio/mp4", ".m4a")
    generate_feeds()
