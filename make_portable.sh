#!/data/data/com.termux/files/usr/bin/bash
# ============================================================
# Make Portable Backup — Phone-to-Phone Transfer
# ============================================================

set -e

PROJECT_DIR="$HOME/ai_digital_brain"
TS=$(date +%Y%m%d_%H%M%S)
OUTDIR="$PROJECT_DIR/portable_${TS}"

cd "$PROJECT_DIR"
mkdir -p "$OUTDIR"

echo "=== Making Portable Backup: $OUTDIR ==="

# ============================================================
# 1. requirements.txt — EXACT versions (pip freeze)
# ============================================================
echo "[1/5] Capturing pip freeze..."
pip freeze > "$OUTDIR/requirements.txt"
echo "  → $(wc -l < "$OUTDIR/requirements.txt") packages"

# ============================================================
# 2. Termux packages list
# ============================================================
echo "[2/5] Capturing Termux packages..."
dpkg --get-selections 2>/dev/null | awk '{print $1}' > "$OUTDIR/termux_packages.txt" || true
echo "  → $(wc -l < "$OUTDIR/termux_packages.txt") packages"

# ============================================================
# 3. Project tar.gz — real files (no venv, no backups)
# ============================================================
echo "[3/5] Compressing project (excluding venv, backups, .git)..."
tar --exclude='venv' \
    --exclude='.venv' \
    --exclude='env' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='*.pyo' \
    --exclude='backups' \
    --exclude='portable_*' \
    --exclude='.git' \
    --exclude='logs' \
    --exclude='*.log' \
    --exclude='nohup.out' \
    --exclude='.backup_loop.pid' \
    --exclude='instance' \
    --exclude='uploads' \
    --exclude='media_files' \
    --exclude='knowledge_photos' \
    --exclude='error_photos' \
    --exclude='broadcast_photos' \
    --exclude='static/uploads' \
    --exclude='static/photos' \
    --exclude='*.db' \
    --exclude='*.sqlite' \
    --exclude='*.sqlite3' \
    --exclude='*.tar.gz' \
    --exclude='.pytest_cache' \
    --exclude='.cache' \
    --exclude='node_modules' \
    -czf "$OUTDIR/project.tar.gz" \
    -C "$HOME" "ai_digital_brain"
echo "  → $(du -h "$OUTDIR/project.tar.gz" | cut -f1)"

# ============================================================
# 4. SNAPSHOT.md — Human-readable single file
# ============================================================
echo "[4/5] Building SNAPSHOT.md..."

{
    echo "# AI Digital Brain — Portable Snapshot"
    echo ""
    echo "| | |"
    echo "|---|---|"
    echo "| **Created** | $(date '+%Y-%m-%d %H:%M:%S') |"
    echo "| **Python** | $(python --version 2>&1) |"
    echo "| **Pip** | $(pip --version 2>&1) |"
    echo "| **Termux** | $(uname -m) |"
    echo ""
    echo "## 📦 How to Restore on New Phone"
    echo ""
    echo '```bash'
    echo "# 1. Install Termux (F-Droid version)"
    echo "pkg update && pkg upgrade -y"
    echo "pkg install python sqlite git curl openssl libffi -y"
    echo ""
    echo "# 2. Extract project"
    echo "cd ~"
    echo "tar -xzf project.tar.gz"
    echo ""
    echo "# 3. Create venv"
    echo "cd ai_digital_brain"
    echo "python -m venv venv"
    echo "source venv/bin/activate"
    echo ""
    echo "# 4. Install libraries (EXACT versions)"
    echo "pip install -r requirements.txt"
    echo ""
    echo "# 5. Copy config (manually — .env)"
    echo "#    Edit app/config.py if needed"
    echo ""
    echo "# 6. Run"
    echo "python run.py          # Flask"
    echo "python bot.py          # Bot (other terminal)"
    echo '```'
    echo ""
    echo "---"
    echo ""
    echo "## 1. requirements.txt (pip freeze — EXACT)"
    echo ""
    echo '```'
    cat "$OUTDIR/requirements.txt"
    echo '```'
    echo ""
    echo "## 2. Termux Packages"
    echo ""
    echo '```'
    cat "$OUTDIR/termux_packages.txt" 2>/dev/null | head -50
    echo '```'
    echo ""
    echo "## 3. Config File (app/config.py)"
    echo ""
    echo '```python'
    cat app/config.py 2>/dev/null || echo "# not found"
    echo '```'
    echo ""
    echo "## 4. Database Schema"
    echo ""
    echo '```sql'
    sqlite3 instance/ai_brain.db ".schema" 2>/dev/null || echo "-- no db"
    echo '```'
    echo ""
    echo "## 5. File Structure"
    echo ""
    echo '```'
    find . -type f -name "*.py" -not -path "./venv/*" -not -path "./backups/*" | sort
    echo '```'
    echo ""
    echo "## 6. Critical Files"
    echo ""
    for f in app/telegram/client.py app/telegram/handlers.py app/telegram/bot.py \
             app/services/broadcast_service.py run.py; do
        if [ -f "$f" ]; then
            echo "### \`$f\`"
            echo ""
            echo '```python'
            cat "$f"
            echo '```'
            echo ""
        fi
    done
    echo "---"
    echo "_End of snapshot_"
} > "$OUTDIR/SNAPSHOT.md"

