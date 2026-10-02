# Debugging the Cyberdeck

A field guide for humans **and** AI agents debugging the cyberdeck: the
Raspberry Pi host, the UPS Module 3S battery monitor (INA219 over I2C), the CYD
display (ESP32 + ILI9341), and the `whiskerframe` command path.

Everything here is copy-pasteable. Every command that runs **on the Pi** is
given in two forms: the raw command (run it in an SSH session on the Pi) and the
same command wrapped from your workstation over SSH.

## Identifying facts for this build

- Pi host: `root@10.0.0.212`, key `/home/lyra/.ssh/id_rsa`, deploy path
    `/opt/cyd-display-link`
- Pi venv Python: `/opt/cyd-display-link/pi/.venv/bin/python`
- UPS: INA219 on `/dev/i2c-1` at address `0x41` (3S pack, 9.0-12.6 V)
- CYD: CH340 `1a86:7523`,
    `/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0`, 115200 baud

## SSH shortcut

Define this once in your shell; every Pi command below can be run as
`$PI "<command>"`:

```sh
PI="ssh -i /home/lyra/.ssh/id_rsa root@10.0.0.212 -C"
```

Example:

```sh
$PI "i2cdetect -y 1"
```

The `-C` requests compression; the command string is re-parsed by the Pi's login
shell, so quote it as a single argument.

## The tracepoint system

Both the host tooling (`scripts/`) and the Pi daemon (`pi/battery_monitor/`)
carry an env-gated tracepoint helper (`scripts/debug.py` and
`pi/battery_monitor/debug.py`, identical stdlib-only API). Set the environment
variable `WHISKERFRAME_DEBUG` to a truthy value (`1`, `true`, or `yes`,
case-insensitive) and named test points emit a single greppable line to
**stderr**:

```text
[TP] <name> key=value key2=value2
```

Names are dotted (`module.action`), e.g. `pi_env.ssh_run`, `flash.gate`,
`ina219.read`, `daemon.poll`. When the variable is unset, every tracepoint is a
near-zero-cost no-op and nothing is printed. No timestamps are added -- journald
and your terminal already timestamp each line.

Grep for all tracepoints in a stream:

```sh
... 2>&1 | grep '\[TP\]'
```

### Enable it locally (host tooling)

```sh
WHISKERFRAME_DEBUG=1 uv run python -m scripts.pi_env_check
```

Quick proof it works (prints one line to stderr, nothing to stdout):

```sh
WHISKERFRAME_DEBUG=1 uv run python -c \
  "import sys; sys.path.insert(0,'scripts'); from debug import tracepoint; tracepoint('demo.test', a=1)"
# -> [TP] demo.test a=1   (on stderr)
```

With the variable unset the same command prints nothing.

### Enable it for the Pi daemon

Run the daemon manually with debug on (this also runs the real poll loop, so it
will publish and, if `auto_shutdown` is on and the pack is critical, could power
off -- see the safety note):

Raw (on the Pi):

```sh
WHISKERFRAME_DEBUG=1 /opt/cyd-display-link/pi/.venv/bin/python -m battery_monitor.daemon
```

Over SSH:

```sh
$PI "cd /opt/cyd-display-link/pi && WHISKERFRAME_DEBUG=1 .venv/bin/python -m battery_monitor.daemon"
```

To turn tracepoints on for the **installed systemd service**, add the
environment variable to a drop-in and restart:

Raw (on the Pi):

```sh
systemctl edit battery-monitor
# In the editor, add:
#   [Service]
#   Environment=WHISKERFRAME_DEBUG=1
systemctl restart battery-monitor
journalctl -u battery-monitor -n 50 -f
```

Over SSH (non-interactive drop-in write):

```sh
$PI "mkdir -p /etc/systemd/system/battery-monitor.service.d && printf '[Service]\nEnvironment=WHISKERFRAME_DEBUG=1\n' > /etc/systemd/system/battery-monitor.service.d/debug.conf && systemctl daemon-reload && systemctl restart battery-monitor"
$PI "journalctl -u battery-monitor -n 50 -f"
```

Remove the drop-in to disable:

