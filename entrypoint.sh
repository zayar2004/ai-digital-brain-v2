#!/bin/bash
set -e

echo "🚀 AI Digital Brain — starting"

# Init DB if missing
if [ ! -f /app/instance/ai_brain.db ]; then
    echo "📦 Initializing database..."
    python -m scripts.init_db || echo "⚠️ init_db failed or already exists"
fi

# Start Bot in background
echo "🤖 Starting Telegram Bot..."
python bot.py > logs/bot.log 2>&1 &
BOT_PID=$!
echo "   Bot PID: $BOT_PID"

# Trap to cleanup
trap "kill $BOT_PID 2>/dev/null; exit" SIGTERM SIGINT

# Start Flask (foreground)
echo "🌐 Starting Flask on port ${PORT:-5000}..."
exec python run.py
