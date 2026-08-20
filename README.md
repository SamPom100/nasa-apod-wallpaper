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
- 🧠 Smart fallback: tries today, uses yesterday if not available yet
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

**Note:** The script automatically keeps only the 30 most recent wallpapers to save disk space.

## Uninstall

```bash
# Remove LaunchAgent
launchctl unload ~/Library/LaunchAgents/com.nasa.apod.wallpaper.plist
rm ~/Library/LaunchAgents/com.nasa.apod.wallpaper.plist

# Remove downloaded images and config
rm -rf ~/.nasa_apod_wallpapers/
```

## Troubleshooting

### "Today's APOD not available yet"
The NASA API can be unreliable when fetching the current day's image. The script automatically falls back to yesterday's image if today's fails. This ensures the script always works reliably.

### "Today's APOD is not an image"
Sometimes NASA posts videos instead of images. The script will notify you and skip setting the wallpaper.

### Check Logs
```bash
tail -f ~/.nasa_apod_wallpapers/apod.log
```

## Requirements

- macOS (uses AppleScript for wallpaper setting)
- Python 3.6+
- Internet connection
- Free NASA API key

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
