#!/usr/bin/env bash
set -euo pipefail

DEST_DIR="/home/lyra/backups/cyberdeck-pi"
SSH_KEY="/home/lyra/.ssh/id_rsa"
PI_HOST="root@10.0.0.212"
REMOTE_SRC="/mnt/250GB-SSD/backup/2026-10-14/sdcard-mmcblk0.img.zst"
LOCAL_FILE="${DEST_DIR}/sdcard-mmcblk0.img.zst"
LOG_FILE="${DEST_DIR}/rsync-thermal.log"

mkdir -p "$DEST_DIR"
echo "[$(date -u)] Starting thermal-supervised rsync of sdcard-mmcblk0.img.zst" | tee -a "$LOG_FILE"

# Background thermal monitor
monitor_thermal() {
    local rsync_pid=$1
    while kill -0 "$rsync_pid" 2>/dev/null; do
        sleep 20
        raw_temp=$(ssh -o ConnectTimeout=5 -i "$SSH_KEY" "$PI_HOST" "vcgencmd measure_temp 2>/dev/null" 2>/dev/null || echo "temp=0.0'C")
        temp=$(echo "$raw_temp" | grep -oE '[0-9]+\.[0-9]+' || echo "0.0")
        echo "[$(date -u)] Pi Temp: ${temp}°C" >> "$LOG_FILE"
        if awk "BEGIN {exit !($temp > 72.0)}"; then
            echo "[$(date -u)] THERMAL ABORT: Pi temp ${temp}°C > 72.0°C! Terminating rsync..." | tee -a "$LOG_FILE"
            kill -TERM "$rsync_pid" 2>/dev/null || true
            exit 1
        fi
    done
}

# Start rsync
rsync --partial --bwlimit=1500 -e "ssh -i $SSH_KEY" "$PI_HOST:$REMOTE_SRC" "$LOCAL_FILE" >> "$LOG_FILE" 2>&1 &
RSYNC_PID=$!

monitor_thermal "$RSYNC_PID" &
MONITOR_PID=$!

wait "$RSYNC_PID"
RSYNC_STATUS=$?

kill "$MONITOR_PID" 2>/dev/null || true

if [ $RSYNC_STATUS -eq 0 ]; then
    echo "[$(date -u)] Rsync completed successfully. Verifying SHA256..." | tee -a "$LOG_FILE"
    cd "$DEST_DIR"
    ln -sf sdcard-mmcblk0.img.zst backimg.zst
    sha256sum -c SHA256SUMS >> "$LOG_FILE" 2>&1
    echo "[$(date -u)] Verification complete." | tee -a "$LOG_FILE"
else
    echo "[$(date -u)] Rsync exited with status $RSYNC_STATUS" | tee -a "$LOG_FILE"
    exit $RSYNC_STATUS
fi