```sh
$PI "rm -f /etc/systemd/system/battery-monitor.service.d/debug.conf && systemctl daemon-reload && systemctl restart battery-monitor"
```

## UPS / battery

### I2C detect (expect `41`)

Checks the INA219 answers on bus 1. Expected: the grid shows `41` at row `40`,
column `1`.

Raw (on the Pi):

```sh
i2cdetect -y 1
```

Over SSH:

```sh
$PI "i2cdetect -y 1"
```

### Live status (daemon must be running)

`status.json` is the friendly snapshot; `uevent` is the kernel
`power_supply`-format mirror.

Raw (on the Pi):

```sh
cat /run/battery_monitor/status.json
cat /run/battery_monitor/uevent
```

Over SSH:

```sh
$PI "cat /run/battery_monitor/status.json"
$PI "cat /run/battery_monitor/uevent"
```

Expected `status.json` (values vary):

```json
{
  "name": "cyberdeck_ups",
  "voltage_v": 11.67,
  "current_ma": -812.0,
  "percent": 74,
  "status": "Discharging"
}
```

Expected `uevent`:

```text
POWER_SUPPLY_NAME=cyberdeck_ups
POWER_SUPPLY_TYPE=Battery
POWER_SUPPLY_PRESENT=1
POWER_SUPPLY_CAPACITY=74
POWER_SUPPLY_STATUS=Discharging
POWER_SUPPLY_VOLTAGE_NOW=11670000
POWER_SUPPLY_CURRENT_NOW=-812000
```

### Daemon health

Raw (on the Pi):

```sh
systemctl status battery-monitor
journalctl -u battery-monitor -n 50 -f
```

Over SSH:

```sh
$PI "systemctl status battery-monitor"
$PI "journalctl -u battery-monitor -n 50 -f"
```

Expected: `active (running)`; log lines like
`INFO: 74% Discharging 11.67V -812.0mA`. With `WHISKERFRAME_DEBUG=1` you also see
`[TP] daemon.poll percent=74 status=Discharging`,
`[TP] power_supply.publish ...`, and `[TP] daemon.threshold ...`.

### Run the daemon manually with debug

Shows the full tracepoint trail (`daemon.config`, `ina219.open`,
`ina219.calibrate`, `ina219.read`, `battery.percent`, `battery.status`,
`daemon.poll`, `power_supply.publish`, `daemon.threshold`). Note it runs the real
loop; `Ctrl-C` to stop.

Raw (on the Pi):

```sh
WHISKERFRAME_DEBUG=1 /opt/cyd-display-link/pi/.venv/bin/python -m battery_monitor.daemon
```

Over SSH:

```sh
$PI "cd /opt/cyd-display-link/pi && WHISKERFRAME_DEBUG=1 .venv/bin/python -m battery_monitor.daemon"
```

### One-shot INA219 read without the daemon

Reads bus voltage and current directly via the stdlib `fcntl` driver at `0x41` --
no daemon, no publish, read-only. Useful when the service is stopped or you want
a raw sanity read.

Raw (on the Pi):

```sh
cd /opt/cyd-display-link/pi && WHISKERFRAME_DEBUG=1 .venv/bin/python -c "
from battery_monitor.ina219 import INA219
with INA219(bus=1, address=0x41) as dev:
    print('voltage_v', round(dev.bus_voltage_v(), 4))
    print('current_ma', round(dev.current_ma(), 2))
    print('shunt_mv', round(dev.shunt_mv(), 3))
    print('power_w', round(dev.power_w(), 4))
"
```

Over SSH:

```sh
$PI "cd /opt/cyd-display-link/pi && WHISKERFRAME_DEBUG=1 .venv/bin/python -c \"from battery_monitor.ina219 import INA219;
dev=INA219(bus=1, address=0x41); dev.open(); dev.calibrate();
print('voltage_v', round(dev.bus_voltage_v(),4));
print('current_ma', round(dev.current_ma(),2)); dev.close()\""
```

Expected: `voltage_v` near the pack voltage (e.g. `11.67`), `current_ma` negative
while discharging. With debug on you also see `[TP] ina219.read register=0x02
raw=...` lines.

