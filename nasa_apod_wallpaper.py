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


def load_config():
    """Load configuration dictionary from config file."""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Warning: Could not read config file: {e}")
    return {}


def load_api_key(config=None):
    """Load API key from config file or environment variable"""
    # First try environment variable
    api_key = os.environ.get("NASA_API_KEY")
    if api_key:
        return api_key

    # Then try config dict
    if config and config.get('api_key'):
        return config.get('api_key')

    # Then try config file
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r') as f:
                cfg = json.load(f)
                api_key = cfg.get('api_key')
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
        api_key = input("\nEnter your NASA API key (press Enter to use DEMO_KEY, or Ctrl+C to exit): ").strip()
        if not api_key:
            api_key = "DEMO_KEY"
        current_cfg = load_config()
        current_cfg["api_key"] = api_key
        # Save it to config file
        with open(CONFIG_FILE, 'w') as f:
            json.dump(current_cfg, f, indent=2)
        print(f"\nAPI key saved to {CONFIG_FILE}")
        return api_key
    except (KeyboardInterrupt, EOFError):
        print("\nSetup cancelled.")

    sys.exit(1)


# Load API key
CONFIG = load_config()
NASA_API_KEY = load_api_key(CONFIG)
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


def fetch_apod_data(date=None, exit_on_error=True, max_attempts=FETCH_ATTEMPTS):
    """Fetch the APOD metadata from NASA API. Returns data dict, or None on failure if exit_on_error=False."""
    url = APOD_API_URL
    if date:
        url += f"&date={date}"

    for attempt in range(1, max_attempts + 1):
        try:
            print(f"Fetching NASA APOD data{f' for {date}' if date else ''}...", flush=True)
            with urllib.request.urlopen(url, timeout=10) as response:
                return json.loads(response.read().decode())
        except urllib.error.HTTPError as e:
            print(f"HTTP Error {e.code}: {e.reason}", flush=True)
            if e.code == 429:
                print("Rate limit reached on NASA API. Skipping retries to use cache fallback.", flush=True)
                retry = False
            else:
                retry = e.code in {500, 502, 503, 504}
        except urllib.error.URLError as e:
            print(f"Error fetching APOD data: {e}", flush=True)
            retry = True
        except Exception as e:
            print(f"Unexpected error: {e}", flush=True)
            retry = True

        if retry and attempt < max_attempts:
            print(f"Retrying in {FETCH_RETRY_DELAY_SECONDS} seconds...", flush=True)
            time.sleep(FETCH_RETRY_DELAY_SECONDS)
            continue

        if exit_on_error:
            sys.exit(1)
        return None


def fetch_apod_with_fallback(date=None, exit_on_error=True):
    """Fetch APOD data with fallback to yesterday if today isn't available"""
    if date:
        return fetch_apod_data(date, exit_on_error=exit_on_error)

    today = datetime.now().strftime('%Y-%m-%d')
    data = fetch_apod_data(today, exit_on_error=False)
    if data is not None:
        return data

    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    print(f"Could not fetch today's APOD, fetching yesterday ({yesterday})...")
    return fetch_apod_data(yesterday, exit_on_error=exit_on_error)


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


def pick_random_cached_wallpaper(exclude_paths=None, exclude_date=None):
    """Pick a random cached APOD image, preferring older ones not currently displayed."""
    candidates = cached_image_files()
    if not candidates:
        return None

    if exclude_date is None:
        exclude_date = datetime.now().strftime('%Y-%m-%d')

    try:
        target_dt = datetime.strptime(exclude_date, '%Y-%m-%d')

        def is_older(p):
            try:
                p_date_str = p.stem.replace("apod_", "")
                return datetime.strptime(p_date_str, '%Y-%m-%d') < target_dt
            except ValueError:
                return not p.stem.startswith(f"apod_{exclude_date}")

        older_candidates = [p for p in candidates if is_older(p)]
    except ValueError:
        date_prefix = f"apod_{exclude_date}"
        older_candidates = [p for p in candidates if not p.stem.startswith(date_prefix)]

    if older_candidates:
        candidates = older_candidates

    if exclude_paths:
        if isinstance(exclude_paths, (str, Path)):
            exclude_paths = [exclude_paths]
        exclude_resolved = {Path(p).resolve() for p in exclude_paths if p is not None}
        filtered = [p for p in candidates if p.resolve() not in exclude_resolved]
        if filtered:
            candidates = filtered

    return random.choice(candidates)


