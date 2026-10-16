# Manual Hardware Steps — Cyberdeck Build

Reproducible, from-scratch setup for the whole cyberdeck: the **Raspberry Pi Zero
2W** host, the **ESP32 "Cheap Yellow Display" (CYD)**, and the **UPS Module 3S**
battery board. Every physical and system step is listed in order with the exact
commands and expected output, so a fresh board can be brought up from these docs
alone (see the reproducible-build rule).

Component reference:

- Pinout and wiring: `docs/Pinouts.md`, `docs/Schematics.md`
- Pi host runtime provisioning: `pi/README.md`, `pi/bootstrap.sh`
- CYD firmware: `firmware/cyd_display_link/`
- Battery daemon: `pi/battery_monitor/` (INA219 over I2C-1)
- Debugging: `docs/dev/debug.md` (env-gated `WHISKERFRAME_DEBUG` tracepoints + copy-pasteable diagnostics for every step here)

Recommended order:

1. Section A — Raspberry Pi base OS + interfaces
2. Section B — Pi host runtime (uv provisioning)
3. Section C — CYD discovery, backup, flash (irreversible steps flagged)
4. Section D — UPS Module 3S wiring + I2C enable + battery daemon
5. Section E — M5Stack CardKB keyboard (I2C-0)
6. Section G — CYD terminal bridge (login shell on the CYD)

Steps marked **IRREVERSIBLE** overwrite hardware state — read their safety notes.

---

## Section A — Raspberry Pi base setup

**Goal:** a headless Pi reachable over SSH by key, with a known address.

1. Flash Raspberry Pi OS (Bookworm, 64-bit) to the SD card (Raspberry Pi Imager).
   In the imager's advanced options, enable SSH (public-key), set the hostname,
   and preload your public key. This keeps first boot headless and reproducible.
2. Boot the Pi, find it on the network, and confirm key-based SSH:

   ```sh
   ssh -i /home/lyra/.ssh/id_rsa root@10.0.0.212 "uname -a && python3 --version"
   ```

   Expected: kernel/arch line and a Python 3.x version. (Adjust the IP/user to
   your Pi; this project uses `root@10.0.0.212`.)

3. Record the Pi's address and the SSH key path. They are referenced throughout
   (`10.0.0.212`, `/home/lyra/.ssh/id_rsa`).

---

## Section B — Pi host runtime (uv-managed, PEP 668 safe)

**Goal:** install the `whiskerframe` runtime + `pyserial` on the Pi without touching
the externally-managed system Python.

1. From the workstation, deploy the repo to the Pi (agent rules, dev tooling,
   firmware sources, docs, and 3D models are excluded by `pi/deploy-exclude.txt`;
   only `whiskerframe/`, `pi/`, and `scripts/` transfer):

   ```sh
   rsync -av --exclude-from=pi/deploy-exclude.txt \
       -e "ssh -i /home/lyra/.ssh/id_rsa" \
       ./ root@10.0.0.212:/opt/cyd-display-link/
   ```

2. Provision the uv-managed venv on the Pi (installs uv if missing, then
   `uv sync`; idempotent — safe to re-run):

   ```sh
   ssh -i /home/lyra/.ssh/id_rsa root@10.0.0.212 \
       "cd /opt/cyd-display-link/pi && ./bootstrap.sh"
   ```

   Expected tail: `pyserial 3.5` and the `whiskerframe` export list.

3. Verify from the workstation (read-only; probes the Pi's venv interpreter,
   falling back to system `python3`):

   ```sh
   uv run python -c "import sys; sys.path.insert(0,'scripts'); import pi_env_check as p; print(p.verify_pi_environment().summary)"
   ```

   Expected: `All components present: python3, pip, pyserial.`

> uv-managed venvs ship without `pip`; the env check accepts venv `python -m pip`,
> system `python3 -m pip`, or `pip3`/`pip`. Never `pip install --break-system-packages`.

---

## Section C — CYD discovery, backup, and flash

### C.1 — Discover the CYD serial port

**Goal:** identify which `/dev/tty*` node is the CYD (a CH340 USB-serial bridge).

1. With the CYD **unplugged**, capture a baseline:

   ```sh
   echo "=== USB ===" && lsusb
   echo "=== SERIAL ===" && ls -la /dev/ttyUSB* /dev/ttyACM* /dev/serial/by-id/* 2>/dev/null || echo "none"
   ```

2. Plug the CYD in over USB-C, wait ~2 s, re-run the same commands.
3. The **newly appeared** node is the CYD. On this build it enumerates as a CH340
   (`1a86:7523`) at:

   ```text
   /dev/serial/by-id/usb-1a86_USB_Serial-if00-port0  ->  /dev/ttyUSB0
   ```

   Prefer the `/dev/serial/by-id/...` path (stable across reboots). Use it as
   `<PORT>` below.