### View the effective daemon config

Prints the resolved `DaemonConfig` the daemon actually uses (after merging
`.whiskerframe.yaml` with the built-in fallbacks).

Raw (on the Pi):

```sh
cd /opt/cyd-display-link/pi && WHISKERFRAME_DEBUG=1 .venv/bin/python -c "
from battery_monitor.daemon import load_daemon_config
print(load_daemon_config())
"
```

Over SSH:

```sh
$PI "cd /opt/cyd-display-link/pi && WHISKERFRAME_DEBUG=1 .venv/bin/python -c \"from battery_monitor.daemon import load_daemon_config; print(load_daemon_config())\""
```

Expected: a `DaemonConfig(...)` repr with `i2c_address=65` (`0x41`),
`poll_interval_s=10.0`, `auto_shutdown=True`, `critical_percent=5`. With debug on,
the `[TP] daemon.config ...` line shows the same key facts.

### Show the UPS config file

Raw (on the Pi):

```sh
cat /opt/cyd-display-link/.whiskerframe.yaml
```

Over SSH:

```sh
$PI "cat /opt/cyd-display-link/.whiskerframe.yaml"
```

The daemon resolves this file via `scripts/config.py` (`load_yaml_config`),
reading the `ups:` block; any missing key falls back to the live-verified
default. `load_daemon_config()` (above) shows the merged result.

## I2C bus

Confirm the bus device node exists, the boot config enables I2C-1, and the
kernel modules are loaded.

Raw (on the Pi):

```sh
ls /dev/i2c-*
grep -n "dtparam=i2c_arm=on" /boot/firmware/config.txt
lsmod | grep i2c
```

Over SSH:

```sh
$PI "ls /dev/i2c-*"
$PI "grep -n 'dtparam=i2c_arm=on' /boot/firmware/config.txt"
$PI "lsmod | grep i2c"
```

Expected: `/dev/i2c-1` present; the `grep` prints the uncommented
`dtparam=i2c_arm=on` line; `lsmod` shows `i2c_bcm2835` and `i2c_dev`.

## CYD (ESP32 + ILI9341 display)

### Discover the serial port (baseline diff)

Capture a baseline with the CYD **unplugged**, then plug it in and diff. Run this
on the workstation the CYD is attached to.

```sh
uv run python -c "
import sys; sys.path.insert(0,'scripts')
import device_discovery as d
base = d.capture_baseline()
input('Unplug the CYD, then plug it back in and press Enter...')
cur = d.enumerate_devices()
r = d.report(base, cur)
print('CYD ports:', r.cyd_ports)
print('Pi  ports:', r.pi_ports)
"
```

With `WHISKERFRAME_DEBUG=1` prepended you also see `[TP] discovery.enumerate ...`,
`[TP] discovery.diff ...`, and `[TP] discovery.report ...`. Expected `cyd_ports`
contains the CH340 `by-id` symlink.

### Validate a flash backup (esptool read)

The full-flash read is an **irreversible-safe, read-only** operation but is the
mandatory precursor to any write. Read 4 MiB (`0x400000`) then validate it:

```sh
esptool --port /dev/serial/by-id/usb-1a86_USB_Serial-if00-port0 --baud 460800 read-flash 0x0 0x400000 cyd_factory_backup.bin
uv run python -c "
import sys; sys.path.insert(0,'scripts')
from flash_gate import validate_backup
print(validate_backup('cyd_factory_backup.bin'))
"
```

Expected: `BackupValidation(..., valid=True, actual_size=4194304, reason=None)`.
With `WHISKERFRAME_DEBUG=1` you see `[TP] flash.validate path=... valid=True ...`.

### Serial monitor

Watch the CYD's serial output at 115200 baud:

```sh
uv run python -m serial.tools.miniterm /dev/serial/by-id/usb-1a86_USB_Serial-if00-port0 115200
```

Expected: boot banner / any firmware log. `Ctrl-]` to exit.

### Resend a smoke-test draw

Build a single centered `DRAW_TEXT`, serialize it, and send it over the serial
transport:

```sh
WHISKERFRAME_DEBUG=1 uv run python -c "
from whiskerframe import CommandBuilder, XYXY, serialize
from whiskerframe.transport import SerialTransport
cmd = CommandBuilder().draw_text(XYXY(0, 0, 319, 239), 'SMOKE', anchor='mm')
frame = serialize(cmd)
print('frame bytes:', frame.hex())
with SerialTransport('/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0', 115200) as t:
    t.send(frame)
"
```

Expected: `SMOKE` centered on the display; the printed hex is the framed bytes.

## Pi host runtime

### Environment check with debug

Verifies `python3`, `pip`, and `pyserial` over SSH and prints exactly which are
missing. Run from the workstation:

```sh
WHISKERFRAME_DEBUG=1 uv run python -m scripts.pi_env_check
```

Expected: `All components present: python3, pip, pyserial.` With debug on you see
`[TP] pi_env.ssh_run ...`, `[TP] pi_env.probe_result component=... present=...`,
and `[TP] pi_env.report missing=none all_present=True`.

### Venv Python path and uv version

Raw (on the Pi):

```sh
/opt/cyd-display-link/pi/.venv/bin/python --version
uv --version
```

Over SSH:

```sh
$PI "/opt/cyd-display-link/pi/.venv/bin/python --version"
$PI "uv --version"
```

### Re-provision the host

Idempotent; safe to re-run. From the workstation, after syncing `pi/`:

```sh
$PI "cd /opt/cyd-display-link/pi && ./bootstrap.sh"
```

## CYD terminal daemon

The terminal bridge (`pi/terminal/`, service `terminal.service`) renders a
`bash -l` login shell on the CYD. Logs go to journald; tracepoints use the
`terminal.*` namespace and gate on `WHISKERFRAME_DEBUG`.

> **Stop the service to free the serial port.** `terminal.service` holds the CYD
> serial EXCLUSIVELY. Any other serial use (re-flash, a `whiskerframe` send, a
> serial monitor) will fail with the port busy until you stop it:
>
> ```sh
> $PI "systemctl stop terminal"
> ```
>
> Re-start with `$PI "systemctl start terminal"` when done.

### Follow the daemon log

```sh
$PI "journalctl -u terminal -f"
```

Expected lines (plain): `INFO: terminal bridge started (serial ..., cardkb ...)`,
then per session `INFO:` activity. Errors (serial reopen, auth-adapter missing)
print as `ERROR:`.

### Enable terminal tracepoints

Add `Environment=WHISKERFRAME_DEBUG=1` to the unit's `[Service]` section (via a
drop-in `systemctl edit terminal`), then restart and follow the log. You will see
greppable `[TP] terminal.* ...` lines:

| Tracepoint | When |
| ---------- | ---- |
| `terminal.config` | config resolved at startup |
| `terminal.splash` | splash shown / skipped / write error |
| `terminal.login` | login screen shown |
| `terminal.auth` | an auth attempt (`user=`, `success=`; the password is NEVER logged) |
| `terminal.shell_start` | a shell spawned for a user |
| `terminal.logout` | a shell session ended (back to login) |
| `terminal.keyframe` | a periodic full-repaint keyframe fired |
| `terminal.serial_reopen` | serial opened / write error / reopen |
| `terminal.resize` | the resize chord cycled the font size |

```sh
$PI "journalctl -u terminal | grep '\[TP\] terminal'"
```

Note: `terminal.auth` logs only the username and the boolean result — the
plaintext password is never passed to a tracepoint and never appears in the
journal or on the screen (it is only ever shown masked).

### Import-check the daemon on the Pi (no display needed)

```sh
$PI "cd /opt/cyd-display-link/pi && .venv/bin/python -c \"
from terminal.daemon import load_bridge_config
from terminal.bridge import TerminalBridge, RESIZE_CHORD
c = load_bridge_config()
TerminalBridge(c)
print('config ok:', c.serial_port, 'resize chord:', hex(RESIZE_CHORD))\""
```

Expected: `config ok: /dev/serial/by-id/... resize chord: 0x1d`.

## whiskerframe command path

