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
    AUDIOBOOKS_BASE_DIR = Path(r"\\DEVOMEDIA\web\audiobooks") # Use 'r' for raw string to handle backslashes
    OUTPUT_WEB_DIR = Path(r"\\DEVOMEDIA\web")
else:
    print(f"ERROR: Unsupported Operating System '{current_os}'. Please configure paths manually.")
    AUDIOBOOKS_BASE_DIR = Path("./audiobooks_unknown_os") # Dummy path
    OUTPUT_WEB_DIR = Path("./output_unknown_os")     # Dummy path


# --- Common Configuration (adjust if needed) ---
FEEDS_SUBDIR = "feeds" # Subdirectory for feed XML files (relative to OUTPUT_WEB_DIR)
HTML_INDEX_FILENAME = "audiobook_feeds.html" # Name of the HTML index file (in OUTPUT_WEB_DIR)
DESCRIPTION_FILENAME = "description.txt" # Filename for book description text file (fallback)
COVER_IMAGE_FILENAME = "folder.jpg" # Standard name for cover images

# Public base URL for accessing audio files and cover images FROM THE INTERNET
PUBLIC_AUDIO_BASE_URL = "https://audiobooks.devo-media.synology.me/audiobooks"
PUBLIC_FEEDS_BASE_URL = f"https://audiobooks.devo-media.synology.me/{FEEDS_SUBDIR}"

