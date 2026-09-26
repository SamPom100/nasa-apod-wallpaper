#!/usr/bin/env python3
"""
NASA APOD Desktop Background Setter
Fetches the Astronomy Picture of the Day and sets it as macOS desktop background
"""

import os
import sys
import copy
import json
import plistlib
import random
import time
import urllib.request
import urllib.error
import urllib.parse
from html.parser import HTMLParser
from pathlib import Path
import subprocess
import tempfile
from datetime import datetime, timedelta

# Directory to store downloaded wallpapers and config
WALLPAPER_DIR = Path.home() / ".nasa_apod_wallpapers"
WALLPAPER_DIR.mkdir(exist_ok=True)

CONFIG_FILE = WALLPAPER_DIR / "config.json"
WALLPAPER_STORE_INDEX = Path.home() / "Library/Application Support/com.apple.wallpaper/Store/Index.plist"

FETCH_ATTEMPTS = 6
FETCH_RETRY_DELAY_SECONDS = 60
DOWNLOAD_TIMEOUT_SECONDS = 30
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
        with urllib.request.urlopen(url, timeout=DOWNLOAD_TIMEOUT_SECONDS) as response:
            temporary_path.write_bytes(response.read())
        if not is_valid_image(temporary_path):
            raise ValueError("The download is not a valid image")
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


def is_valid_image(path):
    try:
        result = subprocess.run(
            ['/usr/bin/sips', '-g', 'pixelWidth', '-g', 'pixelHeight', str(path)],
            check=True, capture_output=True, text=True, timeout=10,
        )
        dimensions = [
            line.split(':', 1)[1].strip()
            for line in result.stdout.splitlines()
            if line.strip().startswith(('pixelWidth:', 'pixelHeight:'))
        ]
        return len(dimensions) == 2 and all(
            value.isdecimal() and int(value) > 0 for value in dimensions
        )
    except (OSError, subprocess.SubprocessError):
        return False


def cached_image_files():
    """Return cached APOD image files."""
    return [
        path for path in WALLPAPER_DIR.glob("apod_*")
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
        and is_valid_image(path)
    ]


def pick_cache_images(exclude_path, count):
    """Pick distinct cached APOD images, excluding the given path."""
    today = datetime.now().strftime('%Y-%m-%d')
    candidates = [path for path in cached_image_files() if path.stem != f'apod_{today}']
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


def get_desktop_contexts():
    script = '''
    ObjC.import('Foundation');
    ObjC.import('ColorSync');
    var displayUUIDs = Application('System Events').desktops().map(function (display) {
        var uuid = $.CGDisplayCreateUUIDFromDisplayID(display.id());
        return ObjC.unwrap(ObjC.castRefToObject($.CFUUIDCreateString(null, uuid)));
    });
    var prefs = ObjC.deepUnwrap(
        $.NSUserDefaults.standardUserDefaults.persistentDomainForName('com.apple.spaces')
    );
    JSON.stringify({
        display_uuids: displayUUIDs,
        monitors: prefs.SpacesDisplayConfiguration['Management Data'].Monitors
    });
    '''
    try:
        result = subprocess.run(
            ['/usr/bin/osascript', '-l', 'JavaScript', '-e', script],
            check=True, capture_output=True, text=True, timeout=10,
        )
        data = json.loads(result.stdout)
        contexts = []
        for display_uuid in data['display_uuids']:
            monitor = None
            for identifier in (display_uuid, 'Main'):
                monitor = next((
                    item for item in data['monitors']
                    if item.get('Display Identifier') == identifier and item.get('Spaces')
                ), None)
                if monitor is not None:
                    break
            if monitor is None:
                raise ValueError('A display has no Space information')
            normal_spaces = [space for space in monitor['Spaces'] if space.get('type', 0) == 0]
            if not normal_spaces:
                raise ValueError('A display has no normal desktops')
            for space in normal_spaces:
                context = {
                    'display_uuid': display_uuid,
                    'space_uuid': space['uuid'],
                    'current_space_uuid': monitor['Current Space']['uuid'],
                }
                if not display_uuid or not all(isinstance(value, str) for value in context.values()):
                    raise ValueError('The desktop identifiers are invalid')
                contexts.append(context)
        return contexts
    except Exception as error:
        print(f"Cannot identify the desktops: {error}")
    return []


DEFAULT_WALLPAPER_CONFIGURATION = {
    'backgroundColor': {
        'components': [0.2549019607843137, 0.4117647058823529, 0.6666666666666666, 1.0],
        'colorSpace': b'bplist00_\x10\x17kCGColorSpaceGenericRGB\x08\x00\x00\x00\x00\x00\x00\x01\x01\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"'
    },
    'placement': 1,
}


