#!/data/data/com.termux/files/usr/bin/bash
PROJECT="$HOME/ai_digital_brain"
LOG="$PROJECT/logs/watchdog.log"

mkdir -p "$PROJECT/logs"
echo "[$(date '+%F %T')] 🐕 Watchdog started" >> "$LOG"

while true; do
    # Internet မရ → skip
    if ! ping -c 1 -W 2 8.8.8.8 > /dev/null 2>&1; then
        sleep 60
        continue
    fi
    
    # Flask
    if ! pgrep -f "python run.py" > /dev/null; then
        echo "[$(date '+%F %T')] ❌ Flask down — restart" >> "$LOG"
        cd "$PROJECT" && source venv/bin/activate
        nohup python run.py > flask.log 2>&1 &
        sleep 3
    fi
    
    # Bot
    if ! pgrep -f "python bot.py" > /dev/null; then
        echo "[$(date '+%F %T')] ❌ Bot down — restart" >> "$LOG"
        cd "$PROJECT" && source venv/bin/activate
        nohup python bot.py > bot.log 2>&1 &
        sleep 2
    fi
    
    # Backup loop
    if ! pgrep -f "auto_backup_loop.sh" > /dev/null; then
        echo "[$(date '+%F %T')] ❌ Backup down — restart" >> "$LOG"
        cd "$PROJECT" && nohup ./auto_backup_loop.sh > /dev/null 2>&1 &
    fi
    
    sleep 60
done
