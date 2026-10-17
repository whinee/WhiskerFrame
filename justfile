# Settings
set windows-shell := ['pwsh.exe', '-CommandWithArgs']
set positional-arguments
set dotenv-load

# Constants
dev_docs := "docs/dev"
docs_api_root_dir := "docs/api"
docs_api_unreleased_dir := docs_api_root_dir + "/unreleased"

app_id := `python -c 'exec("""\ntry:\n from alltheutils import config\n print(config.read_conf_file("dev/values/constants/main.yaml")["app_name"])\nexcept ModuleNotFoundError:\n print("PLACEHOLDER")\nexcept FileNotFoundError:\n print("FILE NOT FOUND")""")'`

app_version := `python -c 'exec("""\ntry:\n from alltheutils import config\n print(config.read_conf_file("dev/values/programmatic_variables/main.dev.json")["version"])\nexcept ModuleNotFoundError:\n print("PLACEHOLDER")\nexcept FileNotFoundError:\n print("FILE NOT FOUND")""")'`

# Choose recipes
default:
    @ just -l

[private]
black:
    @ python -m black -q examples > /dev/null 2>&1
    @ python -m black -q whiskerframe > /dev/null 2>&1
    @ python -m black -q test > /dev/null 2>&1

[private]
nio:
    @ python -m no_implicit_optional examples
    @ python -m no_implicit_optional whiskerframe
    @ python -m no_implicit_optional test

[private]
ruff:
    @ python -m ruff check --fix --exit-zero examples
    @ python -m ruff check --fix --exit-zero whiskerframe
    @ python -m ruff check --fix --exit-zero test

# Lint codebase
lint:
    @ just black
    @ just nio
    @ just ruff

test:
    python test/text_anchors.py
    python test/text_anchors_multiline.py
    python test/text_anchors_inverted_multiline.py

examples:
    python examples/01_coordinates.py
    python examples/02_text.py
    python examples/03_multiline_text.py

version:
    @ echo {{app_version}}

# Launch the desktop preview mirror connected to the cyberdeck serial port.
[unix]
preview:
    uv run python scripts/desktop_mirror.py

# Launch the desktop preview mirror in explicit mock/demo mode.
[unix]
preview-mock:
    uv run python scripts/desktop_mirror.py --mock

# Run visual verification and inspection pipeline.
[unix]
preview-inspect:
    uv run python scripts/visual_verify.py

# Stop any running desktop preview mirror processes.
[unix]
preview-stop:
    -pkill -f desktop_mirror.py

# Convert the configured boot-splash image to a 320x240 RGB565 blob (programmer-side).
[unix]
splash:
    uv run python scripts/convert_splash.py

# Rsync the Pi runtime (whiskerframe/, pi/, scripts/, firmware/dist/) to the deploy root on the Pi.
# Does NOT activate code or restart services. Infra params from .env (set dotenv-load).
[unix]
sync:
    rsync -a --exclude-from=pi/deploy-exclude.txt -e "ssh -i $DEFAULT_KEY_PATH" ./ "$PI_USER@$PI_HOST:/opt/cyd-display-link/"

# Run preflight tests locally before deployment.
[unix]
preflight:
    @ echo "=== Running pre-deploy preflight checks ==="
    uv run pytest test/ -q --maxfail=1

# Preflight checks, sync code, restart affected Pi services, and verify health.
[unix]
apply: preflight sync
    @ echo "=== Activating runtime changes on Pi ==="
    ssh -i "$DEFAULT_KEY_PATH" "$PI_USER@$PI_HOST" "systemctl restart terminal && systemctl is-active terminal"
    @ echo "[SUCCESS] terminal.service restarted and active."

# Compile CYD display link firmware and package distribution binaries with checksums.
[unix]
build-firmware:
    @ echo "=== Compiling CYD Display Link Firmware ==="
    uvx platformio run -d firmware/cyd_display_link
    @ mkdir -p firmware/dist
    @ cp firmware/cyd_display_link/.pio/build/esp32dev/bootloader.bin firmware/dist/
    @ cp firmware/cyd_display_link/.pio/build/esp32dev/partitions.bin firmware/dist/
    @ cp firmware/cyd_display_link/.pio/build/esp32dev/firmware.bin firmware/dist/
    @ (cd firmware/dist && sha256sum bootloader.bin firmware.bin partitions.bin > checksums.sha256)
    @ echo "=== Updated firmware/dist/checksums.sha256 ==="
    @ cat firmware/dist/checksums.sha256