**If nothing appears:** use a data-capable USB-C cable (not charge-only) and
confirm the CH340 driver is present.

### C.2 — Back up the CYD factory flash — **IRREVERSIBLE READ, do this first**

> The flash in C.3 overwrites factory firmware and cannot be undone. This backup
> is the only way back. Do not proceed to C.3 without a `VALID` backup.

1. Read the entire 4 MiB flash with an explicit size (a CH340 at high baud can
   corrupt mid-read; `115200` is the reliable default here):

   ```sh
   uv run python -m esptool --chip esp32 \
       --port /dev/serial/by-id/usb-1a86_USB_Serial-if00-port0 \
       --baud 115200 --before default-reset --after hard-reset \
       read-flash --flash-size keep 0x0 0x400000 cyd_factory_backup.bin
   ```

   If it errors with `Corrupt data`, retry at a lower baud (`--baud 57600`).

2. Validate (must be exactly `0x400000` = 4,194,304 bytes):

   ```sh
   uv run python -c "import sys; sys.path.insert(0,'scripts'); import flash_gate as g; r=g.validate_backup('cyd_factory_backup.bin'); print('VALID' if r.valid else 'INVALID:', r.reason or '')"
   ```

   Expected: `VALID`. Copy `cyd_factory_backup.bin` somewhere durable.

### C.3 — Build and flash the CYD firmware — **IRREVERSIBLE WRITE**

> **Blocked until C.2 produced a `VALID` backup.**

1. Confirm the safety gate permits the write (needs valid backup + explicit size +
   explicit confirmation):

   ```sh
   uv run python -c "import sys; sys.path.insert(0,'scripts'); import flash_gate as g; b=g.validate_backup('cyd_factory_backup.bin'); d=g.gate_decision(b, 0x400000, True); print('PERMITTED' if d.permitted else 'BLOCKED:', d.detail)"
   ```

   Continue only on `PERMITTED`.

2. Build and flash with PlatformIO via `uvx` (keeps PlatformIO out of the project
   deps):

   ```sh
   uvx --from platformio pio run -d firmware/cyd_display_link
   uvx --from platformio pio run -d firmware/cyd_display_link \
       -t upload --upload-port /dev/serial/by-id/usb-1a86_USB_Serial-if00-port0
   ```

   Expected: build `[SUCCESS]`, upload writes with `Hash of data verified` and a
   hard reset.

3. Smoke test — draw a green rectangle + centered white "Meow":

   ```sh
   uv run --extra serial python -c "
   import time
   from whiskerframe import XYWH, CommandBuilder, TextStyle, serialize
   from whiskerframe.transport import SerialTransport
   PORT='/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0'
   b=CommandBuilder()
   cmds=[b.draw_rect(XYWH(20,20,200,80), color=0x07E0, filled=False),
         b.draw_text(XYWH(20,20,200,80), 'Meow', anchor='mm', style=TextStyle(color=0xFFFF, font_size=3))]
   with SerialTransport(PORT,115200,timeout=2.0) as t:
       time.sleep(2.0)
       for c in cmds: t.send(serialize(c))
   print('sent')"
   ```

**Restore factory firmware** (if needed):

```sh
uv run python -m esptool --chip esp32 \
    --port /dev/serial/by-id/usb-1a86_USB_Serial-if00-port0 \
    write-flash 0x0 cyd_factory_backup.bin
```

---

## Section D — UPS Module 3S (battery monitor over I2C)

The UPS Module 3S (LAFVIN/Waveshare-compatible, 3x 18650 in series) carries a
**Texas Instruments INA219** voltage/current/power monitor on I2C at address
**`0x41`**.

### D.1 — Wiring (I2C-1)

Wire the UPS I2C to the Pi's **hardware I2C-1** bus (GPIO 2/3), per
`docs/Schematics.md`:

| Pi pin | Pi signal         | Wire   | UPS pin | UPS signal |
| :----: | :---------------- | :----- | :-----: | :--------- |
|   3    | GPIO 2 (I2C1 SDA) | Orange |    7    | SDA        |
|   5    | GPIO 3 (I2C1 SCL) | Purple |    8    | SCL        |
|   6    | GND               | Green  |    3    | GND        |
|   9    | GND               | Blue   |    4    | GND        |

> Do **not** use GPIO 27/22 — they have no hardware I2C peripheral. Power the UPS
> module on (charged 18650s installed, module switch on) or the INA219 will not
> appear on the bus.

### D.2 — Enable I2C-1 on the Pi (boot config + reboot)

