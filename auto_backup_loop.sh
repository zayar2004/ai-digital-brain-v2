#!/data/data/com.termux/files/usr/bin/bash
# ============================================================
# Auto Backup Loop — Runs backup.sh every INTERVAL seconds
# ============================================================

INTERVAL=1800      # 30 minutes
ROTATE_EVERY=48    # rotate every 24h (48 × 30min)
LOGFILE="$HOME/ai_digital_brain/backup.log"

echo "[$(date '+%F %T')] 🚀 Auto-backup loop started (every ${INTERVAL}s)" >> "$LOGFILE"

i=0
while true; do
    cd "$HOME/ai_digital_brain" || exit 1

    # Run snapshot
    ./backup.sh AUTO >> "$LOGFILE" 2>&1

    i=$((i + 1))

    # Every 24h → rotate old backups
    if [ $((i % ROTATE_EVERY)) -eq 0 ]; then
        ./backup_rotate.sh >> "$LOGFILE" 2>&1
    fi

    sleep $INTERVAL
done
