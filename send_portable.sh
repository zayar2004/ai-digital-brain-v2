#!/data/data/com.termux/files/usr/bin/bash
# Send portable.zip via Telegram Bot

PORTABLE_DIR=$(ls -td ~/ai_digital_brain/portable_* | head -1)
ZIP_FILE="$HOME/ai_digital_brain/portable.zip"
ADMIN_CHAT_ID="${1:-6366275414}"   # default — A3 AT Zayar

source "$HOME/ai_digital_brain/venv/bin/activate"

python3 - <<PYEOF
import os
from app.telegram import client as tg
from app.config import Config

chat_id = $ADMIN_CHAT_ID
file_path = "$ZIP_FILE"

print(f"Sending: {file_path}")
print(f"Size: {os.path.getsize(file_path) / 1024 / 1024:.2f} MB")
print(f"To chat: {chat_id}")

import httpx
url = f"https://api.telegram.org/bot{Config.TELEGRAM_BOT_TOKEN}/sendDocument"
with open(file_path, "rb") as fh:
    r = httpx.post(url, data={"chat_id": chat_id, "caption": "📦 AI Brain — Portable Package"}, files={"document": fh}, timeout=300)
    print(r.status_code)
    print(r.json())
PYEOF