1. Enable the ARM I2C bus and ensure `i2c-dev` loads (idempotent):

   ```sh
   ssh -i /home/lyra/.ssh/id_rsa root@10.0.0.212 '
     CFG=/boot/firmware/config.txt
     cp "$CFG" "$CFG.bak.$(date +%s)"
     grep -q "^dtparam=i2c_arm=on" "$CFG" || sed -i "s/^#dtparam=i2c_arm=on/dtparam=i2c_arm=on/" "$CFG"
     grep -q "^dtparam=i2c_arm=on" "$CFG" || echo "dtparam=i2c_arm=on" >> "$CFG"
     grep -q "^i2c-dev" /etc/modules || echo "i2c-dev" >> /etc/modules
     grep i2c_arm "$CFG" | grep -v "^#"'
   ```

2. Reboot and wait:

   ```sh
   ssh -i /home/lyra/.ssh/id_rsa root@10.0.0.212 "nohup reboot >/dev/null 2>&1 &"; sleep 45
   ```

3. Confirm the bus and detect the INA219 (needs `i2c-tools`: `apt install i2c-tools`):

   ```sh
   ssh -i /home/lyra/.ssh/id_rsa root@10.0.0.212 "ls /dev/i2c-* && i2cdetect -y 1"
   ```

   Expected: `/dev/i2c-1` present and address **`41`** shown in the grid. If the
   grid is empty, the UPS is unpowered or SDA/SCL are swapped/loose — fix wiring
   (D.1) and rescan.

### D.3 — Install the battery-monitor daemon

The daemon reads the INA219 read-only over I2C-1, converts pack voltage to a
battery percentage for the 3S pack (full `12.6V` = 100%, empty `9.0V` = 0%,
clamped), and publishes battery status; it runs as a systemd service. Install:

```sh
ssh -i /home/lyra/.ssh/id_rsa root@10.0.0.212 \
    "cd /opt/cyd-display-link/pi/battery_monitor && ./install.sh"
```

Expected: `systemctl status battery-monitor` shows `active (running)`, and the
status file / `power_supply` entry reports voltage, current, and percentage.

> This section is finalized once the INA219 is detected in D.2. Until then the
> daemon is documented here but not installed.

---

## Section E — M5Stack CardKB keyboard (I2C-0)

The CardKB is an I2C keypad on the Pi's **I2C-0** bus (GPIO 0/1, pins 27/28),
separate from the UPS on I2C-1. See `docs/Schematics.md` for wiring.

1. Enable I2C-0 (idempotent) and reboot:

   ```sh
   ssh -i /home/lyra/.ssh/id_rsa root@10.0.0.212 -C '
     CFG=/boot/firmware/config.txt; cp "$CFG" "$CFG.bak.$(date +%s)"
     grep -q "^dtparam=i2c_vc=on" "$CFG" || echo "dtparam=i2c_vc=on" >> "$CFG"
     grep -q "^dtoverlay=i2c0" "$CFG" || echo "dtoverlay=i2c0,pins_0_1" >> "$CFG"'
   ssh -i /home/lyra/.ssh/id_rsa root@10.0.0.212 -C "nohup reboot >/dev/null 2>&1 &"; sleep 45
   ```

2. Detect the CardKB (expect `5f` on bus 0):

   ```sh
   ssh -i /home/lyra/.ssh/id_rsa root@10.0.0.212 -C "i2cdetect -y 0"
   ```

3. Read keys (requires the deployed Pi runtime). A pressed key returns its ASCII
   byte; idle returns `0`:

   ```sh
   ssh -i /home/lyra/.ssh/id_rsa root@10.0.0.212 -C "cd /opt/cyd-display-link/pi && .venv/bin/python -c \"from cardkb.reader import CardKB
   with CardKB(bus=0, address=0x5f) as kb:
       print('press keys (Ctrl-C to stop)')
       for k in kb.keys():
           print(k, repr(chr(k)))\""
   ```

   Expected: each key you press prints its byte + character.

## Section G — CYD terminal bridge (login shell on the CYD)

**Goal:** a real `bash -l` login shell rendered on the CYD, typed on the CardKB,
gated by a boot splash + a system login (user select + masked password + PAM).
This daemon ties together the CYD serial display (Section C), the CardKB
(Section E), and PAM auth. It runs as a `Restart=always` systemd service.

**Prerequisites:**

- Section B done (Pi venv at `/opt/cyd-display-link/pi/.venv`).
- Section C done (CYD firmware flashed with the Wave B draw ops; serial reachable).
- Section E done (CardKB detected on `/dev/i2c-0` at `0x5f`).
- The Pi runtime has `simplepam` (added to `pi/pyproject.toml`; re-run
  `pi/bootstrap.sh` if the venv predates it).

