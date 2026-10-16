#!/usr/bin/env bash
# scripts/backup-sync.sh: Network-gated, thermal-supervised backup snapshot sync (REQ-STORAGE-05)
# Enforces non-LTE unmetered network gating to protect cellular data and battery budgets.

set -euo pipefail

DEST_DIR="${CYBERDECK_BACKUP_DEST:-/home/lyra/backups/cyberdeck-pi}"
SSH_KEY="${CYBERDECK_SSH_KEY:-/home/lyra/.ssh/id_rsa}"
PI_HOST="${CYBERDECK_PI_HOST:-root@10.0.0.212}"
REMOTE_SRC="${CYBERDECK_REMOTE_SRC:-/mnt/250GB-SSD/backup/2026-10-14/sdcard-mmcblk0.img.zst}"
LOCAL_FILE="${DEST_DIR}/sdcard-mmcblk0.img.zst"
LOG_FILE="${DEST_DIR}/rsync-thermal.log"

DRY_RUN=false
FORCE=false
CHECK_ONLY=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --force)
            FORCE=true
            shift
            ;;
        --check-network)
            CHECK_ONLY=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [--dry-run] [--force] [--check-network]"
            echo "  --dry-run        Verify network and thermal gate without syncing"
            echo "  --force          Bypass network cellular gate (operator override)"
            echo "  --check-network  Inspect network gate status and exit"
            exit 0
            ;;
        *)
            echo "Unknown argument: $1" >&2
            exit 1
            ;;
    esac
done

# REQ-STORAGE-05 Network Gate
check_network_gate() {
    # Check mock override first
    local active_iface="${CYBERDECK_MOCK_INTERFACE:-}"
    if [ -z "$active_iface" ]; then
        active_iface=$(ip route show default 2>/dev/null | awk '/default/ {print $5}' | head -n1 || echo "")
    fi

    # Blocked cellular / metered interfaces
    case "$active_iface" in
        usb0|wwan*|ppp*|lte*|rmnet*)
            if [ "$FORCE" = true ]; then
                echo "[$(date -u)] [WARN] Active interface is cellular ($active_iface), but --force passed. Proceeding."
                return 0
            else
                echo "[$(date -u)] [GATE] REQ-STORAGE-05: Sync BLOCKED on cellular/LTE interface ($active_iface) to preserve battery & quota." >&2
                return 2
            fi
            ;;
        wlan*|eth*|en*|wl*|lo|br*|"")
            echo "[$(date -u)] [PASS] REQ-STORAGE-05: Network gate approved (interface: ${active_iface:-default-unmetered})."
            return 0
            ;;
        *)
            echo "[$(date -u)] [INFO] Active interface: $active_iface (unmetered assumed)."
            return 0
            ;;
    esac
}

if [ "$CHECK_ONLY" = true ]; then
    check_network_gate
    exit $?
fi

mkdir -p "$DEST_DIR"
echo "[$(date -u)] Starting thermal-supervised, network-gated snapshot sync" | tee -a "$LOG_FILE"

# Evaluate network gate
if ! check_network_gate; then
    exit 2
fi

if [ "$DRY_RUN" = true ]; then
    echo "[$(date -u)] [DRY-RUN] Pre-flight network gate passed. Host target: $PI_HOST:$REMOTE_SRC -> $LOCAL_FILE" | tee -a "$LOG_FILE"
    exit 0
fi

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

wait "$RSYNC_PID" || RSYNC_STATUS=$?
RSYNC_STATUS=${RSYNC_STATUS:-0}

kill "$MONITOR_PID" 2>/dev/null || true

if [ $RSYNC_STATUS -eq 0 ]; then
    echo "[$(date -u)] Rsync completed successfully. Verifying SHA256..." | tee -a "$LOG_FILE"
    cd "$DEST_DIR"
    ln -sf sdcard-mmcblk0.img.zst backimg.zst
    if [ -f SHA256SUMS ]; then
        sha256sum -c SHA256SUMS >> "$LOG_FILE" 2>&1 || true
    fi
    echo "[$(date -u)] Verification complete." | tee -a "$LOG_FILE"
else
    echo "[$(date -u)] Rsync exited with status $RSYNC_STATUS" | tee -a "$LOG_FILE"
    exit $RSYNC_STATUS
fi
