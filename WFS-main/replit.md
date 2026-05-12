# Mpd-Debugger (Thanos Bot)

## Overview

A Telegram bot with a real-time web dashboard. The bot handles media downloading, DRM decryption, and file uploading via Telegram. The web dashboard displays live system stats (CPU, memory, network speed) and bot status.

## Architecture

- **`main.py`** — Telegram bot built with Pyrogram (pyrofork). Handles all bot commands, media processing, and user authentication.
- **`app.py`** — Flask web dashboard on port 5000. Shows real-time system metrics and bot online/offline status.
- **`vars.py`** — Configuration via environment variables (API_ID, API_HASH, BOT_TOKEN, OWNER_ID, ADMINS, etc.)
- **`db.py`** — SQLite-based database for user management and subscriptions.
- **`auth.py`** — User authorization and subscription checking.
- **`thanos.py`** — Core bot helper functions for media downloading/processing.
- **`html_handler.py`** — Handles HTML/text file processing.
- **`clean.py`** — File cleanup handlers.
- **`compat.py`** — Cross-platform compatibility (Windows/Linux).
- **`utils.py`** — Progress bar and utility functions.
- **`logs.py`** — Logging configuration.
- **`mp4decrypt`** — Binary for DRM-protected MP4 decryption.

## Workflows

- **Start application** — Runs `python app.py` on port 5000 (web dashboard)

## Environment Variables

Set these for the bot to work:
- `API_ID` — Telegram API ID
- `API_HASH` — Telegram API Hash
- `BOT_TOKEN` — Telegram Bot Token
- `OWNER_ID` — Bot owner's Telegram user ID
- `ADMINS` — Space-separated admin user IDs
- `PORT` — Web server port (default: 8000, but app.py uses 5000)

## Running the Bot

The web dashboard starts automatically. To run the Telegram bot alongside it:
```
python main.py
```

## YouTube Download Architecture

YouTube downloads use a layered, resilient approach:

1. **Primary strategy**: `web` client + YouTube cookies (`youtube_cookies.txt`) + Node.js EJS challenge solver (`yt-dlp-ejs` Python package)
2. **Auto-fallback**: If the web client fails due to cookie expiry or JS challenge issues, automatically retries with the `android_vr` client (no cookies) for public videos
3. **Bot detection**: If bot detection triggers (requires login), the bot prompts the user for YouTube credentials or to re-upload cookies via `/cookies`

### Cookie Management
- Upload cookies via `/cookies` command (send a Netscape-format .txt file exported from your browser)
- Use `/ytcredentials` to provide YouTube login credentials directly
- Re-upload cookies periodically (they expire every few weeks)

### EJS Challenge Solver
- The `yt-dlp-ejs` Python package is bundled — no external GitHub download needed
- Node.js 22 is installed as the JS runtime for the solver
- This handles YouTube's anti-bot JS challenges automatically

## Dependencies

Python packages: pyrofork, tgcrypto, pyromod, pyrogram, Flask, yt-dlp, yt-dlp-ejs, pycryptodome, aiohttp, cloudscraper, m3u8, ffmpeg-python, pillow, beautifulsoup4, sqlalchemy, and more (see requirements.txt).
