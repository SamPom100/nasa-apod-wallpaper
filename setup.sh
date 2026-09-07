#!/bin/bash
# NASA APOD Wallpaper Setup Script

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
WALLPAPER_DIR="$HOME/.nasa_apod_wallpapers"
CONFIG_FILE="$WALLPAPER_DIR/config.json"
LAUNCHAGENT_PLIST="com.nasa.apod.wallpaper.plist"
LAUNCHAGENT_PATH="$HOME/Library/LaunchAgents/$LAUNCHAGENT_PLIST"

echo "════════════════════════════════════════════════════════════"
echo "  NASA APOD Desktop Wallpaper - Setup"
echo "════════════════════════════════════════════════════════════"
echo ""

# Create wallpaper directory
mkdir -p "$WALLPAPER_DIR"

# Check if config already exists
if [ -f "$CONFIG_FILE" ]; then
    echo "✓ Configuration already exists at $CONFIG_FILE"
    echo ""
    read -p "Do you want to update your API key? (y/N): " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        SKIP_API_KEY=true
    fi
fi

# Get API key if needed
if [ -z "$SKIP_API_KEY" ]; then
    echo "Step 1: NASA API Key"
    echo "────────────────────────────────────────────────────────────"
    echo "You need a free NASA API key to use this tool."
    echo ""
    echo "1. Visit: https://api.nasa.gov/"
    echo "2. Enter your name and email"
    echo "3. Copy your API key"
    echo ""

    read -p "Enter your NASA API key: " API_KEY

    if [ -z "$API_KEY" ]; then
        echo "Error: API key cannot be empty"
        exit 1
    fi

    # Save API key to config
    echo "{\"api_key\": \"$API_KEY\"}" > "$CONFIG_FILE"
    echo ""
    echo "✓ API key saved to $CONFIG_FILE"
fi

echo ""
echo "Step 2: Test the script"
echo "────────────────────────────────────────────────────────────"
echo "Testing the wallpaper setter..."
echo ""

# Test the script (try yesterday's date in case today has issues)
YESTERDAY=$(date -v-1d +%Y-%m-%d)
if python3 "$SCRIPT_DIR/nasa_apod_wallpaper.py" "$YESTERDAY"; then
    echo ""
    echo "✓ Script tested successfully!"
else
    echo ""
    echo "⚠ Test failed. Check the error above."
    echo "You can still continue with setup."
fi

echo ""
echo "Step 3: Enable daily auto-update (optional)"
echo "────────────────────────────────────────────────────────────"
read -p "Do you want to enable daily automatic wallpaper updates? (Y/n): " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Nn]$ ]]; then
    # Create LaunchAgent plist
    cat > "$LAUNCHAGENT_PATH" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.nasa.apod.wallpaper</string>

    <key>ProgramArguments</key>
    <array>
        <string>$SCRIPT_DIR/nasa_apod_daily.sh</string>
    </array>

    <key>StartCalendarInterval</key>
    <array>
        <dict>
            <key>Hour</key>
            <integer>9</integer>
            <key>Minute</key>
            <integer>3</integer>
        </dict>
        <dict>
            <key>Hour</key>
            <integer>12</integer>
            <key>Minute</key>
            <integer>3</integer>
        </dict>
        <dict>
            <key>Hour</key>
            <integer>15</integer>
            <key>Minute</key>
            <integer>3</integer>
        </dict>
        <dict>
            <key>Hour</key>
            <integer>18</integer>
            <key>Minute</key>
            <integer>3</integer>
        </dict>
        <dict>
            <key>Hour</key>
            <integer>21</integer>
            <key>Minute</key>
            <integer>3</integer>
        </dict>
    </array>

    <key>RunAtLoad</key>
    <true/>

    <key>StandardOutPath</key>
    <string>$WALLPAPER_DIR/launchd.log</string>

    <key>StandardErrorPath</key>
    <string>$WALLPAPER_DIR/launchd_error.log</string>
</dict>
</plist>
EOF

    # Load LaunchAgent
    launchctl unload "$LAUNCHAGENT_PATH" 2>/dev/null || true
    launchctl load "$LAUNCHAGENT_PATH"

    echo ""
    echo "✓ Daily auto-update enabled (runs at 9:03 AM)"
    echo "  LaunchAgent installed at: $LAUNCHAGENT_PATH"
else
    echo "Skipping auto-update setup."
fi

echo ""
echo "════════════════════════════════════════════════════════════"
echo "  Setup Complete! 🚀"
echo "════════════════════════════════════════════════════════════"
echo ""
echo "Your desktop wallpaper should now show NASA's APOD!"
echo ""
echo "Usage:"
echo "  • Run manually:      python3 $SCRIPT_DIR/nasa_apod_wallpaper.py"
echo "  • Specific date:     python3 $SCRIPT_DIR/nasa_apod_wallpaper.py 2024-01-15"
echo "  • View logs:         tail -f $WALLPAPER_DIR/apod.log"
echo ""
echo "Images are saved to: $WALLPAPER_DIR"
echo ""
echo "To uninstall:"
echo "  launchctl unload $LAUNCHAGENT_PATH"
echo "  rm $LAUNCHAGENT_PATH"
echo "  rm -rf $WALLPAPER_DIR"
echo ""
