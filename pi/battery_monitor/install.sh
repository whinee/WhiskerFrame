#!/usr/bin/env bash
# Install (or re-install) the cyberdeck battery-monitor systemd service.
#
# Idempotent: safe to re-run. Installs the tmpfiles.d entry (creates
# /run/battery_monitor), installs the unit, reloads systemd, and enables +
# starts the service. Run ON THE PI as root, from this directory:
#
#   chmod +x install.sh && sudo ./install.sh
#
# Prerequisite: the Pi host venv exists (pi/bootstrap.sh has been run) so
# /opt/cyd-display-link/pi/.venv/bin/python is present, and I2C is enabled
# (dtparam=i2c_arm=on; /dev/i2c-1 exists). See ../README.md and
# docs/dev/manual-hardware-steps.md.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UNIT_SRC="${HERE}/battery-monitor.service"
TMPFILES_SRC="${HERE}/battery-monitor.tmpfiles.conf"

UNIT_DST="/etc/systemd/system/battery-monitor.service"
TMPFILES_DST="/etc/tmpfiles.d/battery-monitor.conf"

if [ "$(id -u)" -ne 0 ]; then
    echo "install.sh must run as root (use sudo)." >&2
    exit 1
fi

# 1. tmpfiles.d entry so /run/battery_monitor exists on boot; apply it now too.
echo "Installing ${TMPFILES_DST} ..."
install -m 0644 "${TMPFILES_SRC}" "${TMPFILES_DST}"
systemd-tmpfiles --create "${TMPFILES_DST}"

# 2. systemd unit.
echo "Installing ${UNIT_DST} ..."
install -m 0644 "${UNIT_SRC}" "${UNIT_DST}"

# 3. Reload, enable, (re)start. `enable --now` and `restart` are both idempotent.
echo "Reloading systemd and starting the service ..."
systemctl daemon-reload
systemctl enable battery-monitor.service
systemctl restart battery-monitor.service

# 4. Report status (do not fail the script if the pager/status returns non-zero).
echo "=== battery-monitor status ==="
systemctl --no-pager --full status battery-monitor.service || true
