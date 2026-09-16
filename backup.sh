#!/data/data/com.termux/files/usr/bin/bash
# ============================================================
# AI Digital Brain — Complete Snapshot Backup
# Usage: ./backup.sh [LABEL]
#   ./backup.sh              → AUTO
#   ./backup.sh MANUAL       → MANUAL
#   ./backup.sh before-fix   → before-fix
# ============================================================

set -e

PROJECT_DIR="$HOME/ai_digital_brain"
BACKUP_DIR="$PROJECT_DIR/backups"
SNAP_DIR="$BACKUP_DIR/snapshots"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LABEL="${1:-AUTO}"
STAMP="${LABEL}_${TIMESTAMP}"
OUTFILE="$SNAP_DIR/${STAMP}.md"
LOG="$PROJECT_DIR/backup.log"

mkdir -p "$SNAP_DIR" "$BACKUP_DIR/schema" "$BACKUP_DIR/libs" "$BACKUP_DIR/system"

cd "$PROJECT_DIR"

echo "[$(date '+%F %T')] ▶ Starting snapshot: $STAMP" | tee -a "$LOG"

# ============================================================
# Write everything to a single .md file
# ============================================================
{

echo "# AI Digital Brain — Complete Snapshot"
echo ""
echo "| | |"
echo "|---|---|"
echo "| **Label** | \`$LABEL\` |"
echo "| **Timestamp** | \`$TIMESTAMP\` |"
echo "| **Created** | $(date '+%Y-%m-%d %H:%M:%S') |"
echo "| **Project** | \`$PROJECT_DIR\` |"
echo "| **Host** | $(hostname 2>/dev/null || echo 'Termux') |"
echo ""
echo "---"
echo ""

# ---------- 1. TABLE OF CONTENTS ----------
echo "## 📑 Table of Contents"
echo ""
echo "1. [File Index](#1-file-index)"
echo "2. [Application Files](#2-application-files)"
echo "3. [Database Schema](#3-database-schema)"
echo "4. [Configuration](#4-configuration)"
echo "5. [Installed Libraries](#5-installed-libraries)"
echo "6. [System Info](#6-system-info)"
echo "7. [Running Processes](#7-running-processes)"
echo ""
echo "---"
echo ""

# ---------- 2. FILE INDEX ----------
echo "## 1. File Index"
echo ""

FILES=(
    # Core
    "run.py"
    "requirements.txt"
    # Telegram
    "app/telegram/client.py"
    "app/telegram/handlers.py"
    "app/telegram/bot.py"
    "app/telegram/__init__.py"
    # Services
    "app/services/broadcast_service.py"
    "app/services/telegram_notify_service.py"
    "app/services/knowledge_photo_service.py"
    "app/services/shop_service.py"
    # Models
    "app/models/__init__.py"
    "app/models/broadcast.py"
    "app/models/telegram_user.py"
    # Routes
    "app/routes/admin.py"
    # Config
    "app/config.py"
    "app/__init__.py"
)

echo "| File | Size | Lines | Status |"
echo "|------|------|-------|--------|"
for f in "${FILES[@]}"; do
    if [ -f "$PROJECT_DIR/$f" ]; then
        SIZE=$(wc -c < "$PROJECT_DIR/$f" | tr -d ' ')
        LINES=$(wc -l < "$PROJECT_DIR/$f" | tr -d ' ')
        echo "| \`$f\` | ${SIZE}B | ${LINES} | ✅ |"
    else
        echo "| \`$f\` | — | — | ⚠️ MISSING |"
    fi
done
echo ""
echo "---"
echo ""

# ---------- 3. APPLICATION FILES ----------
echo "## 2. Application Files"
echo ""

for f in "${FILES[@]}"; do
    if [ -f "$PROJECT_DIR/$f" ]; then
        EXT="${f##*.}"
        case "$EXT" in
            py) LANG="python" ;;
            js) LANG="javascript" ;;
            html) LANG="html" ;;
            json) LANG="json" ;;
            txt) LANG="text" ;;
            *) LANG="" ;;
        esac
        echo "### \`$f\`"
        echo ""
        echo "\`\`\`$LANG"
        cat "$PROJECT_DIR/$f"
        echo "\`\`\`"
        echo ""
    fi
done
echo "---"
echo ""

# ---------- 4. DATABASE SCHEMA ----------
echo "## 3. Database Schema"
echo ""

DB="$PROJECT_DIR/instance/ai_brain.db"
if [ -f "$DB" ]; then
    echo "**DB:** \`$DB\` ($(wc -c < "$DB" | tr -d ' ') bytes)"
    echo ""
    echo '```sql'
    sqlite3 "$DB" ".schema" 2>/dev/null || echo "-- sqlite3 not available"
    echo '```'
