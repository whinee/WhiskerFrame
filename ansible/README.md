# Cyberdeck Ansible deploy layer

Runs **from the dev host**, targets the Pi Zero 2W over SSH. Complements (does
not replace) the existing `pi/bootstrap.sh` + per-module `install.sh` + `uv`
path — Ansible orchestrates host-level config and the Wave 2 container stack.

## Prerequisites

- `uvx` on the dev host (no global ansible needed — the controller runs via
  `uvx --from ansible-core ...`).
- Infra params in the gitignored `.env` (loaded automatically via `.envrc` /
  direnv): `PI_HOST`, `PI_USER`, `DEFAULT_KEY_PATH`, `DEFAULT_VENV_PATH`.
  The inventory reads these with `lookup('env', ...)` — nothing is hardcoded.
- Galaxy collections from `requirements.yml` (`community.docker`,
  `community.general`). uv cannot replace Galaxy — these are Ansible plugins,
  not Python packages.

## Run

```bash
cd ansible
direnv allow            # once, if not already allowed — loads .env
uvx --from ansible-core ansible-galaxy collection install -r requirements.yml
uvx --from ansible-core ansible-playbook -i inventory.ini site.yml
```

Or from the repo root via just (also rsyncs the Pi runtime first):

```bash
just deploy
```

First contact with a new Pi host key:

```bash
ANSIBLE_HOST_KEY_CHECKING=False uvx --from ansible-core ansible-playbook -i inventory.ini site.yml
```

## Invariants

- **uv-in-venv:** every task that runs Python on the Pi goes through
  `{{ venv_path }}/bin/uv run ...`, never system python. Keeps deps
  deterministic and RAM overhead low on the Pi Zero 2W.
- **No destructive storage here:** the SSD reformat (TSK-02a) and mount
  enable are **deliberately absent** from every playbook. They stay
  human-gated per spec §2.4 / `docs/dev/ai-decisions.md` DEC-W7. No role
  formats, mounts, or wipes anything.

## Layout

- `site.yml` — top-level play; imports the Wave 2 role stubs.
- `inventory.ini` — single `pi_zero` host; all params via env lookups.
- `group_vars/cyberdeck.yml` — deploy root + venv path.
- `group_vars/cyberdeck.yml` — also derives `ssd_mount_point` / `ssd_device_uuid`
  from `.whiskerframe.yaml` (single source of truth for the storage mount).
- `requirements.yml` — Galaxy collection pins.
- `roles/journald_ssd/` — **TSK-03**: journald persistent store → SSD (with
  `/var/log/journal` symlinked out) + log2ram for `/var/log`. Asserts the SSD
  mount is live first.
- `roles/komodo/` — **TSK-04**: installs Docker (data-root on the SSD) and
  deploys Komodo 2.0 Core + FerretDB + Postgres via `docker_compose_v2`. Flat
  bash-only `.env.komodo` (0600, secrets generated once, `no_log`); periphery
  dropped and per-service `mem_limit` set for the 416MB Pi. Health verified via
  `uv run python -m komodo.healthcheck`.

Note the RAM reality: the full Komodo stack on a 416MB Pi Zero 2W leans on zram
swap; watch `dmesg | grep -i oom` on first `compose up`.
