#!/data/data/com.termux/files/usr/bin/bash
#
# Daily auto backup — wraps backup_full.sh + notifies Telegram
#
set -uo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

# Run full backup
bash scripts/backup_full.sh > logs/auto_backup_output.log 2>&1 || true

NEWEST_ZIP=$(ls -1t backups/adb_full_*.zip 2>/dev/null | head -1)
if [ -z "$NEWEST_ZIP" ]; then
  echo "[backup] ❌ No backup created"
  exit 1
fi

NEWEST_SIZE=$(du -h "$NEWEST_ZIP" | cut -f1)
NEWEST_NAME=$(basename "$NEWEST_ZIP")
TIMESTAMP=$(date '+%Y-%m-%d %H:%M')

echo ""
echo "════════════════════════════════════════"
echo "✅ Backup: $NEWEST_NAME ($NEWEST_SIZE)"
echo "   Time:  $TIMESTAMP"
echo "════════════════════════════════════════"

# Optional Telegram notify
if [ -f ".env" ] && grep -q "TELEGRAM_BOT_TOKEN=" .env 2>/dev/null; then
  source venv/bin/activate 2>/dev/null || true
  python - <<PY 2>/dev/null || true
import os, sys
from pathlib import Path
from dotenv import load_dotenv
import httpx

load_dotenv(".env")
token = os.getenv("TELEGRAM_BOT_TOKEN", "")
if not token:
    sys.exit(0)

sys.path.insert(0, ".")
from app import create_app
from app.models import TelegramUser

app = create_app()
with app.app_context():
    admin = TelegramUser.query.filter_by(is_verified=True, is_blocked=False).first()
    if not admin:
        sys.exit(0)
    chat_id = admin.telegram_user_id

msg = f"""📦 Daily Backup Complete

📄 File: $NEWEST_NAME
💾 Size: $NEWEST_SIZE
🕒 Time: $TIMESTAMP"""

try:
    httpx.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": msg},
        timeout=15,
    )
    print(f"  ✓ Notified Telegram admin ({chat_id})")
except Exception as e:
    print(f"  ⚠ Telegram notify failed: {e}")
PY
fi
