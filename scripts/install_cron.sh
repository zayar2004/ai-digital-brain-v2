#!/data/data/com.termux/files/usr/bin/bash
#
# Install auto-start + auto-backup scheduling.
# Order: termux-job-scheduler → crond → background loop
#

set -uo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m'

log()  { echo -e "${GREEN}[cron]${NC} $*"; }
warn() { echo -e "${YELLOW}[warn]${NC} $*"; }
err()  { echo -e "${RED}[error]${NC} $*" >&2; }

mkdir -p "$PROJECT_DIR/logs"

# ------------------------------------------------------------------
# Option 1: termux-job-scheduler
# ------------------------------------------------------------------
if command -v termux-job-scheduler >/dev/null 2>&1; then
  log "Using termux-job-scheduler..."

  log "Scheduling auto-start (every 15 min)..."
  termux-job-scheduler \
    -s "$PROJECT_DIR/scripts/auto_start.sh" \
    --job-id 2002 \
    --period-ms 900000 \
    --network unmetered 2>/dev/null || \
  termux-job-scheduler \
    --script "$PROJECT_DIR/scripts/auto_start.sh" \
    --job-id 2002 \
    --period-ms 900000 2>/dev/null || \
    warn "  Could not schedule"

  echo ""
  log "✓ Jobs scheduled. Check:"
  termux-job-scheduler --pending 2>/dev/null || \
  termux-job-scheduler -p 2>/dev/null || true

  echo ""
  log "⚠️  Install Termux:Boot from F-Droid for boot auto-start."
  exit 0
fi

# ------------------------------------------------------------------
# Option 2: crond
# ------------------------------------------------------------------
if command -v crond >/dev/null 2>&1 || command -v cron >/dev/null 2>&1; then
  log "Using crond..."

  CRON_FILE="$HOME/.cron_adb"
  cat > "$CRON_FILE" <<EOF
# AI Digital Brain — Auto jobs
# Auto-start + backup check every 15 min
*/15 * * * * $PROJECT_DIR/scripts/auto_start.sh start >> $PROJECT_DIR/logs/start_cron.log 2>&1

# Daily backup at 2:00 AM
0 2 * * * $PROJECT_DIR/scripts/auto_backup_daily.sh >> $PROJECT_DIR/logs/backup_cron.log 2>&1
EOF

  if crontab "$CRON_FILE" 2>/dev/null; then
    log "✓ Crontab installed:"
    crontab -l 2>/dev/null | sed 's/^/  /'
  else
    warn "crontab command failed"
  fi

  if ! pgrep -x crond >/dev/null; then
    log "Starting crond..."
    crond 2>/dev/null &
  fi

  exit 0
fi

# ------------------------------------------------------------------
# Option 3: Background loop
# ------------------------------------------------------------------
warn "No scheduler found — installing background loop..."

cat > "$PROJECT_DIR/scripts/auto_loop.sh" <<'LOOP'
#!/data/data/com.termux/files/usr/bin/bash
cd "$(dirname "$0")/.."
while true; do
  bash scripts/auto_start.sh start >> logs/auto_loop.log 2>&1
  sleep 900   # 15 min
done
LOOP
chmod +x "$PROJECT_DIR/scripts/auto_loop.sh"

# Kill existing
pkill -f "scripts/auto_loop.sh" 2>/dev/null || true
sleep 1

nohup bash "$PROJECT_DIR/scripts/auto_loop.sh" > "$PROJECT_DIR/logs/auto_loop.log" 2>&1 &
log "✓ Background loop started (PID $!)"
log "  Logs: tail -f $PROJECT_DIR/logs/auto_loop.log"
