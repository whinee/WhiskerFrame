#!/usr/bin/env bash
# scripts/apply-tsk05-safely.sh
#
# Standalone, safe deployment automation for TSK-05 (Offline Network Automation:
# iwd client mode + hostapd/dnsmasq AP fallback + network-arbiter).
#
# MANDATORY SAFETY SPECIFICATION (DEC-W13 / WS-I):
# - MUST implement a 90-second rescue timer (`systemd-run --on-active=90 ...`)
#   on the target Pi before applying any disruptive network changes.
# - The timer automatically triggers /var/tmp/tsk05-rescue-rollback.sh to
#   restore NetworkManager and wpa_supplicant, flush AP addresses, and restore wlan0
#   if connectivity or the default route is lost.
# - Includes verification checks: ping gateway, verify default route, verify SSH responsiveness.
# - If and ONLY if all checks succeed, the rescue timer is disarmed.
#
# NOTE: DO NOT EXECUTE ON THE PI DIRECTLY!
# This script is staged on the development host for future operator-authorized execution.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Load environment configuration if available
if [ -f "${REPO_ROOT}/.env" ]; then
    # shellcheck disable=SC1091
    source "${REPO_ROOT}/.env"
fi

PI_HOST="${PI_HOST:-10.0.0.212}"
PI_USER="${PI_USER:-root}"
SSH_KEY="${DEFAULT_KEY_PATH:-${HOME}/.ssh/id_ed25519}"
RESCUE_TIMEOUT_SECS=90
ROLLBACK_SCRIPT="/var/tmp/tsk05-rescue-rollback.sh"
SNAPSHOT_PATH="/var/tmp/tsk05-pre-switch-state.txt"
SENTINEL_PATH="/run/cyberdeck-network-automation/connectivity-confirmed"

log() {
    printf "[%s] [TSK-05-SAFE] %s\n" "$(date +'%Y-%m-%d %H:%M:%S')" "$*"
}

err() {
    printf "[%s] [TSK-05-SAFE] ERROR: %s\n" "$(date +'%Y-%m-%d %H:%M:%S')" "$*" >&2
}

ssh_cmd() {
    ssh -o BatchMode=yes \
        -o ConnectTimeout=5 \
        -o StrictHostKeyChecking=accept-new \
        -i "${SSH_KEY}" \
        "${PI_USER}@${PI_HOST}" "$@"
}

log "======================================================================"
log "WhiskerFrame TSK-05 Safe Deployment Runner"
log "Target Host: ${PI_USER}@${PI_HOST}"
log "Rescue Timer Window: ${RESCUE_TIMEOUT_SECS} seconds"
log "======================================================================"

# -----------------------------------------------------------------------------
# 1. Pre-flight checks on developer host & remote target
# -----------------------------------------------------------------------------
log "Step 1: Running pre-flight checks..."

if [ ! -f "${SSH_KEY}" ]; then
    err "SSH private key not found at ${SSH_KEY}"
    exit 1
fi

if ! ssh_cmd "echo 'SSH probe successful'" >/dev/null 2>&1; then
    err "Unable to reach ${PI_USER}@${PI_HOST} via SSH. Aborting switch."
    exit 1
fi

log "SSH connectivity confirmed."

# -----------------------------------------------------------------------------
# 2. Capture known-good network snapshot on the Pi
# -----------------------------------------------------------------------------
log "Step 2: Capturing known-good network state on the Pi..."
ssh_cmd "bash -s" <<EOF
set -euo pipefail
mkdir -p /var/tmp
cat <<STATE > "${SNAPSHOT_PATH}"
# Known-good network snapshot captured at \$(date -u +'%Y-%m-%dT%H:%M:%SZ')
## Interfaces & Addresses
\$(ip -o addr show)
## Routing Table
\$(ip route show)
## Systemd Unit States
NetworkManager: \$(systemctl is-active NetworkManager 2>/dev/null || echo 'inactive')
wpa_supplicant: \$(systemctl is-active wpa_supplicant 2>/dev/null || echo 'inactive')
STATE
chmod 0600 "${SNAPSHOT_PATH}"
EOF
log "Known-good state saved to ${SNAPSHOT_PATH} on target."

# -----------------------------------------------------------------------------
# 3. Stage the rescue rollback script on the Pi
# -----------------------------------------------------------------------------
log "Step 3: Staging standalone rescue rollback script at ${ROLLBACK_SCRIPT}..."
ssh_cmd "cat <<'EOF' > '${ROLLBACK_SCRIPT}'
#!/usr/bin/env bash
# /var/tmp/tsk05-rescue-rollback.sh
# Emergency network rollback triggered by 90-second rescue timer
set -uo pipefail

log_msg() {
    logger -t tsk05-rescue -- \"\$*\"
    echo \"[tsk05-rescue] \$*\" >&2
}

log_msg \"RESCUE TIMER EXPIRED: Initiating emergency rollback to NetworkManager...\"

# 1. Stop all TSK-05 components
systemctl stop network-arbiter.timer 2>/dev/null || true
systemctl stop network-arbiter.service 2>/dev/null || true
systemctl stop hostapd.service 2>/dev/null || true
systemctl stop dnsmasq.service 2>/dev/null || true
systemctl stop iwd.service 2>/dev/null || true
systemctl disable iwd.service 2>/dev/null || true

# 2. Flush any static IP assigned to wlan0 during AP mode
ip addr flush dev wlan0 2>/dev/null || true