# Safely flash compiled CYD firmware to the connected display coprocessor on the Pi.
[unix]
flash-firmware *FLAGS: sync
    @ echo "=== Flashing CYD Display Link over Pi serial link ==="
    ssh -i "$DEFAULT_KEY_PATH" "$PI_USER@$PI_HOST" "bash -c 'trap \"systemctl restart terminal\" EXIT; systemctl stop terminal; /opt/cyd-display-link/pi/.venv/bin/python /opt/cyd-display-link/scripts/flash_cyd_display_link.py --confirm {{FLAGS}}'"
    @ echo "[SUCCESS] CYD firmware flashed and terminal.service restored."

# Run full local tests and remote Pi hardware/service verification.
[unix]
verify:
    @ echo "=== Local test suite ==="
    uv run pytest test/
    @ echo "=== Pi hardware and service verification ==="
    ssh -i "$DEFAULT_KEY_PATH" "$PI_USER@$PI_HOST" "systemctl is-active terminal && ls -l /dev/serial/by-id/usb-1a86_USB_Serial-if00-port0 && i2cdetect -y 0"

# Fetch terminal daemon logs from the Pi.
[unix]
logs *FLAGS="-n 50 --no-pager":
    ssh -i "$DEFAULT_KEY_PATH" "$PI_USER@$PI_HOST" "journalctl -u terminal {{FLAGS}}"

# Query live status of cyberdeck services and attached peripherals on the Pi.
[unix]
status:
    @ echo "=== Pi Services ==="
    ssh -i "$DEFAULT_KEY_PATH" "$PI_USER@$PI_HOST" "systemctl status terminal --no-pager"
    @ echo "=== Serial Devices ==="
    ssh -i "$DEFAULT_KEY_PATH" "$PI_USER@$PI_HOST" "ls -la /dev/serial/by-id/"
    @ echo "=== I2C Devices (Bus 0) ==="
    ssh -i "$DEFAULT_KEY_PATH" "$PI_USER@$PI_HOST" "i2cdetect -y 0"

# Install Galaxy collections, then run the Ansible playbook against the Pi.
# Controller runs via uvx (no global ansible); Pi-side python still goes through uv.
[unix]
deploy: sync
    cd ansible && uvx --from ansible-core ansible-galaxy collection install -r requirements.yml
    cd ansible && uvx --from ansible-core ansible-playbook -i inventory.ini site.yml

# Generate documentation
[unix]
docs:
    #!/usr/bin/env bash
    set -euo pipefail
    TMPDIR=$(mktemp -d)
    TARGET_DIR="{{docs_api_unreleased_dir}}"

    just lint

    pdoc --force --output-dir "$TMPDIR" --template-dir dev/tpl/pdoc3 {{app_id}} >/dev/null
    
    rm -rf "$TARGET_DIR"
    mkdir -p "$TARGET_DIR"
    cp -r "$TMPDIR/{{app_id}}"/* "$TARGET_DIR"
    rm -rf "$TMPDIR"

    mkdir -p "$TARGET_DIR/dev"

    echo "Docs generated in $TARGET_DIR"

[unix]
[confirm('Are you sure you want to bump the version? [y/N]')]
bump *FLAGS:
    #!/usr/bin/env bash
    set -euo pipefail

    python -m dev.scripts.py.dev bump {{FLAGS}}

    just docs

    APP_VERSION=$(python -c 'from alltheutils.config import read_conf_file;print(read_conf_file("dev/values/programmatic_variables/main.dev.json")["version"])')

    DOCS_SOURCE_DIR="{{docs_api_unreleased_dir}}"
    DOCS_TARGET_DIR="{{docs_api_root_dir}}/$APP_VERSION"

    rm -rf "$DOCS_TARGET_DIR"
    mkdir -p "$DOCS_TARGET_DIR"
    cp -r "$DOCS_SOURCE_DIR"/* "$DOCS_TARGET_DIR"

    echo "Docs generated in $DOCS_TARGET_DIR"