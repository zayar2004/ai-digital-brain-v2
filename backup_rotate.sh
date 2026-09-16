#!/data/data/com.termux/files/usr/bin/bash
# ============================================================
# Backup Rotation — Keep last N AUTO backups + manual forever
# ============================================================

BACKUP_DIR="$HOME/ai_digital_brain/backups"
LOG="$HOME/ai_digital_brain/backup.log"
KEEP_AUTO=30      # keep last 30 AUTO snapshots
KEEP_DAYS=30      # delete dated folders older than 30 days

cd "$BACKUP_DIR" || exit 1

# 1. Rotate AUTO snapshots
if [ -d snapshots ]; then
    cd snapshots
    TOTAL=$(ls -1 AUTO_*.md 2>/dev/null | wc -l | tr -d ' ')
    if [ "$TOTAL" -gt "$KEEP_AUTO" ]; then
        ls -t AUTO_*.md 2>/dev/null | tail -n +$((KEEP_AUTO + 1)) | while read f; do
            rm -f "$f"
            echo "  deleted: $f"
        done
    fi
    cd "$BACKUP_DIR"
fi

# 2. Delete old dated folders
find "$BACKUP_DIR" -maxdepth 1 -type d -name "20*" -mtime +$KEEP_DAYS -exec rm -rf {} \; 2>/dev/null

# 3. Delete old sidecars
find "$BACKUP_DIR/schema" -name "*.sql" -mtime +$KEEP_DAYS -delete 2>/dev/null
find "$BACKUP_DIR/libs" -name "*.txt" -mtime +$KEEP_DAYS -delete 2>/dev/null
find "$BACKUP_DIR/system" -name "*.txt" -mtime +$KEEP_DAYS -delete 2>/dev/null

echo "[$(date '+%F %T')] 🔄 Rotation done (keep AUTO=$KEEP_AUTO, days=$KEEP_DAYS)" >> "$LOG"
echo "✓ Rotation complete"