# 3. Unmask, enable, and start standard NetworkManager stack
for unit in NetworkManager.service wpa_supplicant.service; do
    systemctl unmask \"\$unit\" 2>/dev/null || true
    systemctl enable \"\$unit\" 2>/dev/null || true
    systemctl start \"\$unit\" 2>/dev/null || true
done

# 4. Bring wireless interface up
ip link set wlan0 up 2>/dev/null || true

# 5. Mark rollback execution
echo \"rollback-executed \$(date -u +'%Y-%m-%dT%H:%M:%SZ')\" > /var/tmp/tsk05-rollback-fired.marker

log_msg \"Rollback finished: NetworkManager and wpa_supplicant restored.\"
EOF
chmod 0755 '${ROLLBACK_SCRIPT}'
"
log "Rescue rollback script staged."

# -----------------------------------------------------------------------------
# 4. Arm the 90-second rescue timer via systemd-run
# -----------------------------------------------------------------------------
log "Step 4: Arming ${RESCUE_TIMEOUT_SECS}-second rescue timer on target..."
ssh_cmd "systemd-run \
    --unit=tsk05-rescue-timer \
    --description='TSK-05 Network Rescue 90s Rollback' \
    --on-active=${RESCUE_TIMEOUT_SECS} \
    '${ROLLBACK_SCRIPT}'"

log "Rescue timer armed. If not disarmed within ${RESCUE_TIMEOUT_SECS}s, the system will auto-revert."

# -----------------------------------------------------------------------------
# 5. Execute TSK-05 network migration
# -----------------------------------------------------------------------------
log "Step 5: Applying TSK-05 offline network automation playbooks..."
ANSIBLE_CMD="cd ansible && uvx --from ansible-core ansible-playbook -i inventory.ini site.yml --tags network -e network_automation_apply=true"

if (cd "${REPO_ROOT}" && eval "${ANSIBLE_CMD}"); then
    log "Ansible network_automation tasks executed successfully."
else
    err "Ansible execution reported errors. Entering health verification to check connectivity."
fi

# -----------------------------------------------------------------------------
# 6. Safety Verification: Ping gateway, verify default route, check SSH
# -----------------------------------------------------------------------------
log "Step 6: Running safety & health verification checks on target..."

CHECK_ATTEMPTS=6
CHECK_INTERVAL=3
VERIFIED=false

for attempt in $(seq 1 "${CHECK_ATTEMPTS}"); do
    log "Verification attempt ${attempt}/${CHECK_ATTEMPTS}..."

    # Check 1: SSH connection responsiveness
    if ! ssh_cmd "echo 'ping'" >/dev/null 2>&1; then
        log "SSH unresponsive on attempt ${attempt}. Waiting ${CHECK_INTERVAL}s..."
        sleep "${CHECK_INTERVAL}"
        continue
    fi

    # Check 2: Default route presence on Pi
    HAS_ROUTE=$(ssh_cmd "ip route show | grep -c '^default' || true")
    if [ "${HAS_ROUTE}" -eq 0 ]; then
        log "No default route detected on target. Waiting ${CHECK_INTERVAL}s..."
        sleep "${CHECK_INTERVAL}"
        continue
    fi

    # Check 3: Gateway ping check
    GW_PING=$(ssh_cmd "bash -c '
        GW=\$(ip route show default | awk \"{print \\\$3}\" | head -n1)
        if [ -n \"\$GW\" ] && ping -c 2 -W 2 \"\$GW\" >/dev/null 2>&1; then
            echo \"OK\"
        else
            echo \"FAIL\"
        fi
    '")

    if [ "${GW_PING}" = "OK" ]; then
        log "Gateway ping successful!"
        VERIFIED=true
        break
    else
        log "Gateway ping failed on attempt ${attempt}. Waiting ${CHECK_INTERVAL}s..."
        sleep "${CHECK_INTERVAL}"
    fi
done

# -----------------------------------------------------------------------------
# 7. Disarm timer on success OR wait for rescue rollback on failure
# -----------------------------------------------------------------------------
if [ "${VERIFIED}" = "true" ]; then
    log "======================================================================"
    log "SUCCESS: All safety checks passed! Disarming rescue rollback timer..."
    log "======================================================================"

    ssh_cmd "bash -s" <<EOF
set -euo pipefail
# Stop and reset the transient rescue timer
systemctl stop tsk05-rescue-timer.timer 2>/dev/null || true
systemctl reset-failed tsk05-rescue-timer.timer 2>/dev/null || true

# Create connectivity confirmed sentinel for the network-rollback role
mkdir -p "\$(dirname "${SENTINEL_PATH}")"
echo "confirmed \$(date -u +'%Y-%m-%dT%H:%M:%SZ')" > "${SENTINEL_PATH}"
chmod 0644 "${SENTINEL_PATH}"

# Disarm network_automation persistent rollback timer if active
systemctl stop network-rollback.timer 2>/dev/null || true
systemctl disable network-rollback.timer 2>/dev/null || true
EOF

    log "Rescue timer safely DISARMED. TSK-05 deployment is permanent."
    exit 0
else
    err "======================================================================"
    err "CRITICAL: Verification checks FAILED or connection dropped!"
    err "DO NOT PANIC: The 90-second rescue timer will fire automatically."
    err "NetworkManager and wpa_supplicant will be restored on target."
    err "Wait 90 seconds, then reconnect via SSH to inspect /var/tmp/tsk05-pre-switch-state.txt."
    err "======================================================================"
    exit 2
fi
