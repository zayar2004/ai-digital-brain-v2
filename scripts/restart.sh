#!/data/data/com.termux/files/usr/bin/bash
# Restart AI Digital Brain services.
# Usage: bash scripts/restart.sh [web|bot|all]

set -e
cd "$(dirname "$0")/.."

source venv/bin/activate

TARGET="${1:-all}"

stop() {
  echo "→ Stopping..."
  pkill -f "python run.py" 2>/dev/null || true
  pkill -f "python bot.py" 2>/dev/null || true
  sleep 2
  echo "✓ Stopped"
}

start_web() {
  echo "→ Starting web..."
  nohup python run.py > logs/web.log 2>&1 &
  echo "✓ Web started (PID $!)"
}

start_bot() {
  echo "→ Starting bot..."
  nohup python bot.py > logs/bot.log 2>&1 &
  echo "✓ Bot started (PID $!)"
}

case "$TARGET" in
  web)  stop; start_web ;;
  bot)  stop; start_bot ;;
  all)  stop; start_web; sleep 2; start_bot ;;
  *)    echo "Usage: $0 [web|bot|all]" ; exit 1 ;;
esac

echo
echo "Done. Logs:"
echo "  tail -f logs/web.log"
echo "  tail -f logs/bot.log"
