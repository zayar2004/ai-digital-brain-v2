#!/data/data/com.termux/files/usr/bin/bash
# ============================================================
# Send Portable Backup to Telegram
# ============================================================

TOKEN="8914319439:AAEaiEifDLHjfGh6z7M5EN9Kh9zYgE93t0o"
CHAT_ID="6366275414"

DIR=$(ls -d portable_* 2>/dev/null | tail -1)
if [ -z "$DIR" ]; then
    echo "❌ No portable folder"
    exit 1
fi

echo "Sending from: $DIR"
echo ""

send_file() {
    local f="$1"
    if [ ! -f "$DIR/$f" ]; then
        echo "  ⏭  $f (not found)"
        return
    fi
    local size=$(du -h "$DIR/$f" | cut -f1)
    echo "  → $f ($size)"
    local resp=$(curl -s -F "chat_id=$CHAT_ID" \
                       -F "document=@$DIR/$f" \
                       "https://api.telegram.org/bot$TOKEN/sendDocument")
    if echo "$resp" | grep -q '"ok":true'; then
        echo "    ✅ sent"
    else
        echo "    ❌ failed: $resp"
    fi
    sleep 1
}

send_file "project.tar.gz"
send_file "SNAPSHOT.md"
send_file "requirements.txt"
send_file "setup.sh"
send_file "termux_packages.txt"

# Photos — optional (ကြာမယ်)
read -p "Send photos.tar.gz (47 MB)? [y/N] " ans
if [ "$ans" = "y" ] || [ "$ans" = "Y" ]; then
    send_file "photos.tar.gz"
fi

echo ""
echo "✓ Done"
