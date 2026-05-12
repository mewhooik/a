import os
import sys
import time
import json
import psutil
import subprocess
import requests
from flask import Flask, jsonify
from apscheduler.schedulers.background import BackgroundScheduler

IS_WINDOWS = os.name == "nt"

app = Flask(__name__)

prev_net = {"bytes_sent": 0, "bytes_recv": 0, "time": time.time()}


def get_network_speed():
    global prev_net
    net = psutil.net_io_counters()
    now = time.time()
    elapsed = now - prev_net["time"]
    if elapsed <= 0:
        elapsed = 1

    upload_speed = (net.bytes_sent - prev_net["bytes_sent"]) / elapsed
    download_speed = (net.bytes_recv - prev_net["bytes_recv"]) / elapsed

    prev_net = {
        "bytes_sent": net.bytes_sent,
        "bytes_recv": net.bytes_recv,
        "time": now,
    }

    return upload_speed, download_speed


def format_bytes(b):
    for unit in ["B/s", "KB/s", "MB/s", "GB/s"]:
        if b < 1024:
            return f"{b:.2f} {unit}"
        b /= 1024
    return f"{b:.2f} TB/s"


def is_bot_alive():
    for proc in psutil.process_iter(["pid", "cmdline"]):
        try:
            cmdline = proc.info.get("cmdline") or []
            if any("main.py" in arg for arg in cmdline):
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return False


def keep_alive():
    try:
        # Use REPLIT_DEV_DOMAIN (new format) with fallback to old format
        dev_domain = os.environ.get("REPLIT_DEV_DOMAIN")
        if dev_domain:
            url = f"https://{dev_domain}/ping"
        else:
            repl_slug = os.environ.get("REPL_SLUG")
            repl_owner = os.environ.get("REPL_OWNER")
            if repl_slug and repl_owner:
                url = f"https://{repl_slug}.{repl_owner}.repl.co/ping"
            else:
                return
        requests.get(url, timeout=10)
    except Exception:
        pass


scheduler = BackgroundScheduler()
if not IS_WINDOWS:
    # Ping every 4 minutes — before Replit's ~5 min sleep threshold
    scheduler.add_job(func=keep_alive, trigger="interval", minutes=4)
scheduler.start()


@app.route("/api/files")
def api_files():
    downloads_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloads")
    files = []
    if os.path.isdir(downloads_dir):
        for fname in sorted(os.listdir(downloads_dir)):
            fpath = os.path.join(downloads_dir, fname)
            if os.path.isfile(fpath):
                size = os.path.getsize(fpath)
                mtime = os.path.getmtime(fpath)
                # Format size
                for unit in ["B", "KB", "MB", "GB"]:
                    if size < 1024:
                        size_str = f"{size:.1f} {unit}"
                        break
                    size /= 1024
                else:
                    size_str = f"{size:.1f} TB"
                files.append({
                    "name": fname,
                    "size": size_str,
                    "modified": time.strftime("%Y-%m-%d %H:%M", time.localtime(mtime)),
                })
    return jsonify({"files": files, "count": len(files)})


@app.route("/ping")
def ping():
    return "pong", 200