else
    echo "_No DB found at \`$DB\`_"
fi
echo ""
echo "---"
echo ""

# ---------- 5. CONFIGURATION ----------
echo "## 4. Configuration"
echo ""
echo "### \`app/config.py\`"
echo ""
if [ -f "$PROJECT_DIR/app/config.py" ]; then
    echo '```python'
    cat "$PROJECT_DIR/app/config.py"
    echo '```'
else
    echo "_not found_"
fi
echo ""
echo "### Environment (names only, values redacted)"
echo ""
if [ -f "$PROJECT_DIR/.env" ]; then
    echo '```'
    grep -v '^#' "$PROJECT_DIR/.env" | grep '=' | cut -d= -f1 | sed 's/$/=<REDACTED>/'
    echo '```'
else
    echo "_No .env file_"
fi
echo ""
echo "---"
echo ""

# ---------- 6. INSTALLED LIBRARIES ----------
echo "## 5. Installed Libraries"
echo ""
echo "### Python Packages (pip freeze)"
echo ""
echo '```'
if command -v pip >/dev/null 2>&1; then
    pip freeze 2>/dev/null | sort || echo "(pip freeze failed)"
else
    echo "(pip not in PATH)"
fi
echo '```'
echo ""
echo "### Termux Packages (relevant)"
echo ""
echo '```'
for pkg in python sqlite git curl openssl libffi; do
    if dpkg -l "$pkg" >/dev/null 2>&1; then
        dpkg -l "$pkg" | awk 'NR>5 {print $2, $3}'
    fi
done
echo '```'
echo ""
echo "---"
echo ""

# ---------- 7. SYSTEM INFO ----------
echo "## 6. System Info"
echo ""
echo '```'
echo "Date:     $(date)"
echo "Hostname: $(hostname 2>/dev/null || echo 'Termux')"
echo "User:     $(whoami)"
echo "PWD:      $PROJECT_DIR"
echo ""
echo "OS:       $(uname -a)"
echo "Python:   $(python --version 2>&1)"
echo "Pip:      $(pip --version 2>&1)"
echo "Sqlite3:  $(sqlite3 --version 2>&1 | head -1)"
echo "Bash:     $BASH_VERSION"
echo ""
echo "Disk usage:"
df -h "$PROJECT_DIR" 2>/dev/null | tail -2
echo ""
echo "Project size:"
du -sh "$PROJECT_DIR" 2>/dev/null
echo '```'
echo ""
echo "---"
echo ""

# ---------- 8. RUNNING PROCESSES ----------
echo "## 7. Running Processes"
echo ""
echo '```'
echo "=== Python / bot / flask ==="
ps aux | grep -iE "python|bot|flask|gunicorn" | grep -v grep || echo "(none)"
echo ""
echo "=== Listening ports ==="
(netstat -tlnp 2>/dev/null || ss -tlnp 2>/dev/null) | grep LISTEN || echo "(none)"
echo '```'
echo ""
echo "---"
echo ""
echo "## ✅ End of Snapshot"
echo ""
echo "_Generated by \`backup.sh\` on $(date '+%Y-%m-%d %H:%M:%S')_"

} > "$OUTFILE"

# ============================================================
# Sidecar files (raw copies)
# ============================================================
DATED_DIR="$BACKUP_DIR/$(date +%Y%m%d)"
mkdir -p "$DATED_DIR"
for f in "${FILES[@]}"; do
    [ -f "$PROJECT_DIR/$f" ] && cp "$PROJECT_DIR/$f" "$DATED_DIR/" 2>/dev/null || true
done

# Schema sidecar
sqlite3 "$DB" ".schema" > "$BACKUP_DIR/schema/schema_${STAMP}.sql" 2>/dev/null || true

# Libs sidecar
pip freeze > "$BACKUP_DIR/libs/pip_${STAMP}.txt" 2>/dev/null || true

# System sidecar
{
    uname -a
    python --version
    pip --version
    date
} > "$BACKUP_DIR/system/sys_${STAMP}.txt" 2>/dev/null || true

SIZE=$(wc -c < "$OUTFILE" | tr -d ' ')
LINES=$(wc -l < "$OUTFILE" | tr -d ' ')
echo "[$(date '+%F %T')] ✅ $STAMP → $OUTFILE (${SIZE}B, ${LINES}L)" | tee -a "$LOG"
echo ""
echo "✓ Snapshot: $OUTFILE"
echo "  Size: ${SIZE} bytes / ${LINES} lines"
echo "  Sidecars: $BACKUP_DIR/{schema,libs,system}/*_${STAMP}.*"
