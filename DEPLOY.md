# Deployment Guide

## Deploy on Northflank (Recommended — 0.2 vCPU / 512 MB / 2048 MB)

### Step 1 — Push to GitHub
Push this repo to a GitHub repository (all files must be committed).

### Step 2 — Create a Combined Service on Northflank
1. Go to https://app.northflank.com and sign in.
2. Create a new project, then click **New Service → Deployment Service**.
3. Choose **Deploy from a Git repository** and connect your GitHub repo.
4. Build settings:
   - **Build type**: `Dockerfile`
   - Northflank will detect the `Dockerfile` automatically.
5. Port settings:
   - Add a port: **5000 / HTTP** — this is the web dashboard.
6. Resources:
   - vCPU: `0.2`
   - Memory: `512 MB`
   - Ephemeral storage: `2048 MB`

### Step 3 — Set Environment Variables
Under the service's **Environment** tab, add:

| Key | Value |
|-----|-------|
| `BOT_TOKEN` | Your Telegram bot token |
| `API_ID` | Your Telegram API ID |
| `API_HASH` | Your Telegram API Hash |
| `OWNER_ID` | Your Telegram user ID |
| `ADMINS` | Space-separated admin Telegram user IDs |

### Step 4 — Deploy
Click **Deploy**. Northflank will build the Docker image and start both the Telegram bot and the web dashboard inside the same container (managed by supervisord).

### Step 5 — Persistent Session (Important)
After first deploy, the bot will generate a Pyrogram `.session` file inside the container.  
**This file is lost on every redeploy** unless you mount a persistent volume.

To persist the session:
1. In Northflank, add a **Volume** to your service.
2. Mount path: `/app` — this mounts the full working directory persistently.
3. Alternatively, use a `STRING_SESSION` environment variable (requires code changes).

---

## Large File Handling (≤ 2048 MB storage)

The bot is optimised for constrained storage:

- **Pre-download disk check**: If less than 512 MB of free space is available, the download is rejected with a friendly message. Use `/clean` to free up space.
- **Split-and-free**: Files larger than 1.9 GB are split into parts. The original is deleted *immediately* after splitting (before uploading parts) to avoid doubling disk usage.
- **Guaranteed cleanup**: If an upload fails at any point, the downloaded file and thumbnail are always deleted.
- **Low-memory downloads**: HLS streams use 4 concurrent fragments (instead of 16) to keep RAM usage low.

---

## Deploy on Render

1. Push this repo to GitHub.
2. Go to https://render.com and sign in.
3. Click **New → Web Service**.
   - Connect your GitHub repo.
   - Runtime: **Docker** (Render detects the `Dockerfile` automatically).
4. Set the environment variables listed above.
5. Port: `5000`.
6. Click **Deploy**.

> **Note:** The free Render plan spins down after inactivity. Use the Starter plan ($7/mo) or higher to keep the bot always running.

---

## Run Locally (Windows)

### Step 1 — Install Python 3.11
Download from https://www.python.org/downloads/  
During install, check **"Add Python to PATH"**.

### Step 2 — Install ffmpeg
1. Download from https://www.gyan.dev/ffmpeg/builds/ → `ffmpeg-release-essentials.zip`
2. Extract to e.g. `C:\ffmpeg`
3. Add `C:\ffmpeg\bin` to system PATH.

### Step 3 — Install aria2
1. Download from https://github.com/aria2/aria2/releases/latest
2. Place `aria2c.exe` in `C:\ffmpeg\bin`.

### Step 4 — Install mp4decrypt (Bento4)
1. Download from https://www.bok.net/Bento4/binaries/Bento4-SDK-1-6-0-641.x86_64-pc-windows.zip
2. Copy `mp4decrypt.exe` into the same folder as `main.py`.

### Step 5 — Install Python packages
```
pip install -r requirements.txt
```

### Step 6 — Set environment variables
Create a `.env` file in the bot folder:
```
BOT_TOKEN=your_bot_token_here
API_ID=your_api_id
API_HASH=your_api_hash
OWNER_ID=your_telegram_id
ADMINS=your_telegram_id
```

### Step 7 — Run the bot
```
python main.py
```
