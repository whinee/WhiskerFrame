# Battery Monitor -- Cyberdeck UPS Module 3S (INA219)

A small, railguarded systemd daemon that reads the UPS Module 3S's Texas
Instruments **INA219** over I2C and publishes the pack state to the kernel
`power_supply` class, so the operating system sees the cyberdeck's battery as if
it were a real one.

Stdlib-only on the I2C path (no `smbus`/`smbus2`), so it runs inside the minimal
uv-managed Pi venv that ships only `pydantic` / `pyserial`.

## What it does

Every poll (default 10 s) the daemon:

1. Reads the INA219 bus voltage and current over `/dev/i2c-1`.
2. Converts the bus voltage to a 0-100 % state of charge for the 3S pack
   (linear map, `voltage_empty..voltage_full`, clamped).
3. Derives a status: `Charging`, `Discharging`, `Full` (near 100 %), or
   `Not charging` (idle current).
4. Publishes the reading to `/run/battery_monitor/`:
   - `uevent` -- kernel `power_supply`-formatted key/value file
     (`POWER_SUPPLY_NAME`, `POWER_SUPPLY_TYPE=Battery`, `POWER_SUPPLY_CAPACITY`,
     `POWER_SUPPLY_STATUS`, `POWER_SUPPLY_VOLTAGE_NOW` in microvolts,
     `POWER_SUPPLY_CURRENT_NOW` in microamps).
   - `status.json` -- a friendly JSON snapshot.
5. Logs one line to the journal (`journalctl -u battery-monitor`).

### Railguards

- A transient I2C error never crashes the daemon; it is logged and retried with
  bounded exponential backoff (1 s -> 30 s), reset on the next good read.
- At/below `critical_percent` the daemon logs `CRITICAL`. It powers off when
  `auto_shutdown` is `true`, which is now the **default** (a clean poweroff at 5%
  protects the pack). A spurious reading at <= 5% could trigger a real poweroff;
  set `auto_shutdown: false` and restart to disable.
- The I2C bus is read-only except for the INA219's one-time calibration/config
  write the chip requires.
- The systemd unit is hardened (`NoNewPrivileges`, `ProtectSystem=strict`,
  `PrivateTmp`, `DeviceAllow=/dev/i2c-1` with `DevicePolicy=closed`,
  `ReadWritePaths=/run/battery_monitor`).

## Configuration

All values come from the committed `.whiskerframe.yaml` `ups:` block (no
hard-coding, per the reproducible-build rule). Missing keys fall back to the
live-verified hardware defaults.

| Key | Default | Meaning |
| --- | --- | --- |
| `chip` | `INA219` | Monitor chip (informational). |
| `i2c_bus` | `1` | `/dev/i2c-N` bus number. |
| `i2c_address` | `0x41` | INA219 slave address (from `i2cdetect -y 1`). |
| `cells_series` | `3` | 3S pack (informational). |
| `voltage_full` | `12.6` | Bus voltage (V) treated as 100 %. |
| `voltage_empty` | `9.0` | Bus voltage (V) treated as 0 %. |
| `shunt_ohms` | `0.1` | Shunt resistor (informational; cal is fixed at 4096). |
| `low_battery_percent` | `15` | Log `WARNING` at/below. |
| `critical_percent` | `5` | Log `CRITICAL` at/below (+ shutdown if enabled). |
| `poll_interval_seconds` | `10` | Seconds between polls. |
| `auto_shutdown` | `true` | Power off cleanly at critical (5%) to protect the pack. |
| `power_supply_name` | `cyberdeck_ups` | `POWER_SUPPLY_NAME` published. |

## Install

Prerequisites: I2C enabled (`dtparam=i2c_arm=on`, so `/dev/i2c-1` exists) and the
Pi host venv provisioned (`pi/bootstrap.sh`, giving
`/opt/cyd-display-link/pi/.venv/bin/python`). See
`docs/dev/manual-hardware-steps.md`.

On the Pi, from this directory:

```sh
chmod +x install.sh && sudo ./install.sh
```

`install.sh` is idempotent: it installs the `tmpfiles.d` entry (creates
`/run/battery_monitor`), installs the unit to `/etc/systemd/system/`, runs
`daemon-reload`, `enable --now`, and prints `systemctl status`. Re-running it is
safe.

## Read the status

```sh
cat /run/battery_monitor/status.json      # JSON snapshot
cat /run/battery_monitor/uevent           # kernel power_supply mirror
systemctl status battery-monitor          # service health
journalctl -u battery-monitor -f          # live logs
```

## Debugging

Set `WHISKERFRAME_DEBUG=1` to emit greppable `[TP] <name> key=value ...`
tracepoints (e.g. `daemon.config`, `daemon.poll`, `ina219.read`,
`power_supply.publish`) to stderr / the journal. See **`docs/dev/debug.md`** for
the full tracepoint reference, one-shot INA219 reads, effective-config dumps, and
the `auto_shutdown` safety note.

## Kernel `power_supply`: userspace mirror vs. in-kernel `ina2xx`

This daemon implements a **userspace** `power_supply`-class mirror: it writes the
same `POWER_SUPPLY_*` `uevent` grammar the kernel emits, under
`/run/battery_monitor/`. This works on the **stock Raspberry Pi OS image with no
kernel rebuild**, which is why it is the robust default for this exact board.

An **even more kernel-native** option exists: the mainline **`ina2xx`** hwmon
driver can bind the INA219 via a **device-tree overlay**, exposing it under
`/sys/class/hwmon`. Combined with a battery `power_supply` shim it would register
a *true in-kernel* `power_supply` device. That path requires a compatible kernel
and a custom device-tree overlay (adding an `ina219@41` node on `i2c1` with the
`shunt-resistor` property), so it is documented here as the alternative rather
than the default. The userspace publisher needs neither.
