# NASA APOD Desktop Wallpaper

Automatically set NASA's Astronomy Picture of the Day as your macOS desktop wallpaper.

![NASA APOD](https://apod.nasa.gov/apod/image/2603/cg4_1024.jpg)

## Features

- 🚀 Fetches NASA's daily Astronomy Picture of the Day
- 🖼️ Downloads high-resolution images
- Uses the APOD webpage when the API full-resolution link fails
- Never uses the lower-resolution API display image
- 💻 Automatically sets as macOS desktop background
- 📅 Can fetch images from specific dates
- ⏰ Optional daily auto-update via LaunchAgent
- 🧠 Smart fallback: tries today, uses yesterday if not available yet, or selects a random cached wallpaper if today's APOD fails or is a video
- 🧹 Auto-cleanup keeps only the last 30 wallpapers
- 🔔 System notifications with image title and description
- 📝 Shows full image details in terminal

## Quick Start

### 1. Get a NASA API Key (Free!)

1. Visit https://api.nasa.gov/
2. Enter your name and email
3. Copy your API key

### 2. Run Setup

```bash
./setup.sh
```

The setup script will:
- Install Python dependencies (none required - uses standard library!)
- Prompt for your NASA API key
- Set up the daily auto-update (optional)

### 3. Manual Usage

Run once to set today's APOD as wallpaper:
```bash
python3 nasa_apod_wallpaper.py
```

Get APOD from a specific date:
```bash
python3 nasa_apod_wallpaper.py 2024-12-25
```

Shuffle to a random cached wallpaper:
```bash
python3 nasa_apod_wallpaper.py --shuffle
```

Backfill previous wallpapers to cache:
```bash
python3 nasa_apod_wallpaper.py --backfill 30
```

### Refresh After Laptop Wake, Unlock, or Display Changes

If the daily LaunchAgent is absent, enable it through `./setup.sh`.
Then install the wake listener:

```bash
./install_wake.sh
```

The listener requests an update when the display wakes, the screen unlocks, or the display configuration changes.
This includes a display wake after you open the laptop lid.
After a locked wake, the unlock event gives the updater another chance to access the desktops.
Display changes also trigger an update when an external monitor connects or becomes available.
The listener waits five seconds after the last event so that the display configuration can settle.

Today's APOD goes only to Desktop 1, the first normal Space on the first display.
Other desktops receive random cached images, including other Spaces on the same display.
Each random image stays the same until the updater detects a new APOD date.
Wake, unlock, and display events reuse the saved choices, including after a restart.

If APOD is a video or its image fails, Desktop 1 also uses a saved random image.
If NASA is unavailable, the updater keeps the existing choices until it receives a new APOD entry.
If a saved image disappears from the cache, the updater replaces that image.

`--shuffle` selects new random images immediately. `--force` fetches APOD again and preserves the other desktop choices for that APOD date.
After `--shuffle`, the next automatic refresh restores APOD on Desktop 1 and keeps the other random choices.

The `desktop_1_only` configuration limits updates to Desktop 1.
If today's image is cached, the updater reuses it without a download.
Otherwise, the updater fetches today's APOD through the existing workflow.

The listener uses the existing daily LaunchAgent.
If that updater is active, the listener retains the request and retries after the updater exits.
The installer requires the Xcode Command Line Tools and preserves the daily schedule.

To update an existing installation, run these commands from the repository:

```bash
git pull --ff-only
./install_wake.sh
```

The installer rebuilds and restarts the listener with the updated code.

## Installation

### Method 1: Simple (No auto-update)

```bash
# Clone or download this repository
git clone <your-repo-url>
cd nasa-apod-wallpaper

# Run the script
python3 nasa_apod_wallpaper.py
```

### Method 2: With Daily Auto-Update

```bash
# Run the setup script
./setup.sh

# Or manually set up LaunchAgent:
cp com.nasa.apod.wallpaper.plist ~/Library/LaunchAgents/
# Edit the plist to use your home directory path
launchctl load ~/Library/LaunchAgents/com.nasa.apod.wallpaper.plist
```

## iPhone Shortcut

`APOD_Wallpaper.shortcut` sets today's APOD as the iPhone wallpaper. It does not use an API key.

1. AirDrop `APOD_Wallpaper.shortcut` to the iPhone.
2. Tap **Add Shortcut**.
3. If iOS asks for a wallpaper, select the wallpaper that the shortcut must replace.
4. Optional: Add a daily automation in the Shortcuts app that runs the shortcut.

The shortcut reads the image link from the APOD webpage. It downloads the image from `assets.science.nasa.gov`, because NASA is moving APOD to `science.nasa.gov/apod`.

## Configuration

The script will prompt for your API key on first run and save it to:
```
~/.nasa_apod_wallpapers/config.json
```

Alternatively, set an environment variable:
```bash
export NASA_API_KEY="your_key_here"
```

## File Locations

- **Downloaded images**: `~/.nasa_apod_wallpapers/`
- **Configuration**: `~/.nasa_apod_wallpapers/config.json`
- **Logs**: `~/.nasa_apod_wallpapers/apod.log`
- **Wake listener log**: `~/.nasa_apod_wallpapers/wake.log`

**Note:** The script automatically keeps only the 30 most recent wallpapers to save disk space.

## Uninstall

```bash
# Remove LaunchAgent
launchctl bootout gui/$(id -u)/com.nasa.apod.wallpaper.wake
rm -f ~/Library/LaunchAgents/com.nasa.apod.wallpaper.wake.plist
launchctl unload ~/Library/LaunchAgents/com.nasa.apod.wallpaper.plist
rm ~/Library/LaunchAgents/com.nasa.apod.wallpaper.plist

# Remove downloaded images and config
rm -rf ~/.nasa_apod_wallpapers/
```

## Troubleshooting

### "Today's APOD not available yet"
If NASA does not provide today's entry, the updater tries yesterday's entry.
The random images change only when the updater receives a new APOD date.
If both requests fail, the updater reuses its saved choices.

### "Today's APOD is not an image" or Download Fails
If APOD is a video or its image download fails, the updater selects a random cached image for Desktop 1.
Repeated refreshes reuse that image and the random choices for other desktops.
If the image download later succeeds, Desktop 1 uses APOD and the other desktops keep their choices until the next APOD date.

### Check Logs
```bash
tail -f ~/.nasa_apod_wallpapers/apod.log
```

## Requirements

- macOS (uses AppleScript for wallpaper setting)
- Python 3.6+
- Internet connection
- Free NASA API key
- Xcode Command Line Tools for optional updates after display wake or screen unlock

## How It Works

1. Fetches metadata from NASA's APOD API
2. Downloads the high-resolution image
3. Saves to `~/.nasa_apod_wallpapers/`
4. Uses AppleScript to set as desktop background
5. Displays the image title and description

## API Rate Limits

- Free API key: 1000 requests/hour
- Demo key: 30 requests/hour

More than enough for daily updates!

## Credits

- Images and data provided by [NASA's APOD](https://apod.nasa.gov/)
- Built with ❤️ using Python

## License

MIT License - Feel free to use and modify!

## Contributing

Pull requests welcome! Ideas for improvements:
- Support for multiple monitors
- Image filtering options
- Support for Linux/Windows
- GUI interface
