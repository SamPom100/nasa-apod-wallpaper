#!/usr/bin/env python3
"""
NASA APOD Desktop Background Setter
Fetches the Astronomy Picture of the Day and sets it as macOS desktop background
"""

import os
import sys
import json
import random
import time
import urllib.request
import urllib.error
import urllib.parse
from html.parser import HTMLParser
from pathlib import Path
import subprocess
from datetime import datetime, timedelta

# Directory to store downloaded wallpapers and config
WALLPAPER_DIR = Path.home() / ".nasa_apod_wallpapers"
WALLPAPER_DIR.mkdir(exist_ok=True)

CONFIG_FILE = WALLPAPER_DIR / "config.json"

FETCH_ATTEMPTS = 6
FETCH_RETRY_DELAY_SECONDS = 60
DESKTOP_ATTEMPTS = 3
DESKTOP_RETRY_DELAY_SECONDS = 5
IMAGE_EXTENSIONS = {
    '.jpg', '.jpeg', '.png', '.gif', '.webp', '.heic', '.tif', '.tiff'
}


def load_api_key():
    """Load API key from config file or environment variable"""
    # First try environment variable
    api_key = os.environ.get("NASA_API_KEY")
    if api_key:
        return api_key

    # Then try config file
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                api_key = config.get('api_key')
                if api_key:
                    return api_key
        except Exception as e:
            print(f"Warning: Could not read config file: {e}")

    # Prompt user to set up API key
    print("\n" + "=" * 60)
    print("NASA API Key Required")
    print("=" * 60)
    print("\nTo use this script, you need a free NASA API key.")
    print("\n1. Get your key at: https://api.nasa.gov/")
    print("2. Run this script again and enter your key when prompted")
    print("\nOr set it as an environment variable:")
    print("   export NASA_API_KEY='your_key_here'")
    print("\nOr create a config file at:")
    print(f"   {CONFIG_FILE}")
    print('   With content: {"api_key": "your_key_here"}')
    print("=" * 60)

    # Try to get key interactively
    try:
        api_key = input("\nEnter your NASA API key (or press Ctrl+C to exit): ").strip()
        if api_key:
            # Save it to config file
            with open(CONFIG_FILE, 'w') as f:
                json.dump({"api_key": api_key}, f, indent=2)
            print(f"\nAPI key saved to {CONFIG_FILE}")
            return api_key
    except (KeyboardInterrupt, EOFError):
        print("\nSetup cancelled.")

    sys.exit(1)


# Load API key
NASA_API_KEY = load_api_key()
APOD_API_URL = f"https://api.nasa.gov/planetary/apod?api_key={NASA_API_KEY}"
APOD_SITE_URL = "https://apod.nasa.gov/apod"


class ApodPageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.current_link = None
        self.full_image_path = None

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag.lower() == 'a':
            self.current_link = attributes.get('href')
        elif tag.lower() == 'img' and self.current_link:
            source = attributes.get('src')
            link_extension = Path(
                urllib.parse.urlparse(self.current_link).path
            ).suffix.lower()
            source_extension = Path(
                urllib.parse.urlparse(source or '').path
            ).suffix.lower()
            if (
                link_extension in IMAGE_EXTENSIONS
                and source_extension in IMAGE_EXTENSIONS
                and self.full_image_path is None
            ):
                self.full_image_path = self.current_link

    def handle_endtag(self, tag):
        if tag.lower() == 'a':
            self.current_link = None


def fetch_apod_data(date=None, exit_on_error=True):
    """Fetch the APOD metadata from NASA API. Returns data dict, or None on failure if exit_on_error=False."""
    url = APOD_API_URL
    if date:
        url += f"&date={date}"

    for attempt in range(1, FETCH_ATTEMPTS + 1):
        try:
            print(f"Fetching NASA APOD data{f' for {date}' if date else ''}...")
            with urllib.request.urlopen(url, timeout=10) as response:
                return json.loads(response.read().decode())
        except urllib.error.HTTPError as e:
            print(f"HTTP Error {e.code}: {e.reason}")
            retry = e.code in {429, 500, 502, 503, 504}
        except urllib.error.URLError as e:
            print(f"Error fetching APOD data: {e}")
            retry = True
        except Exception as e:
            print(f"Unexpected error: {e}")
            retry = True

        if retry and attempt < FETCH_ATTEMPTS:
            print(f"Retrying in {FETCH_RETRY_DELAY_SECONDS} seconds...")
            time.sleep(FETCH_RETRY_DELAY_SECONDS)
            continue

        if exit_on_error:
            sys.exit(1)
        return None


def fetch_apod_with_fallback(date=None):
    """Fetch APOD data with fallback to yesterday if today isn't available"""
    if date:
        return fetch_apod_data(date)

    today = datetime.now().strftime('%Y-%m-%d')
    data = fetch_apod_data(today, exit_on_error=False)
    if data is not None:
        return data

    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    print(f"Could not fetch today's APOD, fetching yesterday ({yesterday})...")
    return fetch_apod_data(yesterday)