def set_wallpapers_in_store(assignments):
    if not assignments or not WALLPAPER_STORE_INDEX.exists():
        return False
    temporary_path = None
    try:
        with open(WALLPAPER_STORE_INDEX, "rb") as f:
            data = plistlib.load(f)
        for context, image_path in assignments:
            space = data['Spaces'][context['space_uuid']]
            display = copy.deepcopy(space.get('Displays', {}).get(context['display_uuid'], {}))
            desktop = display.get('Desktop') or copy.deepcopy(space.get('Default', {}).get('Desktop'))
            if not desktop or not desktop.get('Content', {}).get('Choices'):
                return False
            url = Path(image_path).resolve().as_uri()
            cfg_dict = copy.deepcopy(DEFAULT_WALLPAPER_CONFIGURATION)
            existing_choices = desktop.get('Content', {}).get('Choices', [])
            if existing_choices and existing_choices[0].get('Configuration'):
                try:
                    loaded = plistlib.loads(existing_choices[0]['Configuration'])
                    if isinstance(loaded, dict):
                        cfg_dict.update(loaded)
                except Exception:
                    pass
            cfg_dict['type'] = 'imageFile'
            cfg_dict['url'] = {'relative': url}
            desktop['Content']['Choices'] = [{
                'Provider': 'com.apple.wallpaper.choice.image',
                'Files': [{'relative': url}],
                'Configuration': plistlib.dumps(cfg_dict, fmt=plistlib.FMT_BINARY),
            }]
            display['Desktop'] = desktop
            space.setdefault('Displays', {})[context['display_uuid']] = display
            if 'Displays' in data and context['display_uuid'] in data['Displays']:
                data['Displays'][context['display_uuid']]['Desktop'] = copy.deepcopy(desktop)
        contents = plistlib.dumps(data, fmt=plistlib.FMT_BINARY)
        with tempfile.NamedTemporaryFile(dir=WALLPAPER_STORE_INDEX.parent, delete=False) as f:
            temporary_path = Path(f.name)
            os.fchmod(f.fileno(), WALLPAPER_STORE_INDEX.stat().st_mode & 0o777)
            f.write(contents)
        temporary_path.replace(WALLPAPER_STORE_INDEX)
        subprocess.run(['/usr/bin/killall', 'WallpaperAgent'], check=False, timeout=10)
        return True
    except Exception as error:
        print(f"Cannot update the wallpaper store: {error}")
        return False
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def load_wallpaper_state():
    try:
        state = json.loads((WALLPAPER_DIR / 'wallpaper_state.json').read_text())
        if (not isinstance(state, dict)
                or not isinstance(state.get('date'), (str, type(None)))
                or not isinstance(state.get('primary'), (str, type(None)))
                or not isinstance(state.get('desktops', {}), dict)):
            raise ValueError('Invalid wallpaper state')
        for entry in state.get('desktops', {}).values():
            if (not isinstance(entry, dict)
                    or not isinstance(entry.get('path'), str)
                    or not isinstance(entry.get('date'), (str, type(None)))):
                raise ValueError('Invalid desktop assignment')
        return state
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as error:
        print(f"Cannot read the saved wallpaper choices: {error}")
        return {}