# Default podcast settings
PODCAST_LANGUAGE = "en-us"
PODCAST_EXPLICIT = "no"
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
    time.sleep(1)

    feeds_output_dir = OUTPUT_WEB_DIR / FEEDS_SUBDIR
    try:
        feeds_output_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        print(f"ERROR: Could not create output directory {feeds_output_dir}: {e}")
        print(f"       Please check permissions and if the base path '{OUTPUT_WEB_DIR}' is accessible.")
        time.sleep(2)
        return

    all_feeds_info = [] # To store info for the HTML index: title, feed_url, image_url

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

            # --- Get Cover Image URL for HTML page and Feed ---
            cover_image_path = book_dir / COVER_IMAGE_FILENAME
            public_cover_image_url_for_feed = None # For the feed XML
            public_cover_image_url_for_html = None # For the HTML page

            if cover_image_path.is_file():
                try:
                    relative_image_path_parts = cover_image_path.relative_to(AUDIOBOOKS_BASE_DIR).parts
                    public_cover_image_url_for_feed = f"{PUBLIC_AUDIO_BASE_URL}/{'/'.join(relative_image_path_parts)}"
                    # For HTML, we can use the same URL or a relative one if HTML and images are served from same domain structure
                    public_cover_image_url_for_html = public_cover_image_url_for_feed
                except ValueError:
                     print(f"    ERROR: Could not determine relative path for cover image: {cover_image_path}")
                     time.sleep(2)
                     # Continue without cover for this book, or skip book? For now, continue.
            else:
                print(f"    WARNING: Cover image '{COVER_IMAGE_FILENAME}' not found for {book_title_folder_name}. Feed will lack image. HTML will show placeholder if any.")
                time.sleep(1)
                # Not skipping the book, just feed will lack image.

            # --- Get Book Description ---
            book_description_text = None
            default_book_description = f"An audiobook: {book_title_folder_name} by {author_name}."

            audio_files = sorted([
                f for f in book_dir.iterdir()
                if f.is_file() and f.suffix.lower() in SUPPORTED_AUDIO_EXTENSIONS
            ])

            if not audio_files:
                print(f"    WARNING: No audio files found for {book_title_folder_name}. Skipping this book for feed generation.")
                time.sleep(2)
                continue

            first_audio_file_path = audio_files[0]
            try:
                audio_tags = mutagen.File(first_audio_file_path, easy=True)
                if audio_tags:
                    if 'comment' in audio_tags and audio_tags['comment']:
                        book_description_text = audio_tags['comment'][0].strip()
                        if book_description_text: print(f"    INFO: Using book description from ID3 'comment' tag of '{first_audio_file_path.name}'.")
                    elif 'description' in audio_tags and audio_tags['description']:
                        book_description_text = audio_tags['description'][0].strip()
                        if book_description_text: print(f"    INFO: Using book description from ID3 'description' tag of '{first_audio_file_path.name}'.")
                    if not book_description_text:
                         print(f"    INFO: Relevant ID3 description/comment tags in '{first_audio_file_path.name}' are empty.")
            except mutagen.MutagenError as e:
                print(f"    WARNING: Mutagen error reading ID3 for book description from '{first_audio_file_path.name}': {e}.")
                time.sleep(1)
            except Exception as e:
                print(f"    WARNING: Unexpected error reading ID3 for book description from '{first_audio_file_path.name}': {e}.")
                time.sleep(1)

            if not book_description_text:
                description_file_path = book_dir / DESCRIPTION_FILENAME
                if description_file_path.is_file():
                    try:
                        with open(description_file_path, "r", encoding="utf-8") as f_desc:
                            book_description_text = f_desc.read().strip()
                        if book_description_text:
                            print(f"    INFO: Found and used description from '{DESCRIPTION_FILENAME}' for {book_title_folder_name}.")
                        else:
                            print(f"    INFO: Description file '{DESCRIPTION_FILENAME}' is empty for {book_title_folder_name}.")
                    except Exception as e:
                        print(f"    WARNING: Could not read '{DESCRIPTION_FILENAME}' for {book_title_folder_name}: {e}.")
                        time.sleep(2)
                else:
                    print(f"    INFO: Description file '{DESCRIPTION_FILENAME}' not found for {book_title_folder_name}.")

            if not book_description_text:
                book_description_text = default_book_description
                print(f"    INFO: Using default generated description for {book_title_folder_name}.")

            # Check for cover image again, as we need it for the feed itself
            if not public_cover_image_url_for_feed:
                 print(f"    WARNING: No cover image URL for feed of book {book_title_folder_name}. iTunes image tag will be missing.")


            print(f"    Found {len(audio_files)} audio files (episodes).")

            rss = ET.Element("rss", version="2.0", attrib={"xmlns:itunes": "http://www.itunes.com/dtds/podcast-1.0.dtd", "xmlns:content": "http://purl.org/rss/1.0/modules/content/"})
            channel = ET.SubElement(rss, "channel")

            ET.SubElement(channel, "title").text = podcast_title
            ET.SubElement(channel, "link").text = PUBLIC_AUDIO_BASE_URL
            ET.SubElement(channel, "description").text = book_description_text
            ET.SubElement(channel, "language").text = PODCAST_LANGUAGE
            ET.SubElement(channel, "pubDate").text = get_rfc822_date()
            ET.SubElement(channel, "lastBuildDate").text = get_rfc822_date()

            ET.SubElement(channel, "itunes:author").text = author_name
            ET.SubElement(channel, "itunes:summary").text = book_description_text
            if public_cover_image_url_for_feed: # Only add image tag if URL exists
                ET.SubElement(channel, "itunes:image", href=public_cover_image_url_for_feed)
            ET.SubElement(channel, "itunes:explicit").text = PODCAST_EXPLICIT
            ET.SubElement(channel, "itunes:category", text=PODCAST_CATEGORY)

            for index, audio_file_path_for_episode in enumerate(audio_files):
                item = ET.SubElement(channel, "item")
                episode_title = audio_file_path_for_episode.stem
                episode_specific_description = f"Chapter: {episode_title}"
                episode_pub_date_obj = datetime.fromtimestamp(audio_file_path_for_episode.stat().st_mtime, timezone.utc) - timedelta(seconds=index)

                try:
                    episode_audio_tags = mutagen.File(audio_file_path_for_episode, easy=True)
                    if episode_audio_tags:
                        if 'title' in episode_audio_tags and episode_audio_tags['title']:
                            episode_title = episode_audio_tags['title'][0]
                        if 'comment' in episode_audio_tags and episode_audio_tags['comment']:
                            episode_specific_description = episode_audio_tags['comment'][0].strip()
                        elif 'description' in episode_audio_tags and episode_audio_tags['description']:
                             episode_specific_description = episode_audio_tags['description'][0].strip()
                        id3_date_str = None
                        if 'date' in episode_audio_tags and episode_audio_tags['date']:
                            id3_date_str = episode_audio_tags['date'][0]
                        elif 'originaldate' in episode_audio_tags and episode_audio_tags['originaldate']:
                            id3_date_str = episode_audio_tags['originaldate'][0]
                        elif 'year' in episode_audio_tags and episode_audio_tags['year']:
                            id3_date_str = episode_audio_tags['year'][0]
                        if id3_date_str:
                            episode_pub_date_obj = id3_date_str
                    else:
                        print(f"      INFO: No ID3 tags found or readable for episode file {audio_file_path_for_episode.name} (using easy=True).")
                except mutagen.MutagenError as e:
                    print(f"      WARNING: Mutagen error reading episode file {audio_file_path_for_episode.name}: {e}. Using filename as title.")
                    time.sleep(2)
                except Exception as e:
                    print(f"      WARNING: Unexpected error reading ID3 for episode file {audio_file_path_for_episode.name}: {e}. Using defaults.")
                    time.sleep(2)

                ET.SubElement(item, "title").text = episode_title
                ET.SubElement(item, "description").text = episode_specific_description
                ET.SubElement(item, "content:encoded").text = f"<![CDATA[{episode_specific_description}]]>"

                try:
                    relative_audio_path_parts = audio_file_path_for_episode.relative_to(AUDIOBOOKS_BASE_DIR).parts
                    public_audio_file_url = f"{PUBLIC_AUDIO_BASE_URL}/{'/'.join(relative_audio_path_parts)}"
                except ValueError:
                     print(f"    ERROR: Could not determine relative path for audio file: {audio_file_path_for_episode}")
                     time.sleep(2)
                     continue

                ET.SubElement(item, "guid", isPermaLink="true").text = public_audio_file_url
                ET.SubElement(item, "pubDate").text = get_rfc822_date(episode_pub_date_obj)
                file_size = str(audio_file_path_for_episode.stat().st_size)
                mime_type = get_file_mime_type(audio_file_path_for_episode)
                ET.SubElement(item, "enclosure", url=public_audio_file_url, length=file_size, type=mime_type)
                ET.SubElement(item, "itunes:author").text = author_name
                ET.SubElement(item, "itunes:summary").text = episode_specific_description
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
                    "feed_url": f"{PUBLIC_FEEDS_BASE_URL}/{feed_xml_filename.replace(os.sep, '/')}", # XML feed URL
                    "image_url": public_cover_image_url_for_html # URL for the cover image for the HTML page
                })
            except Exception as e:
                print(f"    ERROR: Could not write XML feed for {podcast_title}: {e}")
                time.sleep(2)

    if all_feeds_info:
        html_content = """
        <html><head><title>Audiobook Podcast Feeds</title>
        <style>
            body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; margin: 0; background-color: #f4f4f4; color: #333; }
            .container { max-width: 900px; margin: 40px auto; padding: 20px; background-color: #fff; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
            h1 { color: #333; text-align: center; margin-bottom: 30px; }
            .feed-list { list-style-type: none; padding: 0; }
            .feed-item { display: flex; align-items: center; margin-bottom: 20px; padding: 15px; background-color: #fff; border: 1px solid #ddd; border-radius: 6px; transition: box-shadow 0.3s ease; }
            .feed-item:hover { box-shadow: 0 4px 12px rgba(0,0,0,0.15); }
            .feed-item img { width: 80px; height: 80px; object-fit: cover; border-radius: 4px; margin-right: 20px; border: 1px solid #eee; }
            .feed-info { flex-grow: 1; }
            .feed-info h2 { margin: 0 0 8px 0; font-size: 1.4em; color: #007bff; }
            .feed-info h2 a { text-decoration: none; color: inherit; }
            .feed-info h2 a:hover { text-decoration: underline; }
            .feed-info p { margin: 0; font-size: 0.9em; color: #555; }
            .subscribe-link { display: inline-block; margin-top: 5px; font-size: 0.9em; padding: 6px 12px; background-color: #007bff; color: white; border-radius: 4px; text-decoration: none; transition: background-color 0.3s ease; }
            .subscribe-link:hover { background-color: #0056b3; }
            .no-image { width: 80px; height: 80px; background-color: #e9ecef; display: flex; align-items: center; justify-content: center; color: #6c757d; font-size:0.8em; text-align:center; border-radius: 4px; margin-right: 20px; border: 1px solid #ddd;}
        </style>
        </head><body>
        <div class="container">
            <h1>Available Audiobook Podcast Feeds</h1>
            <ul class="feed-list">
        """

        all_feeds_info.sort(key=lambda x: x['title'])

        for feed_info in all_feeds_info:
            html_content += '<li class="feed-item">'
            if feed_info['image_url']:
                html_content += f'<img src="{feed_info["image_url"]}" alt="Cover for {feed_info["title"]}">'
            else:
                html_content += '<div class="no-image">No Cover</div>'
            html_content += '<div class="feed-info">'
            # Using podcast: scheme for the link to encourage opening in podcast app
            feed_link_with_scheme = f"podcast://{feed_info['feed_url'].replace('https://', '').replace('http://', '')}"
            # Some apps might prefer the direct https link, so we can offer both or just the direct one.
            # For simplicity, using the podcast: scheme here. Direct link is also good.
            html_content += f'<h2><a href="{feed_info["feed_url"]}">{feed_info["title"]}</a></h2>' # Direct link is safer for universal compatibility
            html_content += f'<p><a href="{feed_link_with_scheme}" class="subscribe-link">Subscribe with Podcast App</a></p>'
            html_content += f'<p><small>Direct feed: <a href="{feed_info["feed_url"]}">{feed_info["feed_url"]}</a></small></p>'
            html_content += '</div></li>'

        html_content += """
            </ul>
        </div></body></html>
        """
        html_index_path = OUTPUT_WEB_DIR / HTML_INDEX_FILENAME
        try:
            with open(html_index_path, "w", encoding="utf-8") as f:
                f.write(html_content)
            print(f"\nSUCCESS: HTML index page generated: {html_index_path}")
            public_html_index_url = f"{PUBLIC_FEEDS_BASE_URL.rsplit('/', 1)[0]}/{HTML_INDEX_FILENAME}"
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