@app.route("/api/status")
def api_status():
    upload_speed, download_speed = get_network_speed()
    bot_alive = is_bot_alive()

    net = psutil.net_io_counters()
    cpu_percent = psutil.cpu_percent(interval=0.1)
    memory = psutil.virtual_memory()
    uptime_seconds = time.time() - psutil.boot_time()

    days = int(uptime_seconds // 86400)
    hours = int((uptime_seconds % 86400) // 3600)
    minutes = int((uptime_seconds % 3600) // 60)

    return jsonify(
        {
            "bot_alive": bot_alive,
            "upload_speed": format_bytes(upload_speed),
            "download_speed": format_bytes(download_speed),
            "upload_speed_raw": upload_speed,
            "download_speed_raw": download_speed,
            "total_sent": format_bytes(net.bytes_sent).replace("/s", ""),
            "total_recv": format_bytes(net.bytes_recv).replace("/s", ""),
            "cpu_percent": cpu_percent,
            "memory_percent": memory.percent,
            "memory_used": f"{memory.used / (1024**3):.2f} GB",
            "memory_total": f"{memory.total / (1024**3):.2f} GB",
            "uptime": f"{days}d {hours}h {minutes}m",
        }
    )


@app.route("/")
def home():
    return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Thanos Bot Dashboard</title>
    <link rel="icon" type="image/x-icon" href="https://tinypic.host/images/2025/02/07/DeWatermark.ai_1738952933236-1.png">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }

        body {
            background: #0a0a0f;
            color: #e0e0e0;
            font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
            min-height: 100vh;
            overflow-x: hidden;
        }

        .bg-grid {
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            background-image:
                linear-gradient(rgba(255,204,0,0.03) 1px, transparent 1px),
                linear-gradient(90deg, rgba(255,204,0,0.03) 1px, transparent 1px);
            background-size: 40px 40px;
            pointer-events: none;
            z-index: 0;
        }

        .container {
            max-width: 900px;
            margin: 0 auto;
            padding: 40px 20px;
            position: relative;
            z-index: 1;
        }

        .header {
            text-align: center;
            margin-bottom: 40px;
        }

        .header h1 {
            font-size: 2.5rem;
            font-weight: 700;
            background: linear-gradient(135deg, #ffcc00, #ff8800);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 6px;
        }

        .header p {
            color: #888;
            font-size: 0.95rem;
        }

        .status-banner {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 12px;
            padding: 16px 28px;
            border-radius: 12px;
            margin-bottom: 32px;
            font-size: 1.1rem;
            font-weight: 600;
            transition: all 0.5s ease;
        }

        .status-banner.online {
            background: rgba(0, 200, 83, 0.1);
            border: 1px solid rgba(0, 200, 83, 0.3);
            color: #00c853;
        }

        .status-banner.offline {
            background: rgba(255, 23, 68, 0.1);
            border: 1px solid rgba(255, 23, 68, 0.3);
            color: #ff1744;
        }

        .pulse-dot {
            width: 12px;
            height: 12px;
            border-radius: 50%;
            position: relative;
        }

        .pulse-dot.online { background: #00c853; }
        .pulse-dot.offline { background: #ff1744; }

        .pulse-dot::before {
            content: '';
            position: absolute;
            top: -4px; left: -4px;
            width: 20px;
            height: 20px;
            border-radius: 50%;
            animation: pulse 2s infinite;
        }

        .pulse-dot.online::before { background: rgba(0, 200, 83, 0.4); }
        .pulse-dot.offline::before { background: rgba(255, 23, 68, 0.4); }

        @keyframes pulse {
            0% { transform: scale(1); opacity: 1; }
            100% { transform: scale(2); opacity: 0; }
        }

        .cards {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
            gap: 20px;
            margin-bottom: 32px;
        }

        .card {
            background: rgba(255,255,255,0.03);
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 16px;
            padding: 24px;
            transition: transform 0.2s, border-color 0.3s;
        }

        .card:hover {
            transform: translateY(-2px);
            border-color: rgba(255,204,0,0.3);
        }

        .card-label {
            font-size: 0.8rem;
            text-transform: uppercase;
            letter-spacing: 1.5px;
            color: #888;
            margin-bottom: 12px;
        }

        .card-value {
            font-size: 1.8rem;
            font-weight: 700;
            font-variant-numeric: tabular-nums;
        }

        .card-sub {
            font-size: 0.85rem;
            color: #666;
            margin-top: 6px;
        }

        .speed-bar-track {
            width: 100%;
            height: 6px;
            background: rgba(255,255,255,0.05);
            border-radius: 3px;
            margin-top: 14px;
            overflow: hidden;
        }

        .speed-bar {
            height: 100%;
            border-radius: 3px;
            transition: width 0.8s ease;
            min-width: 2%;
        }

        .speed-bar.download { background: linear-gradient(90deg, #00c853, #69f0ae); }
        .speed-bar.upload { background: linear-gradient(90deg, #ffcc00, #ff8800); }

        .sys-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 16px;
        }

        .sys-card {
            background: rgba(255,255,255,0.02);
            border: 1px solid rgba(255,255,255,0.06);
            border-radius: 12px;
            padding: 18px;
            text-align: center;
        }

        .sys-label {
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: #666;
            margin-bottom: 8px;
        }

        .sys-value {
            font-size: 1.2rem;
            font-weight: 600;
            color: #ccc;
        }

        .files-section {
            margin-top: 32px;
        }

        .files-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 14px;
        }

        .files-title {
            font-size: 0.8rem;
            text-transform: uppercase;
            letter-spacing: 1.5px;
            color: #888;
        }

        .files-count {
            font-size: 0.8rem;
            background: rgba(255,204,0,0.12);
            color: #ffcc00;
            border-radius: 20px;
            padding: 2px 10px;
        }

        .files-table {
            width: 100%;
            border-collapse: collapse;
        }

        .files-table thead tr {
            border-bottom: 1px solid rgba(255,255,255,0.06);
        }

        .files-table th {
            text-align: left;
            padding: 8px 12px;
            font-size: 0.72rem;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: #555;
            font-weight: 500;
        }

        .files-table td {
            padding: 10px 12px;
            font-size: 0.88rem;
            border-bottom: 1px solid rgba(255,255,255,0.04);
            vertical-align: middle;
        }

        .files-table tr:last-child td { border-bottom: none; }

        .files-table tr:hover td {
            background: rgba(255,255,255,0.02);
        }

        .file-name {
            color: #ddd;
            word-break: break-all;
        }

        .file-name .ext {
            font-size: 0.75rem;
            background: rgba(255,204,0,0.1);
            color: #ffaa00;
            border-radius: 4px;
            padding: 1px 6px;
            margin-left: 6px;
            vertical-align: middle;
        }

        .file-size { color: #888; white-space: nowrap; }
        .file-date { color: #555; white-space: nowrap; font-size: 0.8rem; }

        .files-empty {
            text-align: center;
            padding: 28px;
            color: #444;
            font-size: 0.9rem;
        }

        .files-box {
            background: rgba(255,255,255,0.02);
            border: 1px solid rgba(255,255,255,0.07);
            border-radius: 16px;
            overflow: hidden;
        }

        .footer {
            text-align: center;
            margin-top: 48px;
            padding: 20px;
            color: #444;
            font-size: 0.8rem;
            border-top: 1px solid rgba(255,255,255,0.05);
        }

        .footer img {
            border-radius: 50%;
            vertical-align: middle;
            margin: 0 4px;
        }

        .update-indicator {
            display: inline-block;
            width: 6px;
            height: 6px;
            background: #ffcc00;
            border-radius: 50%;
            margin-left: 8px;
            animation: blink 1s infinite;
        }

        @keyframes blink {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.3; }
        }

        /* Commands Section */
        .commands-section {
            margin-top: 36px;
        }

        .commands-header {
            display: flex;
            align-items: center;
            gap: 10px;
            margin-bottom: 18px;
        }

        .commands-title {
            font-size: 0.8rem;
            text-transform: uppercase;
            letter-spacing: 1.5px;
            color: #888;
        }

        .commands-badge {
            font-size: 0.75rem;
            background: rgba(255,204,0,0.12);
            color: #ffcc00;
            border-radius: 20px;
            padding: 2px 10px;
        }

        .commands-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
            gap: 16px;
        }

        .cmd-group {
            background: rgba(255,255,255,0.02);
            border: 1px solid rgba(255,255,255,0.06);
            border-radius: 14px;
            padding: 18px 20px;
            transition: border-color 0.25s;
        }

        .cmd-group:hover {
            border-color: rgba(255,204,0,0.2);
        }

        .cmd-group-label {
            font-size: 0.7rem;
            text-transform: uppercase;
            letter-spacing: 1.2px;
            color: #ffaa00;
            margin-bottom: 12px;
            display: flex;
            align-items: center;
            gap: 6px;
        }

        .cmd-group-label .cat-icon {
            font-size: 0.95rem;
        }

        .cmd-list {
            display: flex;
            flex-direction: column;
            gap: 7px;
        }

        .cmd-row {
            display: flex;
            align-items: baseline;
            gap: 8px;
        }

        .cmd-name {
            font-family: 'Courier New', monospace;
            font-size: 0.83rem;
            color: #ffcc00;
            white-space: nowrap;
            min-width: 115px;
        }

        .cmd-desc {
            font-size: 0.8rem;
            color: #666;
            line-height: 1.4;
        }

        @media (max-width: 600px) {
            .header h1 { font-size: 1.8rem; }
            .card-value { font-size: 1.4rem; }
            .container { padding: 24px 16px; }
            .commands-grid { grid-template-columns: 1fr; }
        }
    </style>
</head>
<body>
    <div class="bg-grid"></div>
    <div class="container">
        <div class="header">
            <h1>Thanos Bot</h1>
            <p>Real-time System Dashboard <span class="update-indicator"></span></p>
        </div>

        <div id="statusBanner" class="status-banner offline">
            <div id="pulseDot" class="pulse-dot offline"></div>
            <span id="statusText">Checking...</span>
        </div>

        <div class="cards">
            <div class="card">
                <div class="card-label">Download Speed</div>
                <div class="card-value" id="downloadSpeed">-- B/s</div>
                <div class="card-sub">Total: <span id="totalRecv">--</span></div>
                <div class="speed-bar-track">
                    <div class="speed-bar download" id="downloadBar" style="width: 2%"></div>
                </div>
            </div>
            <div class="card">
                <div class="card-label">Upload Speed</div>
                <div class="card-value" id="uploadSpeed">-- B/s</div>
                <div class="card-sub">Total: <span id="totalSent">--</span></div>
                <div class="speed-bar-track">
                    <div class="speed-bar upload" id="uploadBar" style="width: 2%"></div>
                </div>
            </div>
        </div>

        <div class="sys-grid">
            <div class="sys-card">
                <div class="sys-label">CPU Usage</div>
                <div class="sys-value" id="cpuUsage">--%</div>
            </div>
            <div class="sys-card">
                <div class="sys-label">Memory</div>
                <div class="sys-value" id="memUsage">--</div>
            </div>
            <div class="sys-card">
                <div class="sys-label">RAM Used</div>
                <div class="sys-value" id="memDetail">--</div>
            </div>
            <div class="sys-card">
                <div class="sys-label">Uptime</div>
                <div class="sys-value" id="uptime">--</div>
            </div>
        </div>

        <div class="files-section">
            <div class="files-header">
                <span class="files-title">Downloads Folder</span>
                <span class="files-count" id="filesCount">0 files</span>
            </div>
            <div class="files-box">
                <table class="files-table">
                    <thead>
                        <tr>
                            <th>File Name</th>
                            <th>Size</th>
                            <th>Modified</th>
                        </tr>
                    </thead>
                    <tbody id="filesBody">
                        <tr><td colspan="3" class="files-empty">Loading...</td></tr>
                    </tbody>
                </table>
            </div>
        </div>

        <div class="commands-section">
            <div class="commands-header">
                <span class="commands-title">Bot Commands</span>
                <span class="commands-badge">37 commands</span>
            </div>
            <div class="commands-grid">

                <div class="cmd-group">
                    <div class="cmd-group-label"><span class="cat-icon">⬇️</span> Downloads</div>
                    <div class="cmd-list">
                        <div class="cmd-row"><span class="cmd-name">/drm</span><span class="cmd-desc">Download DRM-protected course videos</span></div>
                        <div class="cmd-row"><span class="cmd-name">/gdrive</span><span class="cmd-desc">Download from Google Drive</span></div>
                        <div class="cmd-row"><span class="cmd-name">/ytpl</span><span class="cmd-desc">Download a YouTube playlist</span></div>
                        <div class="cmd-row"><span class="cmd-name">/ytm</span><span class="cmd-desc">Download YouTube music</span></div>
                    </div>
                </div>

                <div class="cmd-group">
                    <div class="cmd-group-label"><span class="cat-icon">📦</span> Batch Control</div>
                    <div class="cmd-list">
                        <div class="cmd-row"><span class="cmd-name">/cancel</span><span class="cmd-desc">Cancel the active batch</span></div>
                        <div class="cmd-row"><span class="cmd-name">/resume</span><span class="cmd-desc">Resume an interrupted batch</span></div>
                        <div class="cmd-row"><span class="cmd-name">/freshstart</span><span class="cmd-desc">Discard saved batch and start fresh</span></div>
                        <div class="cmd-row"><span class="cmd-name">/batchstatus</span><span class="cmd-desc">Check current batch progress</span></div>
                    </div>
                </div>

                <div class="cmd-group">
                    <div class="cmd-group-label"><span class="cat-icon">⚙️</span> Configuration</div>
                    <div class="cmd-list">
                        <div class="cmd-row"><span class="cmd-name">/setlog</span><span class="cmd-desc">Set the log channel</span></div>
                        <div class="cmd-row"><span class="cmd-name">/getlog</span><span class="cmd-desc">View current log channel</span></div>
                        <div class="cmd-row"><span class="cmd-name">/setgroup</span><span class="cmd-desc">Set the upload group/channel</span></div>
                        <div class="cmd-row"><span class="cmd-name">/getgroup</span><span class="cmd-desc">View current upload group</span></div>
                        <div class="cmd-row"><span class="cmd-name">/removegroup</span><span class="cmd-desc">Remove the upload group</span></div>
                    </div>
                </div>

                <div class="cmd-group">
                    <div class="cmd-group-label"><span class="cat-icon">🍪</span> YouTube Cookies</div>
                    <div class="cmd-list">
                        <div class="cmd-row"><span class="cmd-name">/cookies</span><span class="cmd-desc">Upload Netscape cookies .txt file</span></div>
                        <div class="cmd-row"><span class="cmd-name">/getcookies</span><span class="cmd-desc">Download the saved cookies file</span></div>
                        <div class="cmd-row"><span class="cmd-name">/mytc</span><span class="cmd-desc">Set YouTube login credentials</span></div>
                    </div>
                </div>

                <div class="cmd-group">
                    <div class="cmd-group-label"><span class="cat-icon">👑</span> Admin</div>
                    <div class="cmd-list">
                        <div class="cmd-row"><span class="cmd-name">/add</span><span class="cmd-desc">Add a user subscription</span></div>
                        <div class="cmd-row"><span class="cmd-name">/remove</span><span class="cmd-desc">Remove a user subscription</span></div>
                        <div class="cmd-row"><span class="cmd-name">/users</span><span class="cmd-desc">List all subscribed users</span></div>
                        <div class="cmd-row"><span class="cmd-name">/logs</span><span class="cmd-desc">Download bot log file</span></div>
                        <div class="cmd-row"><span class="cmd-name">/clean</span><span class="cmd-desc">Clean downloads folder &amp; expired users</span></div>
                    </div>
                </div>

                <div class="cmd-group">
                    <div class="cmd-group-label"><span class="cat-icon">👤</span> Account &amp; Info</div>
                    <div class="cmd-list">
                        <div class="cmd-row"><span class="cmd-name">/start</span><span class="cmd-desc">Start the bot &amp; view commands</span></div>
                        <div class="cmd-row"><span class="cmd-name">/plan</span><span class="cmd-desc">View your subscription details</span></div>
                        <div class="cmd-row"><span class="cmd-name">/ping</span><span class="cmd-desc">Check bot response latency</span></div>
                        <div class="cmd-row"><span class="cmd-name">/status</span><span class="cmd-desc">Show bot &amp; system status</span></div>
                        <div class="cmd-row"><span class="cmd-name">/id</span><span class="cmd-desc">Get current chat or user ID</span></div>
                    </div>
                </div>

                <div class="cmd-group">
                    <div class="cmd-group-label"><span class="cat-icon">🛠️</span> Utilities</div>
                    <div class="cmd-list">
                        <div class="cmd-row"><span class="cmd-name">/t2t</span><span class="cmd-desc">Convert text to a .txt file</span></div>
                        <div class="cmd-row"><span class="cmd-name">/t2h</span><span class="cmd-desc">Convert text to HTML file</span></div>
                        <div class="cmd-row"><span class="cmd-name">/stop</span><span class="cmd-desc">Stop the bot process</span></div>
                        <div class="cmd-row"><span class="cmd-name">/reset</span><span class="cmd-desc">Reset the bot</span></div>
                    </div>
                </div>

                <div class="cmd-group">
                    <div class="cmd-group-label"><span class="cat-icon">🎨</span> Themes</div>
                    <div class="cmd-list">
                        <div class="cmd-row"><span class="cmd-name">/modern</span><span class="cmd-desc">Modern UI style</span></div>
                        <div class="cmd-row"><span class="cmd-name">/neumorphic</span><span class="cmd-desc">Neumorphic soft UI</span></div>
                        <div class="cmd-row"><span class="cmd-name">/brutalist</span><span class="cmd-desc">Brutalist design</span></div>
                        <div class="cmd-row"><span class="cmd-name">/glassmorphism</span><span class="cmd-desc">Glass morphism style</span></div>
                        <div class="cmd-row"><span class="cmd-name">/cyberpunk</span><span class="cmd-desc">Cyberpunk aesthetic</span></div>
                        <div class="cmd-row"><span class="cmd-name">/mellow</span><span class="cmd-desc">Mellow calm theme</span></div>
                        <div class="cmd-row"><span class="cmd-name">/yengo</span><span class="cmd-desc">Yengo theme</span></div>
                    </div>
                </div>

            </div>
        </div>

        <div class="footer">
            <img src="https://files.catbox.moe/ui41xs.jpg" width="28" height="28">
            Powered by Thanos
            <img src="https://files.catbox.moe/ui41xs.jpg" width="28" height="28">
            <p style="margin-top: 8px;">&copy; 2025 Thanos Bot</p>
        </div>
    </div>

    <script>
        const MAX_SPEED = 10 * 1024 * 1024;

        async function fetchStatus() {
            try {
                const res = await fetch('/api/status');
                const data = await res.json();

                document.getElementById('downloadSpeed').textContent = data.download_speed;
                document.getElementById('uploadSpeed').textContent = data.upload_speed;
                document.getElementById('totalRecv').textContent = data.total_recv;
                document.getElementById('totalSent').textContent = data.total_sent;

                const dlPercent = Math.min((data.download_speed_raw / MAX_SPEED) * 100, 100);
                const ulPercent = Math.min((data.upload_speed_raw / MAX_SPEED) * 100, 100);
                document.getElementById('downloadBar').style.width = Math.max(dlPercent, 2) + '%';
                document.getElementById('uploadBar').style.width = Math.max(ulPercent, 2) + '%';

                document.getElementById('cpuUsage').textContent = data.cpu_percent + '%';
                document.getElementById('memUsage').textContent = data.memory_percent + '%';
                document.getElementById('memDetail').textContent = data.memory_used + ' / ' + data.memory_total;
                document.getElementById('uptime').textContent = data.uptime;

                const banner = document.getElementById('statusBanner');
                const dot = document.getElementById('pulseDot');
                const text = document.getElementById('statusText');

                if (data.bot_alive) {
                    banner.className = 'status-banner online';
                    dot.className = 'pulse-dot online';
                    text.textContent = 'Bot is Live';
                } else {
                    banner.className = 'status-banner offline';
                    dot.className = 'pulse-dot offline';
                    text.textContent = 'Bot is Offline';
                }
            } catch (e) {
                document.getElementById('statusText').textContent = 'Connection Error';
            }
        }

        async function fetchFiles() {
            try {
                const res = await fetch('/api/files');
                const data = await res.json();
                const tbody = document.getElementById('filesBody');
                const countEl = document.getElementById('filesCount');
                countEl.textContent = data.count + (data.count === 1 ? ' file' : ' files');
                if (data.files.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="3" class="files-empty">No files in downloads folder</td></tr>';
                    return;
                }
                tbody.innerHTML = data.files.map(f => {
                    const dot = f.name.lastIndexOf('.');
                    const ext = dot !== -1 ? f.name.slice(dot + 1).toUpperCase() : '';
                    const base = dot !== -1 ? f.name.slice(0, dot) : f.name;
                    return `<tr>
                        <td class="file-name">${base}${ext ? `<span class="ext">${ext}</span>` : ''}</td>
                        <td class="file-size">${f.size}</td>
                        <td class="file-date">${f.modified}</td>
                    </tr>`;
                }).join('');
            } catch (e) {
                document.getElementById('filesBody').innerHTML =
                    '<tr><td colspan="3" class="files-empty">Could not load files</td></tr>';
            }
        }

        fetchStatus();
        fetchFiles();
        setInterval(fetchStatus, 2000);
        setInterval(fetchFiles, 5000);
    </script>
</body>
</html>"""


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host="0.0.0.0", port=port)
