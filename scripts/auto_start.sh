#!/data/data/com.termux/files/usr/bin/bash
#
# AI DIGITAL BRAIN — Auto Start + Auto Backup
#
# Starts: Web + Bot
# Also: Automatic backup based on interval (default 24h)
#
# Usage:
#   bash scripts/auto_start.sh              (start + auto backup)
#   bash scripts/auto_start.sh --wait-net   (wait for internet)
#   bash scripts/auto_start.sh --stop       (stop services)
#   bash scripts/auto_start.sh --status     (show status)
#   bash scripts/auto_start.sh --backup     (backup only)
#   bash scripts/auto_start.sh --no-backup  (skip auto backup)
#

set -uo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

WEB_LOG="$PROJECT_DIR/logs/web.log"
BOT_LOG="$PROJECT_DIR/logs/bot.log"
BACKUP_LOG="$PROJECT_DIR/logs/backup.log"
BACKUP_STATE="$PROJECT_DIR/instance/.last_backup"
mkdir -p logs instance

# ------------------------------------------------------------------
# CONFIG — Backup interval (seconds)
# ------------------------------------------------------------------
BACKUP_INTERVAL="${BACKUP_INTERVAL:-86400}"   # 24 hours default
# Set to 21600 for 6h, 43200 for 12h, 604800 for 7 days

GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

log()  { echo -e "${GREEN}[start]${NC} $*"; }
warn() { echo -e "${YELLOW}[warn]${NC}  $*"; }
info() { echo -e "${BLUE}[info]${NC}  $*"; }
err()  { echo -e "${RED}[error]${NC} $*" >&2; }

# ------------------------------------------------------------------
# Activate venv
# ------------------------------------------------------------------
if [ -d "venv" ]; then
  # shellcheck disable=SC1091
  source venv/bin/activate
fi

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------
web_running() {
  pgrep -f "python.*run.py" >/dev/null 2>&1
}

bot_running() {
  pgrep -f "python.*bot.py" >/dev/null 2>&1
}

has_internet() {
  curl -s --max-time 5 -o /dev/null -w "%{http_code}" https://api.telegram.org 2>/dev/null | grep -q "200\|401\|404"
}

wait_for_internet() {
  local max_wait=60
  local elapsed=0
  log "Waiting for internet..."
  while ! has_internet; do
    sleep 2
    elapsed=$((elapsed + 2))
    if [ "$elapsed" -ge "$max_wait" ]; then
      warn "Internet timeout after ${max_wait}s — starting anyway"
      return 1
    fi
  done
  log "Internet OK (${elapsed}s)"
  return 0
}

# ------------------------------------------------------------------
# Backup logic
# ------------------------------------------------------------------
needs_backup() {
  if [ ! -f "$BACKUP_STATE" ]; then
    return 0   # never backed up
  fi
  local last
  last=$(cat "$BACKUP_STATE" 2>/dev/null || echo 0)
  local now
  now=$(date +%s)
  local elapsed=$((now - last))
  if [ "$elapsed" -ge "$BACKUP_INTERVAL" ]; then
    return 0
  fi
  return 1
}

run_backup() {
  if ! needs_backup; then
    local last
    last=$(cat "$BACKUP_STATE" 2>/dev/null || echo 0)
    local now=$(date +%s)
    local elapsed=$((now - last))
    local remaining=$((BACKUP_INTERVAL - elapsed))
    local hours=$((remaining / 3600))
    info "Backup not needed yet (${hours}h remaining)"
    return 0
  fi

  log "Running scheduled backup..."
  if [ -x scripts/auto_backup_daily.sh ]; then
    if bash scripts/auto_backup_daily.sh >> "$BACKUP_LOG" 2>&1; then
      date +%s > "$BACKUP_STATE"
      log "  ✓ Backup complete"
    else
      warn "  ⚠ Backup failed — check $BACKUP_LOG"
    fi
  else
    warn "  auto_backup_daily.sh not found or not executable"
  fi
}