def download_image(url, filename, exit_on_error=True):
    """Download the image from the given URL. Returns path, or None on failure."""
    filepath = WALLPAPER_DIR / filename
    temporary_path = filepath.with_suffix(f"{filepath.suffix}.download")

    try:
        print(f"Downloading image from: {url}")
        urllib.request.urlretrieve(url, temporary_path)
        temporary_path.replace(filepath)

        print(f"Image saved to: {filepath}")
        return filepath
    except Exception as e:
        if temporary_path.exists():
            temporary_path.unlink()
        print(f"Error downloading image: {e}")
        if exit_on_error:
            sys.exit(1)
        return None


def image_extension(url):
    """Return a supported image extension from a URL."""
    extension = Path(urllib.parse.urlparse(url).path).suffix.lower()
    return extension if extension in IMAGE_EXTENSIONS else '.jpg'


def fetch_apod_page_image_url(date_str):
    """Fetch the highest-resolution image URL from the APOD webpage."""
    try:
        date = datetime.strptime(date_str, '%Y-%m-%d')
        page_url = f"{APOD_SITE_URL}/ap{date:%y%m%d}.html"
        print("Fetching the APOD webpage for its full-resolution image...")
        with urllib.request.urlopen(page_url, timeout=10) as response:
            page = response.read().decode('utf-8', errors='replace')

        parser = ApodPageParser()
        parser.feed(page)
        if parser.full_image_path:
            return urllib.parse.urljoin(page_url, parser.full_image_path)
        print("Error: The APOD webpage has no full-resolution image link")
    except Exception as e:
        print(f"Error fetching the APOD webpage: {e}")
    return None


def download_apod_image(apod_data, date_str, exit_on_error=True):
    """Download the API full-resolution image or its APOD webpage fallback."""
    api_url = apod_data.get('hdurl')
    if api_url:
        filename = f"apod_{date_str}{image_extension(api_url)}"
        image_path = download_image(api_url, filename, exit_on_error=False)
        if image_path is not None:
            return image_path
        print("The API full-resolution image failed.")
    else:
        print("The API has no full-resolution image URL.")

    page_url = fetch_apod_page_image_url(date_str)
    if page_url:
        filename = f"apod_{date_str}{image_extension(page_url)}"
        image_path = download_image(page_url, filename, exit_on_error=False)
        if image_path is not None:
            return image_path

    print("Error: Could not download a full-resolution APOD image")
    if exit_on_error:
        sys.exit(1)
    return None


def cached_image_files():
    """Return cached APOD image files."""
    return [
        path for path in WALLPAPER_DIR.glob("apod_*")
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    ]


def pick_cache_images(exclude_path, count):
    """Pick distinct cached APOD images, excluding the given path."""
    candidates = cached_image_files()
    if exclude_path is not None:
        candidates = [
            path for path in candidates
            if path.resolve() != Path(exclude_path).resolve()
        ]
    random.shuffle(candidates)
    return candidates[:count]


def set_macos_wallpaper(image_path):
    """Set today's image on desktop 1, a random cached image on each other desktop."""
    script = '''
    on run imagePaths
        tell application "System Events"
            repeat with desktopIndex from 1 to count of imagePaths
                set picture of desktop desktopIndex to item desktopIndex of imagePaths
            end repeat
        end tell
    end run
    '''

    for attempt in range(1, DESKTOP_ATTEMPTS + 1):
        try:
            result = subprocess.run(
                ['osascript', '-e', 'tell application "System Events" to count of desktops'],
                check=True, capture_output=True, text=True
            )
            desktop_count = int(result.stdout.strip())
            if desktop_count < 1:
                raise RuntimeError("No macOS desktops are available")

            assignments = [str(image_path)]
            cached_images = pick_cache_images(image_path, desktop_count - 1)
            assignments.extend(str(cached) for cached in cached_images)
            assignments.extend(
                str(image_path) for _ in range(desktop_count - len(assignments))
            )

            subprocess.run(
                ['osascript', '-e', script, *assignments],
                check=True, capture_output=True, text=True
            )
            for idx, path in enumerate(assignments, start=1):
                print(f"Desktop {idx}: {Path(path).name}")
            return
        except (subprocess.CalledProcessError, RuntimeError, ValueError) as e:
            if attempt < DESKTOP_ATTEMPTS:
                print(f"Could not set the wallpaper: {e}")
                print(f"Retrying in {DESKTOP_RETRY_DELAY_SECONDS} seconds...")
                time.sleep(DESKTOP_RETRY_DELAY_SECONDS)
                continue
            print(f"Error setting wallpaper: {e}")
            sys.exit(1)


