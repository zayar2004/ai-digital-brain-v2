#!/data/data/com.termux/files/usr/bin/bash
# Restore AI Digital Brain from backup

set -euo pipefail
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

GREEN='\033[0;32m'; YELLOW='\033[0;33m'; RED='\033[0;31m'; NC='\033[0m'
log()  { echo -e "${GREEN}[restore]${NC} $*"; }
warn() { echo -e "${YELLOW}[warn]${NC}    $*"; }
err()  { echo -e "${RED}[error]${NC}   $*" >&2; }

if [ "${1:-}" = "--list" ] || [ -z "${1:-}" ]; then
  echo "Available backups:"
  ls -lht backups/adb_full_*.zip 2>/dev/null | awk '{print "  " $9, "(" $5 ")"}'
  echo ""
  echo "Usage: $0 <backup.zip>"
  exit 0
fi

ZIP="$1"
[ -f "$ZIP" ] || { err "Not found: $ZIP"; exit 1; }

log "Safety: creating pre-restore backup..."
bash scripts/backup_full.sh --no-env >/dev/null 2>&1 || warn "Safety backup failed"

log "Stopping services..."
bash scripts/auto_start.sh --stop || true

EXTRACT_DIR="$PROJECT_DIR/logs/restore_$$"
mkdir -p "$EXTRACT_DIR"
log "Extracting: $ZIP"
unzip -q "$ZIP" -d "$EXTRACT_DIR"

INNER=$(find "$EXTRACT_DIR" -maxdepth 1 -type d -name "adb_full_*" | head -1)
[ -n "$INNER" ] || { err "Invalid backup"; exit 1; }

if [ -f "$INNER/instance/ai_brain.db" ]; then
  log "Restoring database..."
  mkdir -p instance
  [ -f instance/ai_brain.db ] && mv instance/ai_brain.db "instance/ai_brain.db.pre_restore_$(date +%s)"
  cp "$INNER/instance/ai_brain.db" instance/ai_brain.db
  log "  ✓ Database"
fi

if [ -d "$INNER/uploads" ]; then
  log "Restoring uploads..."
  cp -r "$INNER/uploads/." uploads/ 2>/dev/null || true
  log "  ✓ Uploads"
fi

if [ -f "$INNER/.env" ]; then
  warn "Backup contains .env"
  read -p "Restore .env? (y/N): " -n 1 -r; echo
  if [[ $REPLY =~ ^[Yy]$ ]]; then
    [ -f .env ] && cp .env ".env.pre_restore_$(date +%s)"
    cp "$INNER/.env" .env
    log "  ✓ .env"
  fi
fi

rm -rf "$EXTRACT_DIR"
log "Restarting services..."
bash scripts/auto_start.sh start || true

log "════════════════════════════════════════"
log "✅ Restore complete"
log "════════════════════════════════════════"
