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
    OUTPUT_WEB_DIR = Path("/volume2/web") # Root directory for index.html, opml, and feeds subdir
elif current_os == "Windows":
    # Configuration for Windows (UNC paths to NAS share)
    # Replace '\\DEVOMEDIA\web' with the correct UNC path to your NAS's '/volume2/web' directory
    AUDIOBOOKS_BASE_DIR = Path(r"\\DEVOMEDIA\web\audiobooks") # Use 'r' for raw string to handle backslashes
    OUTPUT_WEB_DIR = Path(r"\\DEVOMEDIA\web") # Root directory for index.html, opml, and feeds subdir
else:
    print(f"ERROR: Unsupported Operating System '{current_os}'. Please configure paths manually.")
    AUDIOBOOKS_BASE_DIR = Path("./audiobooks_unknown_os") # Dummy path
    OUTPUT_WEB_DIR = Path("./output_unknown_os")     # Dummy path


# --- Common Configuration (adjust if needed) ---
FEEDS_SUBDIR = "feeds" # Subdirectory for feed XML files (relative to OUTPUT_WEB_DIR)
HTML_INDEX_FILENAME = "index.html" # Changed from audiobook_feeds.html
OPML_FILENAME = "audiobook_feeds.opml"       # Name of the OPML file (in OUTPUT_WEB_DIR)
DESCRIPTION_FILENAME = "description.txt" # Filename for book description text file (fallback)
COVER_IMAGE_FILENAME = "folder.jpg" # Standard name for cover images

# Public base URL for accessing audio files and cover images FROM THE INTERNET
# This points to the 'audiobooks' subdirectory where actual media files are.
PUBLIC_AUDIO_FILES_BASE_URL = "https://audiobooks.devo-media.synology.me/audiobooks"

# Base domain URL - this is where index.html and opml will be served from,
# and where the 'feeds' subdirectory will be.
BASE_DOMAIN_URL = "https://audiobooks.devo-media.synology.me"

