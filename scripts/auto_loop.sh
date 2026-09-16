#!/data/data/com.termux/files/usr/bin/bash
cd "$(dirname "$0")/.."
echo "[loop] Started at $(date)"
while true; do
  bash scripts/auto_start.sh start >> logs/auto_loop.log 2>&1
  sleep 900   # 15 min
done
