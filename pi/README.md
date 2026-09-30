# CYD Display Link -- Raspberry Pi Host Runtime

Spec-driven, uv-managed runtime for the Pi Zero 2W that streams drawing commands
to the CYD. Dependencies are declared in `pyproject.toml`; `uv sync` installs them
into an isolated `.venv` with a managed Python, so the Pi's externally-managed
system Python (PEP 668) is never touched -- no `pip install --break-system-packages`,
no `error: externally-managed-environment`.

## Why not `pip install pyserial`?

RPi OS marks the system Python as externally managed (PEP 668), so system-wide
`pip install` is refused. Instead we declare the runtime here and let uv build an
isolated virtual environment. This is reproducible and version-controlled -- the
same "spec drives the install" idea as the rest of this project.

## Provision the Pi

1. Copy the repository to the Pi (the `pi/` directory must sit beside the
   `whiskerframe/` package so the local path dependency resolves), e.g.:

   ```sh
   rsync -av --exclude-from=pi/deploy-exclude.txt \
       -e "ssh -i /home/lyra/.ssh/id_rsa" \
       ./ root@10.0.0.212:/opt/cyd-display-link/
   ```

   `pi/deploy-exclude.txt` keeps AI agent rules (`.agents/`, `.kiro/`, `.cursor/`,
   etc.), dev tooling, firmware sources, docs, tests, and local build artifacts off
   the Pi. Only `whiskerframe/`, `pi/`, and `scripts/` are transferred.

2. On the Pi, provision with the bootstrap script:

   ```sh
   ssh -i /home/lyra/.ssh/id_rsa root@10.0.0.212 \
       "cd /opt/cyd-display-link/pi && ./bootstrap.sh"
   ```

   `bootstrap.sh` installs uv (if needed), runs `uv sync`, and prints the resolved
   `pyserial` / `whiskerframe` versions.

## Verify

From your workstation, re-run the environment check (it should now report all
components present, since the Pi runtime provides `pyserial` inside the venv):

```sh
uv run python -c "import sys; sys.path.insert(0,'scripts'); import pi_env_check as p; print(p.verify_pi_environment().summary)"
```

> Note: the check probes `python3 -c "import serial"` over a plain SSH login. To see
> the venv-provided pyserial, either run the probe through the venv
> (`uv run` inside `/opt/cyd-display-link/pi`) or activate it in the login shell.
> See "Env check and the venv" below.

## Run a drawing command on the Pi

```sh
ssh -i /home/lyra/.ssh/id_rsa root@10.0.0.212 \
    "cd /opt/cyd-display-link/pi && uv run python -c \"
from whiskerframe import XYWH, CommandBuilder, TextStyle, serialize
from whiskerframe.transport import SerialTransport
b = CommandBuilder()
cmd = b.draw_text(XYWH(10,10,120,60), 'Meow', anchor='mm', style=TextStyle(color=0xFFFF, font_size=2))
with SerialTransport('/dev/ttyUSB0', 115200) as t:
    t.send(serialize(cmd))
print('sent')
\""
```

(Replace `/dev/ttyUSB0` with the CYD port discovered in manual task 16.3.)

## Env check and the venv

`scripts/pi_env_check.py` probes the Pi's **uv-managed venv** interpreter at
`/opt/cyd-display-link/pi/.venv/bin/python` when it exists, and falls back to the
system `python3` otherwise. So after `bootstrap.sh` has run, the check reports
`pyserial` (and the rest) present, because it looks in the venv where the runtime
is actually installed -- not the externally-managed system Python.

If you provisioned the venv at a different path, pass it through:

```sh
uv run python -c "import sys; sys.path.insert(0,'scripts'); import pi_env_check as p; print(p.verify_pi_environment(venv_path='/your/venv').summary)"
```
