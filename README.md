# NASA APOD Wallpaper

![NASA APOD](https://apod.nasa.gov/apod/image/2603/cg4_1024.jpg)

## What it does

- Downloads NASA's Astronomy Picture of the Day every day directly from [science.nasa.gov/apod](https://science.nasa.gov/apod/).
- Sets it as your Mac desktop wallpaper (supports Desktop 1 only or all spaces).
- Safely preserves any folder shuffle configured on secondary spaces without advancing them on wake.
- Uses saved pictures if today's post is a video or offline.

## Usage

```bash
# Set today's APOD
python3 nasa_apod_wallpaper.py

# Set APOD for a specific date
python3 nasa_apod_wallpaper.py 2026-09-30

# Set APOD from a direct science.nasa.gov article URL
python3 nasa_apod_wallpaper.py https://science.nasa.gov/image-article/apod-2026-september-30-arp-78-peculiar-galaxy-in-aries/

# Pick a random cached APOD
python3 nasa_apod_wallpaper.py --shuffle

# Backfill the last N days
python3 nasa_apod_wallpaper.py --backfill 30
```

## How to install

1. Run setup:

```bash
./setup.sh
```

Optional: Enter an [api.nasa.gov](https://api.nasa.gov/) API key if desired for fallback support.

