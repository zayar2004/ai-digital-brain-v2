#!/data/data/com.termux/files/usr/bin/bash
FILE="$HOME/ai_digital_brain/requirements_nobcrypt.txt"
CHAT_ID="${1:-6366275414}"
source "$HOME/ai_digital_brain/venv/bin/activate"

python3 - <<PYEOF
import httpx
from app.config import Config
url = f"https://api.telegram.org/bot{Config.TELEGRAM_BOT_TOKEN}/sendDocument"
with open("$FILE", "rb") as fh:
    r = httpx.post(url,
                   data={"chat_id": $CHAT_ID, "caption": "📋 requirements_nobcrypt.txt — for 2nd Phone"},
                   files={"document": fh}, timeout=60)
    print(r.status_code, r.json().get("ok"))
PYEOF