# Construct full public URLs
PUBLIC_FEEDS_BASE_URL = f"{BASE_DOMAIN_URL}/{FEEDS_SUBDIR}"
PUBLIC_HTML_OPML_BASE_URL = f"{BASE_DOMAIN_URL}" # index.html and opml are at the root of this domain


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

            cover_image_path = book_dir / COVER_IMAGE_FILENAME
            public_cover_image_url_for_feed = None
            public_cover_image_url_for_html = None

            if cover_image_path.is_file():
                try:
                    # relative_image_path_parts is relative to AUDIOBOOKS_BASE_DIR
                    relative_image_path_parts = cover_image_path.relative_to(AUDIOBOOKS_BASE_DIR).parts
                    # Construct full public URL for images using PUBLIC_AUDIO_FILES_BASE_URL
                    public_cover_image_url_for_feed = f"{PUBLIC_AUDIO_FILES_BASE_URL}/{'/'.join(relative_image_path_parts)}"
                    public_cover_image_url_for_html = public_cover_image_url_for_feed
                except ValueError:
                     print(f"    ERROR: Could not determine relative path for cover image: {cover_image_path}")
                     time.sleep(2)
            else:
                print(f"    WARNING: Cover image '{COVER_IMAGE_FILENAME}' not found for {book_title_folder_name}. Feed will lack image. HTML will show placeholder if any.")
                time.sleep(1)

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

            if not public_cover_image_url_for_feed:
                 print(f"    WARNING: No cover image URL for feed of book {book_title_folder_name}. iTunes image tag will be missing.")

            print(f"    Found {len(audio_files)} audio files (episodes).")

            rss = ET.Element("rss", version="2.0", attrib={"xmlns:itunes": "http://www.itunes.com/dtds/podcast-1.0.dtd", "xmlns:content": "http://purl.org/rss/1.0/modules/content/"})
            channel = ET.SubElement(rss, "channel")

            ET.SubElement(channel, "title").text = podcast_title
            ET.SubElement(channel, "link").text = BASE_DOMAIN_URL # Link to the main site (where index.html is)
            ET.SubElement(channel, "description").text = book_description_text
            ET.SubElement(channel, "language").text = PODCAST_LANGUAGE
            ET.SubElement(channel, "pubDate").text = get_rfc822_date()
            ET.SubElement(channel, "lastBuildDate").text = get_rfc822_date()

            ET.SubElement(channel, "itunes:author").text = author_name
            ET.SubElement(channel, "itunes:summary").text = book_description_text
            if public_cover_image_url_for_feed:
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
                    # relative_audio_path_parts is relative to AUDIOBOOKS_BASE_DIR
                    relative_audio_path_parts = audio_file_path_for_episode.relative_to(AUDIOBOOKS_BASE_DIR).parts
                    # Construct full public URL for audio files using PUBLIC_AUDIO_FILES_BASE_URL
                    public_audio_file_url = f"{PUBLIC_AUDIO_FILES_BASE_URL}/{'/'.join(relative_audio_path_parts)}"
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
                    "feed_url": f"{PUBLIC_FEEDS_BASE_URL}/{feed_xml_filename.replace(os.sep, '/')}",
                    "image_url": public_cover_image_url_for_html
                })
            except Exception as e:
                print(f"    ERROR: Could not write XML feed for {podcast_title}: {e}")
                time.sleep(2)

    # --- Generate OPML File ---
    if all_feeds_info:
        opml = ET.Element("opml", version="2.0")
        head = ET.SubElement(opml, "head")
        ET.SubElement(head, "title").text = "Audiobook Podcast Feeds"
        ET.SubElement(head, "dateCreated").text = get_rfc822_date()
        body = ET.SubElement(opml, "body")
        
        all_feeds_info.sort(key=lambda x: x['title'])
        for feed_info in all_feeds_info:
            ET.SubElement(body, "outline",
                          type="rss",
                          text=feed_info["title"],
                          title=feed_info["title"],
                          xmlUrl=feed_info["feed_url"])
        
        opml_path = OUTPUT_WEB_DIR / OPML_FILENAME
        try:
            opml_str = ET.tostring(opml, encoding='utf-8')
            parsed_opml = minidom.parseString(opml_str)
            pretty_opml_str = parsed_opml.toprettyxml(indent="  ", encoding="utf-8")
            with open(opml_path, "wb") as f:
                f.write(pretty_opml_str)
            print(f"\nSUCCESS: OPML file generated: {opml_path}")
        except Exception as e:
            print(f"\nERROR: Could not write OPML file: {e}")
            time.sleep(2)


    # --- Generate HTML Index Page ---
    if all_feeds_info:
        public_opml_url = f"{PUBLIC_HTML_OPML_BASE_URL}/{OPML_FILENAME}" # OPML is at the root

        html_content = f"""<!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Audiobook Podcast Feeds</title>
            <style>
                body {{ 
                    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; 
                    margin: 0; 
                    padding: 0;
                    background-color: #f0f2f5; /* Light grey background */
                    color: #333; 
                    line-height: 1.6;
                }}
                .container {{ 
                    width: 90%; /* More fluid width */
                    max-width: 960px; /* Max width for larger screens */
                    margin: 20px auto; /* Reduced top/bottom margin for mobile */
                    padding: 15px; /* Reduced padding for mobile */
                    background-color: #fff; 
                    border-radius: 8px; 
                    box-shadow: 0 2px 10px rgba(0,0,0,0.08); 
                }}
                h1 {{ 
                    color: #1a1a1a; /* Darker heading */
                    text-align: center; 
                    margin-bottom: 20px; /* Reduced margin */
                    font-size: 1.8em; /* Responsive font size */
                }}
                .opml-link-container {{ 
                    text-align: center; 
                    margin-bottom: 25px; 
                }}
                .opml-link {{ 
                    display: inline-block; 
                    padding: 12px 22px; /* Slightly larger padding for touch */
                    background-color: #28a745; 
                    color: white; 
                    border-radius: 5px; 
                    text-decoration: none; 
                    font-size: 1.0em; /* Adjusted font size */
                    transition: background-color 0.3s ease; 
                    font-weight: 500;
                }}
                .opml-link:hover, .opml-link:focus {{ 
                    background-color: #218838; 
                    outline: none; /* Remove default focus outline if custom is not added */
                }}
                .feed-list {{ 
                    list-style-type: none; 
                    padding: 0; 
                }}
                .feed-item {{ 
                    display: flex; 
                    flex-direction: row; /* Default for larger screens */
                    align-items: center; 
                    margin-bottom: 15px; 
                    padding: 12px; 
                    background-color: #f9f9f9; /* Lighter item background */
                    border: 1px solid #e0e0e0; /* Softer border */
                    border-radius: 6px; 
                    transition: box-shadow 0.3s ease; 
                }}
                .feed-item:hover {{ 
                    box-shadow: 0 3px 8px rgba(0,0,0,0.1); 
                }}
                .feed-item img {{ 
                    width: 70px; /* Slightly smaller image */
                    height: 70px; 
                    object-fit: cover; 
                    border-radius: 4px; 
                    margin-right: 15px; 
                    border: 1px solid #ccc;
                    flex-shrink: 0; /* Prevent image from shrinking */
                }}
                .feed-info {{ 
                    flex-grow: 1; 
                    min-width: 0; /* Allow text to wrap properly in flex item */
                }}
                .feed-info h2 {{ 
                    margin: 0 0 5px 0; 
                    font-size: 1.2em; /* Adjusted font size */
                }}
                .feed-info h2 a {{ 
                    text-decoration: none; 
                    color: #0066cc; /* Standard link blue */
                }}
                .feed-info h2 a:hover, .feed-info h2 a:focus {{ 
                    text-decoration: underline; 
                }}
                .feed-info .links-container p {{ /* Target p tags inside links-container */
                    margin: 8px 0 0 0; /* Add some top margin to space out the links */
                    font-size: 0.85em; 
                    color: #444; 
                }}
                .subscribe-link, .pocketcasts-link {{ 
                    display: inline-block; 
                    margin-right: 10px; /* Space between subscribe links */
                    margin-top: 8px; 
                    font-size: 0.85em; 
                    padding: 7px 14px; 
                    color: white; 
                    border-radius: 4px; 
                    text-decoration: none; 
                    transition: background-color 0.3s ease; 
                    font-weight: 500;
                }}
                .subscribe-link {{ /* Generic podcast app link */
                    background-color: #0066cc; 
                }}
                .subscribe-link:hover, .subscribe-link:focus {{ 
                    background-color: #004c99; 
                }}
                .pocketcasts-link {{ /* Pocket Casts specific link */
                    background-color: #f43409; /* Pocket Casts orange/red */
                }}
                .pocketcasts-link:hover, .pocketcasts-link:focus {{
                    background-color: #c32907;
                }}
                .no-image {{ 
                    width: 70px; 
                    height: 70px; 
                    background-color: #e0e0e0; /* Softer placeholder background */
                    display: flex; 
                    align-items: center; 
                    justify-content: center; 
                    color: #555; 
                    font-size:0.75em; 
                    text-align:center; 
                    border-radius: 4px; 
                    margin-right: 15px; 
                    border: 1px solid #ccc;
                    flex-shrink: 0;
                }}

                /* Media Query for smaller screens */
                @media (max-width: 600px) {{
                    .container {{
                        width: 100%;
                        margin: 0;
                        padding: 10px;
                        border-radius: 0; /* Full width on small screens */
                        box-shadow: none;
                    }}
                    h1 {{
                        font-size: 1.5em;
                        margin-bottom: 15px;
                    }}
                    .feed-item {{
                        flex-direction: column; /* Stack image and info vertically */
                        align-items: flex-start; /* Align items to the start */
                    }}
                    .feed-item img, .no-image {{
                        margin-right: 0;
                        margin-bottom: 10px; /* Add space below image when stacked */
                        width: 60px; /* Even smaller image for stacked layout */
                        height: 60px;
                    }}
                    .feed-info h2 {{
                        font-size: 1.1em;
                    }}
                    .opml-link, .subscribe-link, .pocketcasts-link {{
                        padding: 10px 18px; /* Ensure good tap size */
                        font-size: 0.95em;
                        margin-bottom: 5px; /* Add some space if they wrap */
                    }}
                    .feed-info .links-container p {{
                         display: flex; /* Allow links to wrap nicely */
                         flex-wrap: wrap;
                    }}
                }}
            </style>
        </head><body>
        <div class="container">
            <h1>Available Audiobook Podcast Feeds</h1>
            <div class="opml-link-container">
                <a href="{public_opml_url}" class="opml-link" download="{OPML_FILENAME}">Download All Feeds (OPML)</a>
            </div>
            <ul class="feed-list">
        """

        # all_feeds_info is already sorted from OPML generation
        for feed_info in all_feeds_info:
            html_content += '<li class="feed-item">'
            if feed_info['image_url']:
                html_content += f'<img src="{feed_info["image_url"]}" alt="Cover for {feed_info["title"]}">'
            else:
                html_content += '<div class="no-image">No Cover</div>'
            html_content += '<div class="feed-info">'
            
            # Prepare URLs for different subscription links
            direct_feed_url = feed_info["feed_url"]
            generic_podcast_scheme_url = f"podcast://{direct_feed_url.replace('https://', '').replace('http://', '')}"
            pocketcasts_scheme_url = f"pktc://subscribe/{direct_feed_url.replace('https://', '').replace('http://', '')}"

            html_content += f'<h2><a href="{direct_feed_url}">{feed_info["title"]}</a></h2>'
            html_content += '<div class="links-container">' # Container for subscribe links
            html_content += f'<p><a href="{generic_podcast_scheme_url}" class="subscribe-link">Subscribe (General)</a>'
            html_content += f'<a href="{pocketcasts_scheme_url}" class="pocketcasts-link">Subscribe (Pocket Casts)</a></p>'
            html_content += f'<p><small>Direct feed: <a href="{direct_feed_url}">{direct_feed_url}</a></small></p>'
            html_content += '</div>' # Close links-container
            html_content += '</div></li>' # Close feed-info and feed-item

        html_content += """
            </ul>
        </div></body></html>
        """
        html_index_path = OUTPUT_WEB_DIR / HTML_INDEX_FILENAME # This will now be 'index.html'
        try:
            with open(html_index_path, "w", encoding="utf-8") as f:
                f.write(html_content)
            print(f"\nSUCCESS: HTML index page generated: {html_index_path}")
            # The public URL for index.html will be the BASE_DOMAIN_URL itself
            print(f"Access HTML index at: {PUBLIC_HTML_OPML_BASE_URL}/") # Or just BASE_DOMAIN_URL
            print(f"Access OPML file at: {public_opml_url}")

        except Exception as e:
            print(f"\nERROR: Could not write HTML index page: {e}")
            time.sleep(2)
    else:
        print("\nNo feeds were generated, so no HTML index page or OPML file was created.")
        time.sleep(2)
    print("\nPodcast feed generation finished.")

if __name__ == "__main__":
    mimetypes.init()
    mimetypes.add_type("audio/aac", ".aac")
    mimetypes.add_type("audio/mp4", ".m4a")
    generate_feeds()