echo "  → $(du -h "$OUTDIR/SNAPSHOT.md" | cut -f1)"

# ============================================================
# 4.5. DB + .env — CRITICAL
# ============================================================
echo "[4.5/6] Copying DB + .env..."

if [ -f "instance/ai_brain.db" ]; then
    cp "instance/ai_brain.db" "$OUTDIR/ai_brain.db"
    echo "  → DB: $(du -h "$OUTDIR/ai_brain.db" | cut -f1)"
else
    echo "  ⚠️  No DB found"
fi

if [ -f ".env" ]; then
    cp ".env" "$OUTDIR/.env"
    echo "  → .env: $(wc -c < "$OUTDIR/.env") bytes"
fi

# ============================================================
# 5. setup.sh — Auto-install for new phone
# ============================================================
echo "[5/6] Writing setup.sh..."

cat > "$OUTDIR/setup.sh" <<'SETUP'
#!/data/data/com.termux/files/usr/bin/bash
# ============================================================
# Auto-Setup for New Phone
# ============================================================
set -e

echo "=== AI Brain — New Phone Setup ==="
echo ""

# 1. Check Termux
if [ ! -d "/data/data/com.termux" ]; then
    echo "❌ This script must run in Termux"
    exit 1
fi

# 2. Install system packages
echo "[1/6] Installing Termux packages..."
pkg update -y
pkg install -y python sqlite git curl openssl libffi rust clang

# 3. Extract project
echo "[2/6] Extracting project..."
if [ -f "project.tar.gz" ]; then
    tar -xzf project.tar.gz -C "$HOME"
    echo "  ✓ Extracted to $HOME/ai_digital_brain"
else
    echo "❌ project.tar.gz not found in current dir"
    exit 1
fi

cd "$HOME/ai_digital_brain"

# 4. Create venv
echo "[3/6] Creating virtual environment..."
python -m venv venv
source venv/bin/activate

# 5. Install pip packages
echo "[4/6] Installing Python libraries (exact versions)..."
pip install --upgrade pip
pip install -r requirements.txt

# 6. Verify
echo "[5/6] Verifying imports..."
python -c "import flask, httpx, sqlalchemy; print('✓ Core libs OK')" || true

# 6b. Restore DB
if [ -f "ai_brain.db" ]; then
    mkdir -p instance
    cp ai_brain.db instance/ai_brain.db
    echo "  ✓ DB restored"
fi

# 6c. Restore .env
if [ -f ".env" ] && [ ! -f ".env.bak" ]; then
    cp .env .env
    echo "  ✓ .env in place"
fi

# 7. Verify
echo "[6/6] Verifying..."
if [ ! -f ".env" ]; then
    echo "⚠️  No .env file — edit app/config.py with your tokens"
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Edit app/config.py (bot token, API URL)"
echo "  2. source venv/bin/activate"
echo "  3. python run.py  (Flask — Terminal 1)"
echo "  4. python bot.py  (Bot — Terminal 2)"
SETUP

chmod +x "$OUTDIR/setup.sh"
echo "  → setup.sh ready"

# ============================================================
# Final listing
# ============================================================
echo ""
echo "=== ✅ Portable Backup Ready ==="
echo ""
ls -lah "$OUTDIR/"
echo ""
echo "Total: $(du -sh "$OUTDIR/" | cut -f1)"
echo ""
echo "📍 Location: $OUTDIR"
echo ""
echo "Transfer options:"
echo "  1. Copy folder to SD card / Drive"
echo "  2. Upload project.tar.gz to Telegram/Drive"
echo "  3. Run setup.sh on new phone"
