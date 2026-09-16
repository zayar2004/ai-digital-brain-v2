#!/data/data/com.termux/files/usr/bin/bash
# AI DIGITAL BRAIN — Full System Backup

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

BACKUP_DIR="$PROJECT_DIR/backups"
mkdir -p "$BACKUP_DIR" logs

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_NAME="adb_full_${TIMESTAMP}"
STAGING_DIR="$PROJECT_DIR/logs/staging_${BACKUP_NAME}"
ZIP_PATH="$BACKUP_DIR/${BACKUP_NAME}.zip"

INCLUDE_ENV=1
INCLUDE_CODE=0
for arg in "$@"; do
  case "$arg" in
    --no-env)       INCLUDE_ENV=0 ;;
    --include-code) INCLUDE_CODE=1 ;;
  esac
done

GREEN='\033[0;32m'; YELLOW='\033[0;33m'; RED='\033[0;31m'; NC='\033[0m'
log()  { echo -e "${GREEN}[backup]${NC} $*"; }
warn() { echo -e "${YELLOW}[warn]${NC}   $*"; }

log "Preparing staging: $STAGING_DIR"
rm -rf "$STAGING_DIR"
mkdir -p "$STAGING_DIR"

# Metadata
{
  echo "AI Digital Brain — Full Backup"
  echo "Backup name:  $BACKUP_NAME"
  echo "Created at:   $(date '+%Y-%m-%d %H:%M:%S %Z')"
  echo "Host:         $(hostname 2>/dev/null || echo unknown)"
  echo "PWD:          $PROJECT_DIR"
  echo "Python:       $(python --version 2>&1 || echo unknown)"
} > "$STAGING_DIR/METADATA.txt"

# Database
if [ -f "instance/ai_brain.db" ]; then
  log "Backing up database..."
  mkdir -p "$STAGING_DIR/instance"
  cp instance/ai_brain.db "$STAGING_DIR/instance/ai_brain.db"
  log "  Database: $(du -h "$STAGING_DIR/instance/ai_brain.db" | cut -f1)"
else
  warn "Database not found: instance/ai_brain.db"
fi

# Uploads
if [ -d "uploads" ]; then
  log "Backing up uploads..."
  mkdir -p "$STAGING_DIR/uploads"
  cp -r uploads/. "$STAGING_DIR/uploads/" 2>/dev/null || true
  log "  Uploads: $(du -sh "$STAGING_DIR/uploads" | cut -f1)"
fi

# .env
if [ "$INCLUDE_ENV" = "1" ] && [ -f ".env" ]; then
  log "Backing up .env..."
  cp .env "$STAGING_DIR/.env"
  chmod 600 "$STAGING_DIR/.env"
  warn "  .env included — keep this backup secure."
fi

# Requirements
[ -f "requirements.txt" ] && cp requirements.txt "$STAGING_DIR/requirements.txt"

# Code (optional)
if [ "$INCLUDE_CODE" = "1" ]; then
  log "Backing up source code..."
  mkdir -p "$STAGING_DIR/code"
  cp -r app templates static scripts tests requirements.txt run.py bot.py "$STAGING_DIR/code/" 2>/dev/null || true
fi

# Manifest
{
  echo "== Manifest =="
  find "$STAGING_DIR" -type f -exec ls -lh {} \; 2>/dev/null | awk '{print $5, $9}'
  echo ""
  echo "== Total =="
  du -sh "$STAGING_DIR" | cut -f1
} > "$STAGING_DIR/MANIFEST.txt"

# Zip
log "Creating zip: $ZIP_PATH"
if command -v zip >/dev/null 2>&1; then
  (cd "$STAGING_DIR/.." && zip -rq "$ZIP_PATH" "$(basename "$STAGING_DIR")")
else
  # Python fallback
  python - <<PY
import shutil
shutil.make_archive("$BACKUP_DIR/$BACKUP_NAME", "zip", "$STAGING_DIR")
PY
fi

log "  Created: $(du -h "$ZIP_PATH" | cut -f1)"
rm -rf "$STAGING_DIR"

# Cleanup old (keep 30)
log "Cleaning old backups (keep last 30)..."
cd "$BACKUP_DIR"
ls -1t adb_full_*.zip 2>/dev/null | tail -n +31 | while read -r old; do
  rm -f "$old"
  log "  Removed: $old"
done

echo ""
log "════════════════════════════════════════"
log "✅ Backup: $ZIP_PATH"
log "════════════════════════════════════════"
