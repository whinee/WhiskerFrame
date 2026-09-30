#!/usr/bin/env bash
# Provision the Raspberry Pi host runtime for CYD Display Link.
#
# Spec-driven and PEP 668 safe: installs uv (if missing), then `uv sync` creates
# an isolated .venv with a managed Python and the dependencies declared in
# pyproject.toml. The Pi's system Python / system pip are never modified, so the
# "externally-managed-environment" error cannot occur.
#
# Run this ON THE PI, from the pi/ directory:
#   chmod +x bootstrap.sh && ./bootstrap.sh
#
# Or from your workstation over SSH (after copying the repo to the Pi):
#   ssh -i /home/lyra/.ssh/id_rsa root@10.0.0.212 \
#       "cd /opt/cyd-display-link/pi && ./bootstrap.sh"

set -euo pipefail

# 1. Ensure uv is available (user-local install; no sudo, no system pip).
if ! command -v uv >/dev/null 2>&1; then
    echo "uv not found; installing to ~/.local/bin ..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi
echo "uv: $(uv --version)"

# 2. Create the isolated environment and install declared deps from pyproject.
#    uv fetches a managed CPython >=3.12 if the system one is too old.
uv sync

# 3. Report the resolved runtime so provisioning is verifiable.
echo "=== Pi host runtime ready ==="
uv run python -c "import serial, whiskerframe; print('pyserial', serial.__version__); print('whiskerframe', whiskerframe.__all__)"
