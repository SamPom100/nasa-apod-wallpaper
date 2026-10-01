# NASA APOD Wallpaper

<img width="1512" height="982" alt="screenshot" src="https://github.com/user-attachments/assets/e2a839eb-aed6-4b59-bebc-bc6bf07d632f" />

![NASA APOD](https://assets.science.nasa.gov/dynamicimage/assets/science/cds/apod/apod/2026/march/cg4.jpg?w=1024)

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




