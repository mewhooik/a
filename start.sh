#!/bin/bash
set -e

echo "[start.sh] Starting Thanos Bot..."

# Start the web dashboard in the background
python3 -u app.py &
WEBAPP_PID=$!
echo "[start.sh] Web dashboard started (PID $WEBAPP_PID)"

# Start the Telegram bot in the foreground (keeps container alive)
echo "[start.sh] Starting Telegram bot..."
python3 -u main.py
python3 -u app.py &   # web dashboard in background
python3 -u main.py    # bot in foreground (keeps container alive)