# ------------------------------------------------------------------
# Services
# ------------------------------------------------------------------
start_web() {
  if web_running; then
    warn "Web already running (PID: $(pgrep -f 'python.*run.py' | head -1))"
    return 0
  fi
  log "Starting web..."
  nohup python run.py > "$WEB_LOG" 2>&1 &
  local pid=$!
  sleep 2
  if ps -p "$pid" > /dev/null 2>&1; then
    log "  Web started (PID $pid)"
    return 0
  fi
  err "  Web failed — check $WEB_LOG"
  return 1
}

start_bot() {
  if bot_running; then
    warn "Bot already running (PID: $(pgrep -f 'python.*bot.py' | head -1))"
    return 0
  fi
  log "Starting bot..."
  nohup python bot.py > "$BOT_LOG" 2>&1 &
  local pid=$!
  sleep 2
  if ps -p "$pid" > /dev/null 2>&1; then
    log "  Bot started (PID $pid)"
    return 0
  fi
  err "  Bot failed — check $BOT_LOG"
  return 1
}

stop_all() {
  log "Stopping services..."
  pkill -9 -f "python.*run.py" 2>/dev/null && log "  Web stopped" || true
  pkill -9 -f "python.*bot.py" 2>/dev/null && log "  Bot stopped" || true
  sleep 1
}

status_all() {
  echo ""
  echo "─── Services ───────────────────────"
  if web_running; then
    echo -e "  Web:  ${GREEN}RUNNING${NC}  (PID $(pgrep -f 'python.*run.py' | head -1))"
  else
    echo -e "  Web:  ${RED}STOPPED${NC}"
  fi
  if bot_running; then
    echo -e "  Bot:  ${GREEN}RUNNING${NC}  (PID $(pgrep -f 'python.*bot.py' | head -1))"
  else
    echo -e "  Bot:  ${RED}STOPPED${NC}"
  fi
  echo "─── Backup ─────────────────────────"
  if [ -f "$BACKUP_STATE" ]; then
    local last=$(cat "$BACKUP_STATE")
    local now=$(date +%s)
    local elapsed=$((now - last))
    local hours=$((elapsed / 3600))
    local next_hours=$(((BACKUP_INTERVAL - elapsed) / 3600))
    echo "  Last:  ${hours}h ago"
    echo "  Next:  in ${next_hours}h"
  else
    echo "  Last:  (never)"
  fi
  local last_zip
  last_zip=$(ls -1t backups/adb_full_*.zip 2>/dev/null | head -1)
  if [ -n "$last_zip" ]; then
    echo "  File:  $(basename "$last_zip") ($(du -h "$last_zip" | cut -f1))"
  fi
  echo "────────────────────────────────────"
  echo ""
}

# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------
MODE="${1:-start}"

case "$MODE" in
  --stop|stop)
    stop_all
    status_all
    ;;
  --status|status)
    status_all
    ;;
  --backup|backup)
    date -d "@0" +%s > /dev/null 2>&1
    echo "0" > "$BACKUP_STATE"   # force
    run_backup
    ;;
  --no-backup|no-backup)
    log "Starting without backup..."
    wait_for_internet || true
    start_web
    start_bot
    status_all
    ;;
  --wait-net|wait-net)
    wait_for_internet || true
    run_backup
    start_web
    start_bot
    status_all
    ;;
  start|--start|"")
    log "Starting AI Digital Brain..."
    if has_internet; then
      log "Internet: OK"
    else
      warn "Internet: NOT available"
    fi

    # Auto backup check first
    run_backup

    # Then services
    start_web
    start_bot

    echo ""
    log "Logs:"
    log "  tail -f $WEB_LOG"
    log "  tail -f $BOT_LOG"
    log "  tail -f $BACKUP_LOG"
    status_all
    ;;
  *)
    echo "Usage: $0 [start|--stop|--status|--backup|--no-backup|--wait-net]"
    exit 1
    ;;
esac
