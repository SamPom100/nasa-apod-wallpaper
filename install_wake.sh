#!/bin/bash
set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
WALLPAPER_DIR="$HOME/.nasa_apod_wallpapers"
LAUNCHAGENT_PATH="$HOME/Library/LaunchAgents/com.nasa.apod.wallpaper.wake.plist"
USER_DOMAIN="gui/$(id -u)"

/bin/launchctl print "$USER_DOMAIN/com.nasa.apod.wallpaper" > /dev/null
mkdir -p "$WALLPAPER_DIR" "$HOME/Library/LaunchAgents"
/usr/bin/swiftc -O "$SCRIPT_DIR/nasa_apod_wake.swift" -o "$WALLPAPER_DIR/nasa_apod_wake.new"
mv "$WALLPAPER_DIR/nasa_apod_wake.new" "$WALLPAPER_DIR/nasa_apod_wake"

/usr/bin/python3 - "$WALLPAPER_DIR" "$LAUNCHAGENT_PATH" <<'PY'
import plistlib
import sys
from pathlib import Path

directory = Path(sys.argv[1])
with open(sys.argv[2], "wb") as target:
    plistlib.dump({
        "Label": "com.nasa.apod.wallpaper.wake",
        "ProgramArguments": [str(directory / "nasa_apod_wake")],
        "RunAtLoad": True,
        "KeepAlive": True,
        "LimitLoadToSessionType": "Aqua",
        "StandardOutPath": str(directory / "wake.log"),
        "StandardErrorPath": str(directory / "wake.log"),
    }, target)
PY

/bin/launchctl bootout "$USER_DOMAIN/com.nasa.apod.wallpaper.wake" 2>/dev/null || true
/bin/launchctl bootstrap "$USER_DOMAIN" "$LAUNCHAGENT_PATH"
echo "Wallpaper updates after wake, unlock, and display changes are enabled."