def set_macos_wallpaper(image_path, desktop_1_only=False):
    """Set the macOS desktop wallpaper (desktop 1 only, or all desktops)."""
    if desktop_1_only:
        script = '''
        on run argv
            set imagePath to item 1 of argv
            tell application "System Events"
                set picture of desktop 1 to imagePath
            end tell
        end run
        '''
    else:
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

            if desktop_1_only:
                subprocess.run(
                    ['osascript', '-e', script, str(image_path)],
                    check=True, capture_output=True, text=True
                )
                print(f"Desktop 1: {Path(image_path).name}")
            else:
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
    print("=" * 60, flush=True)
    print(f"NASA APOD Backfill - last {days} days", flush=True)
    print("=" * 60, flush=True)

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
            print(f"  {date_str}: already cached", flush=True)
            skipped_existing += 1
            continue

        # Try API first without retrying repeatedly if rate-limited
        data = fetch_apod_data(date_str, exit_on_error=False, max_attempts=1)
        if data is not None:
            if data.get('media_type') != 'image':
                print(f"  {date_str}: skipping ({data.get('media_type')})", flush=True)
                skipped_video += 1
                continue

            result = download_apod_image(data, date_str, exit_on_error=False)
            if result is not None:
                downloaded += 1
                continue

        # Fallback to APOD website directly if API is unavailable, rate-limited, or failed
        page_url = fetch_apod_page_image_url(date_str)
        if page_url:
            filename = f"apod_{date_str}{image_extension(page_url)}"
            result = download_image(page_url, filename, exit_on_error=False)
            if result is not None:
                downloaded += 1
            else:
                failed += 1
        else:
            print(f"  {date_str}: skipping (non-image or unavailable)", flush=True)
            skipped_video += 1

    print("\n" + "=" * 60, flush=True)
    print(f"Backfill complete: {downloaded} downloaded, "
          f"{skipped_existing} already cached, "
          f"{skipped_video} non-image, "
          f"{failed} failed", flush=True)
    print("=" * 60, flush=True)

    cleanup_old_images(keep_count=max(30, days))


def get_current_desktop_1_wallpaper():
    """Return the Path to the current wallpaper set on desktop 1, or None."""
    try:
        result = subprocess.run(
            ['osascript', '-e', 'tell application "System Events" to get picture of desktop 1'],
            capture_output=True, text=True, check=True
        )
        output = result.stdout.strip()
        return Path(output) if output else None
    except Exception:
        return None


