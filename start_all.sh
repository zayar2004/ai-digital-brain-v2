#!/data/data/com.termux/files/usr/bin/bash
PROJECT="$HOME/ai_digital_brain"
LOG="$PROJECT/logs/autostart.log"
WAIT_FOR_NET=30

mkdir -p "$PROJECT/logs"
echo "[$(date '+%F %T')] ▶ start_all.sh" >> "$LOG"

# Internet စောင့်
for i in $(seq 1 $WAIT_FOR_NET); do
    if ping -c 1 -W 1 8.8.8.8 > /dev/null 2>&1; then
        echo "[$(date '+%F %T')] ✓ Internet (${i}s)" >> "$LOG"
        break
    fi
    sleep 1
done

termux-wake-lock 2>/dev/null || true
cd "$PROJECT" || exit 1

# Old process kill
pkill -9 -f "python run.py" 2>/dev/null
pkill -9 -f "python bot.py" 2>/dev/null
sleep 2

source venv/bin/activate

# Flask
nohup python run.py > flask.log 2>&1 &
echo "[$(date '+%F %T')] Flask PID: $!" >> "$LOG"
sleep 5

# Bot
nohup python bot.py > bot.log 2>&1 &
echo "[$(date '+%F %T')] Bot PID: $!" >> "$LOG"
sleep 3

# Backup loop
[ -f auto_backup_loop.sh ] && nohup ./auto_backup_loop.sh > /dev/null 2>&1 &

# Watchdog
[ -f watchdog.sh ] && nohup ./watchdog.sh > /dev/null 2>&1 &

sleep 2
echo "[$(date '+%F %T')] ✓ All started" >> "$LOG"
ps aux | grep -E "python (run|bot).py|watchdog" | grep -v grep >> "$LOG"
