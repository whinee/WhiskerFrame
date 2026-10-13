## §5. Standard Operating Procedures (SOPs)

### §5.1 Remote Deployment & Wheel Sync

```bash
# Infra params (PI_HOST / PI_USER / DEFAULT_KEY_PATH) are sourced from .env.
# 1. Sync workspace to Pi (excluding build artifacts and local caches)
rsync -a --exclude-from=pi/deploy-exclude.txt -e "ssh -i ${DEFAULT_KEY_PATH}" ./ ${PI_USER}@${PI_HOST}:/opt/cyd-display-link/

# 2. Reinstall whiskerframe wheel into Pi runtime environment
ssh -i ${DEFAULT_KEY_PATH} ${PI_USER}@${PI_HOST} "cd /opt/cyd-display-link/pi && uv pip install --reinstall-package whiskerframe ."
```

### §5.2 Safe CYD Reflashing (Via Pi Bridge)

```bash
# 1. Build binary locally
uvx --from platformio pio run -d firmware/cyd_display_link

# 2. Stop terminal service to free /dev/ttyUSB0
ssh -i ${DEFAULT_KEY_PATH} ${PI_USER}@${PI_HOST} "systemctl stop terminal && fuser -k /dev/ttyUSB0 || true"

# 3. Execute flash write from Pi venv
ssh -i ${DEFAULT_KEY_PATH} ${PI_USER}@${PI_HOST} "/opt/cyd-display-link/pi/.venv/bin/python -m esptool --chip esp32 --port /dev/serial/by-id/usb-1a86_USB_Serial-if00-port0 --baud 460800 --before default-reset --after hard-reset write-flash -z 0x10000 /opt/cyd-flash/firmware.bin"

# 4. Resume terminal service
ssh -i ${DEFAULT_KEY_PATH} ${PI_USER}@${PI_HOST} "systemctl start terminal"
```