def send_notification(title, description):
    """Send a macOS notification with the APOD details"""
    try:
        # Truncate description to first 200 chars or first sentence
        desc_short = description[:200]
        if len(description) > 200:
            # Try to end at a sentence
            last_period = desc_short.rfind('. ')
            if last_period > 100:  # Only truncate at sentence if it's reasonable length
                desc_short = desc_short[:last_period + 1]
            else:
                desc_short += "..."

        # Try terminal-notifier first (if installed via Homebrew)
        try:
            subprocess.run([
                'terminal-notifier',
                '-title', 'NASA APOD',
                '-subtitle', title,
                '-message', desc_short,
                '-sound', 'default'
            ], check=True, capture_output=True)
            return
        except FileNotFoundError:
            # Fall back to AppleScript if terminal-notifier not installed
            pass

        # Fallback: AppleScript notification
        title_escaped = title.replace('\\', '\\\\').replace('"', '\\"')
        desc_escaped = desc_short.replace('\\', '\\\\').replace('"', '\\"')
        script = f'''
        display notification "{desc_escaped}" with title "NASA APOD" subtitle "{title_escaped}"
        '''
        subprocess.run(['osascript', '-e', script], check=True)
    except Exception as e:
        # Don't fail if notification fails
        print(f"Note: Could not send notification: {e}")


def cleanup_old_images(keep_count=30):
    """Remove old APOD images, keeping only the most recent ones"""
    try:
        image_files = cached_image_files()

        if len(image_files) <= keep_count:
            return  # Nothing to clean up

        # Sort by modification time (newest first)
        image_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)

        # Delete older files beyond keep_count
        files_to_delete = image_files[keep_count:]
        deleted_count = 0

        for old_file in files_to_delete:
            try:
                old_file.unlink()
                deleted_count += 1
            except Exception as e:
                print(f"Warning: Could not delete {old_file.name}: {e}")

        if deleted_count > 0:
            print(f"\nCleaned up {deleted_count} old wallpaper(s)")
    except Exception as e:
        print(f"Warning: Error during cleanup: {e}")


def backfill(days):
    """Download the last N days of APODs without setting wallpaper or notifying."""
    print("=" * 60)
    print(f"NASA APOD Backfill - last {days} days")
    print("=" * 60)

    downloaded = 0
    skipped_existing = 0
    skipped_video = 0
    failed = 0

    for offset in range(days):
        date_str = (datetime.now() - timedelta(days=offset)).strftime('%Y-%m-%d')

        # Skip dates we already have cached (any extension)
        existing = [
            path for path in cached_image_files()
            if path.stem == f"apod_{date_str}"
        ]
        if existing:
            skipped_existing += 1
            continue

        data = fetch_apod_data(date_str, exit_on_error=False)
        if data is None:
            failed += 1
            continue

        if data.get('media_type') != 'image':
            print(f"  {date_str}: skipping ({data.get('media_type')})")
            skipped_video += 1
            continue

        result = download_apod_image(data, date_str, exit_on_error=False)
        if result is None:
            failed += 1
        else:
            downloaded += 1

    print("\n" + "=" * 60)
    print(f"Backfill complete: {downloaded} downloaded, "
          f"{skipped_existing} already cached, "
          f"{skipped_video} non-image, "
          f"{failed} failed")
    print("=" * 60)

    cleanup_old_images(keep_count=30)


def main():
    print("=" * 60)
    print("NASA Astronomy Picture of the Day - Wallpaper Setter")
    print("=" * 60)

    # Backfill mode
    if len(sys.argv) > 1 and sys.argv[1] == "--backfill":
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
        backfill(days)
        return

    # Get date from command line argument if provided
    date = None
    if len(sys.argv) > 1:
        date = sys.argv[1]
        print(f"Requesting APOD for date: {date}")

    # Fetch APOD data (with fallback to yesterday if today isn't available)
    apod_data = fetch_apod_with_fallback(date)

    # Display info about today's APOD
    print(f"\nTitle: {apod_data.get('title', 'N/A')}")
    print(f"Date: {apod_data.get('date', 'N/A')}")
    print(f"Media Type: {apod_data.get('media_type', 'N/A')}")

    # Check if it's an image (not a video)
    if apod_data.get('media_type') != 'image':
        print("\nToday's APOD is not an image (it might be a video).")
        print(f"URL: {apod_data.get('url', 'N/A')}")
        print("Cannot set as wallpaper. Please try again tomorrow!")
        sys.exit(0)

    date_str = apod_data.get('date', datetime.now().strftime('%Y-%m-%d'))

    image_path = download_apod_image(apod_data, date_str, exit_on_error=False)
    cleanup_old_images(keep_count=30)

    if image_path is None:
        print("The wallpaper was not changed.")
        sys.exit(1)

    set_macos_wallpaper(image_path)

    title = apod_data.get('title', 'NASA APOD')
    description = apod_data.get('explanation', '')
    send_notification(title, description)

    print("\n" + "=" * 60)
    print("Description:")
    print(apod_data.get('explanation', 'N/A'))
    print("=" * 60)


if __name__ == "__main__":
    main()
