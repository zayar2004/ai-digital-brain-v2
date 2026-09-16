"""
Failover Heartbeat — Active phone (Ph 1)
- Send 1 message → admin chat
- Every 30s → edit message → "alive: HH:MM:SS"
"""
import time
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.expanduser("~/ai_digital_brain"))
from app.config import Config

import httpx

TOKEN = Config.TELEGRAM_BOT_TOKEN
CHAT_ID = int(os.getenv("FAILOVER_ADMIN_CHAT_ID", "6366275414"))
INTERVAL = int(os.getenv("FAILOVER_HEARTBEAT_INTERVAL", "30"))

API = f"https://api.telegram.org/bot{TOKEN}"

msg_id = None

def send_initial():
    global msg_id
    url = f"{API}/sendMessage"
    r = httpx.post(url, json={
        "chat_id": CHAT_ID,
        "text": "❤️ alive: --:--:--",
        "disable_notification": True,
    }, timeout=15)
    data = r.json()
    if data.get("ok"):
        msg_id = data["result"]["message_id"]
        print(f"✓ Initial msg_id: {msg_id}")
    else:
        print(f"❌ Send failed: {data}")

def edit_heartbeat():
    global msg_id
    if not msg_id:
        send_initial()
        return
    now = datetime.now().strftime("%H:%M:%S")
    url = f"{API}/editMessageText"
    r = httpx.post(url, json={
        "chat_id": CHAT_ID,
        "message_id": msg_id,
        "text": f"❤️ alive: {now}",
    }, timeout=10)
    data = r.json()
    if data.get("ok"):
        print(f"✓ {now}")
    else:
        err = data.get("description", "unknown")
        print(f"⚠️ Edit failed: {err}")
        if "message to edit not found" in err:
            msg_id = None

def main():
    print("=== Ph 1 — Heartbeat Active ===")
    send_initial()
    while True:
        try:
            edit_heartbeat()
        except Exception as e:
            print(f"❌ Error: {e}")
        time.sleep(INTERVAL)

if __name__ == "__main__":
    main()