def main():
    print("=" * 60)
    print("NASA Astronomy Picture of the Day - Wallpaper Setter")
    print("=" * 60)

    # Backfill mode
    if len(sys.argv) > 1 and sys.argv[1] == "--backfill":
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
        backfill(days)
        return

    # Configuration and options
    config = load_config()
    desktop_1_only = config.get("desktop_1_only", False)
    if "--desktop-1-only" in sys.argv:
        desktop_1_only = True
    elif "--all-desktops" in sys.argv:
        desktop_1_only = False

    # Shuffle / Random cached wallpaper mode
    if "--shuffle" in sys.argv or "--random" in sys.argv:
        print("\nPicking a random wallpaper from the cache...")
        current_wallpaper = get_current_desktop_1_wallpaper()
        image_path = pick_random_cached_wallpaper(exclude_paths=[current_wallpaper])
        if image_path is None:
            print("Error: No cached wallpapers available.")
            sys.exit(1)
        print(f"Selected cached wallpaper: {image_path.name}")
        set_macos_wallpaper(image_path, desktop_1_only=desktop_1_only)
        send_notification(f"NASA APOD (Shuffled: {image_path.name})", f"Set {image_path.name} as wallpaper.")
        return

    # Check for --force flag
    force_update = "--force" in sys.argv
    args = [
        arg for arg in sys.argv[1:]
        if arg not in ("--force", "--desktop-1-only", "--all-desktops", "--shuffle", "--random")
    ]

    # Get date from command line argument if provided
    date = None
    if args:
        date = args[0]
        print(f"Requesting APOD for date: {date}")

    today_str = datetime.now().strftime('%Y-%m-%d')

    # If running for today without --force, check if already downloaded & set
    if date is None and not force_update:
        current_wallpaper = get_current_desktop_1_wallpaper()
        today_files = [
            path for path in cached_image_files()
            if path.stem == f"apod_{today_str}"
        ]
        if today_files and current_wallpaper and today_files[0].resolve() == current_wallpaper.resolve():
            print(f"Today's APOD ({today_str}) is already set as Desktop 1 wallpaper.")
            return

    # Fetch APOD data (with fallback to yesterday if today isn't available)
    apod_data = fetch_apod_with_fallback(date, exit_on_error=False)

    image_path = None
    target_date = date or today_str

    if apod_data is not None:
        # Display info about APOD
        print(f"\nTitle: {apod_data.get('title', 'N/A')}")
        print(f"Date: {apod_data.get('date', 'N/A')}")
        print(f"Media Type: {apod_data.get('media_type', 'N/A')}")

        target_date = apod_data.get('date', target_date)

        # Check if it's an image (not a video)
        if apod_data.get('media_type') == 'image':
            image_path = download_apod_image(apod_data, target_date, exit_on_error=False)
            if image_path is None:
                print("Could not download today's APOD image.")
        else:
            prefix = "The requested" if date else "Today's"
            print(f"\n{prefix} APOD is not an image (it might be a video).")
            print(f"URL: {apod_data.get('url', 'N/A')}")
    else:
        print(f"Could not fetch APOD data{f' for {date}' if date else ''}.")

    used_cached_fallback = False
    if image_path is None:
        print("\nPicking an older random wallpaper from the cache...")
        current_wallpaper = get_current_desktop_1_wallpaper()
        image_path = pick_random_cached_wallpaper(
            exclude_paths=[current_wallpaper],
            exclude_date=target_date,
        )
        if image_path is None:
            print("Error: No cached wallpapers available to use as fallback.")
            print("The wallpaper was not changed.")
            sys.exit(1)
        used_cached_fallback = True
        print(f"Selected cached wallpaper: {image_path.name}")
    else:
        cleanup_old_images(keep_count=30)

    set_macos_wallpaper(image_path, desktop_1_only=desktop_1_only)

    if used_cached_fallback:
        if apod_data and apod_data.get('media_type') != 'image':
            title = f"{apod_data.get('title', 'NASA APOD')} (Video - Cached Wallpaper)"
            description = apod_data.get('explanation') or f"Today's APOD is not an image. Set {image_path.name} from cache."
        elif apod_data:
            title = f"{apod_data.get('title', 'NASA APOD')} (Cached Wallpaper)"
            description = apod_data.get('explanation') or f"Download failed. Set {image_path.name} from cache."
        else:
            title = f"NASA APOD (Cached: {image_path.name})"
            description = "Could not fetch APOD. Set a random wallpaper from cache."

        send_notification(title, description)

        if apod_data and apod_data.get('explanation'):
            print("\n" + "=" * 60)
            print("Description:")
            print(apod_data.get('explanation'))
            print("=" * 60)
    else:
        title = apod_data.get('title', 'NASA APOD')
        description = apod_data.get('explanation', '')
        send_notification(title, description)

        print("\n" + "=" * 60)
        print("Description:")
        print(apod_data.get('explanation', 'N/A'))
        print("=" * 60)


if __name__ == "__main__":
    main()