def save_wallpaper_state(state):
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', dir=WALLPAPER_DIR, delete=False) as output:
            temporary_path = Path(output.name)
            json.dump(state, output, indent=2)
            output.write('\n')
        temporary_path.replace(WALLPAPER_DIR / 'wallpaper_state.json')
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def set_macos_wallpaper(image_path, desktop_1_only=False, apod_date=None, shuffle=False):
    """Set the macOS desktop wallpaper (desktop 1 only, or all desktops)."""
    state = load_wallpaper_state()
    if apod_date is None:
        apod_date = state.get('date')
    desktops = state.setdefault('desktops', {})
    for attempt in range(1, DESKTOP_ATTEMPTS + 1):
        try:
            contexts = get_desktop_contexts()
            if not contexts:
                raise RuntimeError("No macOS desktops are available")
            assignments = [(contexts[0], image_path)]
            if not desktop_1_only and len(contexts) > 1:
                cached_images = pick_cache_images(image_path, None)
                if cached_images:
                    candidates = {str(path.resolve()): path for path in cached_images}
                    used = {entry['path'] for entry in desktops.values()
                            if not shuffle and entry.get('date') == apod_date
                            and entry['path'] in candidates}
                    for context in contexts[1:]:
                        key = context['display_uuid'] + '/' + context['space_uuid']
                        previous = desktops.get(key, {})
                        path = previous.get('path')
                        if shuffle or previous.get('date') != apod_date or path not in candidates:
                            available = [item for item in candidates if item not in used and item != path]
                            available = available or [item for item in candidates if item != path] or list(candidates)
                            path = available[0]
                        desktops[key] = {'date': apod_date, 'path': path}
                        used.add(path)
                        assignments.append((context, candidates[path]))
                else:
                    print("No other cached image is available. Other desktops keep their wallpaper.")
            shuffle = False
            if not set_wallpapers_in_store(assignments):
                raise RuntimeError("The wallpaper store update failed")
            state.update(date=apod_date, primary=str(Path(image_path).resolve()))
            save_wallpaper_state(state)
            for index, (_, path) in enumerate(assignments, start=1):
                print(f"Desktop {index}: {Path(path).name}")
            return
        except (OSError, subprocess.CalledProcessError, RuntimeError, ValueError) as e:
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
        image_files = [
            path for path in WALLPAPER_DIR.glob("apod_*")
            if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
        ]

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
    cached_dates = {path.stem for path in cached_image_files()}

    for offset in range(days):
        date_str = (datetime.now() - timedelta(days=offset)).strftime('%Y-%m-%d')

        # Skip dates we already have cached (any extension)
        if f"apod_{date_str}" in cached_dates:
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
    contexts = get_desktop_contexts()
    if not contexts:
        return None
    context = contexts[0]
    if WALLPAPER_STORE_INDEX.exists():
        try:
            with open(WALLPAPER_STORE_INDEX, "rb") as f:
                data = plistlib.load(f)
            space = data['Spaces'][context['space_uuid']]
            desktop = space.get('Displays', {}).get(context['display_uuid'], {}).get('Desktop')
            desktop = desktop or space.get('Default', {}).get('Desktop', {})
            choices = desktop.get('Content', {}).get('Choices', [])
            if choices:
                configuration = plistlib.loads(choices[0]['Configuration'])
                if configuration.get('type') != 'imageFile':
                    return None
                url = urllib.parse.urlparse(configuration['url']['relative'])
                if url.scheme == 'file':
                    return Path(urllib.parse.unquote(url.path))
        except Exception:
            pass

    if context['space_uuid'] != context['current_space_uuid']:
        return None
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

    state = load_wallpaper_state()

    # Shuffle / Random cached wallpaper mode
    if "--shuffle" in sys.argv or "--random" in sys.argv:
        print("\nPicking a random wallpaper from the cache...")
        current_wallpaper = get_current_desktop_1_wallpaper()
        image_path = pick_random_cached_wallpaper(exclude_paths=[current_wallpaper])
        if image_path is None:
            print("Error: No cached wallpapers available.")
            sys.exit(1)
        print(f"Selected cached wallpaper: {image_path.name}")
        set_macos_wallpaper(image_path, desktop_1_only=desktop_1_only,
                            apod_date=state.get('date') or datetime.now().strftime('%Y-%m-%d'),
                            shuffle=True)
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

    if date is None and not force_update:
        cached_image = next(
            (path for path in cached_image_files() if path.stem == f"apod_{today_str}"),
            None,
        )
        if cached_image is not None:
            if desktop_1_only:
                current_wallpaper = get_current_desktop_1_wallpaper()
                if current_wallpaper and cached_image.resolve() == current_wallpaper.resolve():
                    print(f"Today's APOD ({today_str}) is already set as Desktop 1 wallpaper.")
                    return
            print(f"Using the cached APOD for {today_str}.")
            set_macos_wallpaper(cached_image, desktop_1_only=desktop_1_only, apod_date=today_str)
            return

    # Fetch APOD data (with fallback to yesterday if today isn't available)
    apod_data = fetch_apod_with_fallback(date, exit_on_error=False)
    if (date is None and apod_data and state.get('date')
            and apod_data.get('date', today_str) < state['date']):
        apod_data = None

    image_path = None
    target_date = date or today_str
    apod_date = apod_data.get('date', target_date) if apod_data else state.get('date')

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
    reused_fallback = False
    if image_path is None:
        saved_primary = state.get('primary')
        if state.get('date') == apod_date and saved_primary:
            image_path = next((path for path in cached_image_files()
                               if str(path.resolve()) == saved_primary), None)
            reused_fallback = image_path is not None
        if image_path is None:
            print("\nSelect an older random wallpaper from the cache.")
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

    set_macos_wallpaper(image_path, desktop_1_only=desktop_1_only, apod_date=apod_date)

    if reused_fallback:
        return

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
