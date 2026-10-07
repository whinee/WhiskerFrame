#!/usr/bin/env bash
# Install (or re-install) the cyberdeck CYD terminal bridge systemd service.
#
# Idempotent: safe to re-run. Installs the unit, reloads systemd, and enables +
# (re)starts the service. Run ON THE PI as root, from this directory:
#
#   chmod +x install.sh && sudo ./install.sh
#
# Prerequisite: the Pi host venv exists (pi/bootstrap.sh has been run) so
# /opt/cyd-display-link/pi/.venv/bin/python is present, I2C-0 is enabled for the
# CardKB (/dev/i2c-0), and the pre-converted splash blob has been synced (run
# `just splash` on the programmer). See ../README.md and
# docs/dev/manual-hardware-steps.md Section G.
#
# IMPORTANT: this service holds the CYD serial port EXCLUSIVELY while running.
# Before flashing the CYD firmware or using the serial link for anything else,
# stop it first:
#
#   sudo systemctl stop terminal
#
# then re-start (or re-run this installer) when done.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UNIT_SRC="${HERE}/terminal.service"
UNIT_DST="/etc/systemd/system/terminal.service"

if [ "$(id -u)" -ne 0 ]; then
    echo "install.sh must run as root (use sudo)." >&2
    exit 1
fi

# 1. systemd unit.
echo "Installing ${UNIT_DST} ..."
install -m 0644 "${UNIT_SRC}" "${UNIT_DST}"

# 2. System-wide short shell prompt (r# for root, n$ for neko).
echo "Configuring short CYD shell prompt in /etc/profile.d/cyd_prompt.sh ..."
cat << 'EOF' > /etc/profile.d/cyd_prompt.sh
if [ "$USER" = "root" ]; then
    export PS1='r# '
elif [ "$USER" = "neko" ]; then
    export PS1='n$ '
else
    export PS1='${USER:0:1}\$ '
fi
EOF
chmod 0644 /etc/profile.d/cyd_prompt.sh

for u_home in "/root" "/home/neko"; do
    if [ -d "$u_home" ]; then
        user_name="$(basename "$u_home")"
        [ "$user_name" = "root" ] && p_str="r# " || p_str="${user_name:0:1}\$ "
        bashrc_file="${u_home}/.bashrc"
        if [ -f "$bashrc_file" ]; then
            grep -q "CYD_SHORT_PROMPT" "$bashrc_file" || echo "export PS1='${p_str}' # CYD_SHORT_PROMPT" >> "$bashrc_file"
        fi
    fi
done

# 3. Reload, enable, (re)start. `enable --now` and `restart` are both idempotent.
echo "Reloading systemd and starting the service ..."
systemctl daemon-reload
systemctl enable terminal.service
systemctl restart terminal.service

# 3. Report status (do not fail the script if the pager/status returns non-zero).
echo "=== terminal status ==="
systemctl --no-pager --full status terminal.service || true