> **IMPORTANT — the terminal service owns the CYD serial EXCLUSIVELY.** While
> `terminal.service` is running, nothing else can use the CYD serial port. Before
> re-flashing the CYD (Section C.3) or running any other serial diagnostic, stop
> it first:
>
> ```sh
> ssh -i /home/lyra/.ssh/id_rsa root@10.0.0.212 -C "systemctl stop terminal"
> ```
>
> Re-start it (or re-run the installer) when done.

1. **Generate the splash blob on the programmer** (NOT on the Pi — the Pi never
   runs Pillow). From the repo root on your workstation:

   ```sh
   just splash
   ```

   Expected: `splash: <image> -> <...>.rgb565 (153600 bytes)`. This writes the
   file at `terminal.splash.rgb565`; it is synced to the Pi by the normal deploy.
   Idempotent: the same input always yields the same 153600-byte blob.

2. **Deploy the repo** to the Pi as usual (so `pi/terminal/` and the `.rgb565`
   blob land under `/opt/cyd-display-link`).

3. **Install the service** (idempotent; run on the Pi, as root, from the terminal
   directory):

   ```sh
   ssh -i /home/lyra/.ssh/id_rsa root@10.0.0.212 -C \
     "cd /opt/cyd-display-link/pi/terminal && chmod +x install.sh && ./install.sh"
   ```

   Expected: the unit installs, enables, and starts; `systemctl status terminal`
   shows `active (running)`.

4. **Verify on the CYD:** the splash shows briefly, then the login screen lists
   the configured users (`root`, `lyra`). Use the CardKB arrows + Enter to pick a
   user, type the password (echoed as `*`), and Enter. On success a `bash -l`
   shell for that user renders on the CYD; typing echoes. Run `logout` (or exit
   the shell) to return to the login screen.

5. **Resize (optional):** press `Fn+Del` (CardKB byte `0x8B`) in the shell to
   cycle the font size through 1 → 2 → 3 (grids 53x30 / 26x15 / 17x10). The chord
   is ignored on the login screen. (The old `Ctrl+]`/`0x1d` chord was unreachable —
   the CardKB has no Ctrl key.)

Privilege note: `terminal.service` runs as **root** with `NoNewPrivileges=false`
so the bridge can `su - <user>` into any configured account after a correct
password. The **login gate is the security boundary** — nothing runs an
unauthenticated shell, so physical access no longer yields a free root console.
See `docs/api/unreleased/ai-decisions.md` for the full rationale.

## Quick reference

| Step | What | Reversible? | Gate |
| ---- | ---- | ----------- | ---- |
| A | Flash Pi OS, enable SSH, confirm reachability | Yes | — |
| B | Deploy repo + `bootstrap.sh` (uv venv) | Yes (idempotent) | — |
| C.1 | Discover CYD serial port (baseline diff) | Yes (read-only) | — |
| C.2 | Full CYD flash backup (`read-flash 0x0 0x400000`) | Yes (read-only) | Must produce a VALID 4 MiB backup |
| C.3 | Flash CYD firmware (`pio run -t upload`) | **NO — irreversible** | Blocked until C.2 VALID + explicit confirm |
| D.1 | Wire UPS I2C to Pi I2C-1 (pins 3/5/6/9) | Yes | — |
| D.2 | Enable I2C-1 (`dtparam=i2c_arm=on`) + reboot | Yes | — |
| D.3 | Install battery-monitor daemon | Yes (systemd) | INA219 must be detected first |
| E | Enable I2C-0 + detect CardKB (`0x5f`) | Yes | — |
| G.1 | Generate splash blob (`just splash`, programmer-side) | Yes (idempotent) | — |
| G.3 | Install terminal bridge daemon | Yes (systemd) | Sections C + E done; **stop `terminal` before any CYD serial use/flash** |

Identifying facts for this build:

- Pi: `root@10.0.0.212`, key `/home/lyra/.ssh/id_rsa`, deploy path `/opt/cyd-display-link`
- CYD: CH340 `1a86:7523`, `/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0`, 115200 baud
- UPS: INA219 on `/dev/i2c-1` at `0x41`, 3S pack (9.0-12.6V)

---

## Debugging

When a step above misbehaves, see **`docs/dev/debug.md`**. It documents the
env-gated tracepoint system (set `WHISKERFRAME_DEBUG=1` to emit `[TP] ...` lines)
and gives copy-pasteable diagnostics -- both raw and SSH-wrapped -- for the UPS
/ INA219, the I2C bus, CYD serial discovery/backup/monitor, the Pi host runtime,
and the `whiskerframe` command path, plus an `auto_shutdown` safety note.
