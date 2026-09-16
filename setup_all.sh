#!/data/data/com.termux/files/usr/bin/bash
# One-shot: create all backup scripts + first snapshot + start loop
cd "$HOME/ai_digital_brain"

echo "=== AI Brain — Backup Setup ==="
echo "[1/3] Creating folders..."
mkdir -p backups/snapshots backups/schema backups/libs backups/system

echo "[2/3] First manual snapshot..."
./backup.sh MANUAL

echo "[3/3] Starting auto-backup loop..."
pkill -f auto_backup_loop.sh 2>/dev/null
sleep 1
nohup ./auto_backup_loop.sh > /dev/null 2>&1 &
sleep 2
ps aux | grep auto_backup_loop | grep -v grep

echo ""
echo "✅ Setup complete"
echo ""
echo "Commands:"
echo "  ./backup.sh MANUAL          — manual snapshot now"
echo "  ./backup.sh before-fix      — label this snapshot"
echo "  ./backup_rotate.sh          — cleanup old backups"
echo "  pkill -f auto_backup_loop   — stop auto loop"
echo "  nohup ./auto_backup_loop.sh & — restart auto loop"