Build and serialize a command with tracepoints on, then round-trip decode it to
confirm the wire format is symmetric. Pure -- no hardware needed:

```sh
WHISKERFRAME_DEBUG=1 uv run python -c "
from whiskerframe import CommandBuilder, XYXY, serialize
from whiskerframe.protocol import decode
cmd = CommandBuilder().draw_text(XYXY(0, 0, 319, 239), 'HELLO', anchor='mm')
frame = serialize(cmd)
print('frame:', frame.hex())
print('round-trip ok:', decode(frame) == cmd)
"
```

Expected: `round-trip ok: True`.

## Config resolution

`.env` (gitignored; `.env.example` is the template) holds environment/deploy
values (`PI_HOST`, `PI_USER`, `DEFAULT_KEY_PATH`, `DEFAULT_VENV_PATH`).
`.whiskerframe.yaml` (committed) holds project/hardware facts (`components`,
`ups:`, `cyd:`). Both are loaded by `scripts/config.py`.

Print the resolved values:

```sh
WHISKERFRAME_DEBUG=1 uv run python -c "
import sys; sys.path.insert(0,'scripts')
from config import env, load_yaml_config
print('PI_HOST        =', env('PI_HOST', '10.0.0.212'))
print('DEFAULT_VENV_PATH =', env('DEFAULT_VENV_PATH', '/opt/cyd-display-link/pi/.venv'))
print('yaml keys      =', sorted(load_yaml_config().keys()))
"
```

With debug on you see `[TP] config.env name=... using_default=...` and
`[TP] config.yaml path=... keys=...`.

## auto_shutdown safety

`auto_shutdown` is now **ON by default** (`.whiskerframe.yaml` `ups:
auto_shutdown: true`). At or below `critical_percent` (5%) the daemon logs
`CRITICAL` **and** requests a clean `systemctl poweroff`.

A bad or spurious INA219 reading that momentarily reports <= 5% could therefore
trigger a real poweroff. To check the current setting:

```sh
$PI "grep -n auto_shutdown /opt/cyd-display-link/.whiskerframe.yaml"
```

To disable it, set `auto_shutdown: false` in `.whiskerframe.yaml` and restart the
daemon:

Over SSH:

```sh
$PI "sed -i 's/auto_shutdown: true/auto_shutdown: false/' /opt/cyd-display-link/.whiskerframe.yaml && systemctl restart battery-monitor"
```

Confirm via the effective config (see "View the effective daemon config"): the
`DaemonConfig` repr should show `auto_shutdown=False`, and with debug on the
`[TP] daemon.config ... auto_shutdown=False` line confirms it.

## Quick reference

| Goal | One-liner |
| --- | --- |
| INA219 present? | `$PI "i2cdetect -y 1"` (expect `41`) |
| Live battery snapshot | `$PI "cat /run/battery_monitor/status.json"` |
| Kernel power_supply mirror | `$PI "cat /run/battery_monitor/uevent"` |
| Daemon health | `$PI "systemctl status battery-monitor"` |
| Follow daemon logs | `$PI "journalctl -u battery-monitor -n 50 -f"` |
| Effective daemon config | `$PI "cd /opt/cyd-display-link/pi && .venv/bin/python -c \"from battery_monitor.daemon import load_daemon_config; print(load_daemon_config())\""` |
| Show UPS config | `$PI "cat /opt/cyd-display-link/.whiskerframe.yaml"` |
| I2C node exists | `$PI "ls /dev/i2c-*"` (expect `/dev/i2c-1`) |
| Check auto_shutdown | `$PI "grep -n auto_shutdown /opt/cyd-display-link/.whiskerframe.yaml"` |
| Pi env check (debug) | `WHISKERFRAME_DEBUG=1 uv run python -m scripts.pi_env_check` |
| whiskerframe round-trip | `uv run python -c "from whiskerframe import CommandBuilder,XYXY,serialize; from whiskerframe.protocol import decode; c=CommandBuilder().draw_text(XYXY(0,0,319,239),'HI',anchor='mm'); print(decode(serialize(c))==c)"` |
| Grep tracepoints | `... 2>&1 \| grep '\[TP\]'` |
