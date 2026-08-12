#!/bin/bash
# Daily NASA APOD Wallpaper Updater
# This script runs the Python wallpaper setter and logs the output

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
LOG_FILE="$HOME/.nasa_apod_wallpapers/apod.log"

{
    echo "==================== $(date) ===================="
    /usr/bin/python3 -u "$SCRIPT_DIR/nasa_apod_wallpaper.py"
    status=$?
    echo ""
} >> "$LOG_FILE" 2>&1

exit "$status"
