# WhiskerFrame Cyberdeck Operator Field Guide

*Document ID: DOC-OPERATOR-FIELD-GUIDE*  
*Hardware: Whiskerframe Cyberdeck v0.1*  
*Display: Cheap Yellow Display (320x240 LCD)*  
*Grid Ceiling: 53 Columns x 30 Rows (Font 1)*  
*Security Level: Sovereign Offline / Air-Gapped*  

---

## 1. System Topology & Hardware Map

The WhiskerFrame Cyberdeck is an air-gapped,
battery-powered sovereign computer engineered for
field operations and offline security analysis.

```text
+-------------------------------------------+
|          CYBERDECK HARDWARE MAP           |
+-------------------------------------------+
| Host:      Raspberry Pi Zero 2W (64-bit)  |
| Display:   CYD ESP32-2432S028R 320x240    |
| Port:      /dev/ttyUSB0 (CH340 @ 115200)  |
| Keyboard:  M5Stack CardKB (I2C-0 @ 0x5F)  |
| Battery:   Waveshare 3S UPS (I2C-1 @ 0x41)|
| Storage:   Samsung 860 EVO 250GB SSD      |
| Mount:     /mnt/250GB-SSD (ext4, nofail)  |
| Radio:     Broadcom BCM43436 (2.4GHz only)|
| Accounts:  neko (operator), guest (demo)  |
+-------------------------------------------+
```

### Physical Constraint (53 Columns)
In standard Font 1 (6x8 px cells), the CYD
terminal screen displays 53 columns by 30 rows.
Every command, output, manual topic, and status
indicator is formatted to <= 53 columns to prevent
text wrapping and display corruption.

---

## 2. Boot Sequence & Console Gate

### Cold Boot Progression
1. **Power Switch ON:**
   Slide physical toggle switch to ON. Unswitched
   5V UPS rail energizes Raspberry Pi Zero 2W and
   CYD coprocessor simultaneously.
2. **Firmware & Kernel Init (~25s):**
   Pi loads kernel, device-tree overlays, mounts
   ext4 root on MicroSD, and starts systemd units.
3. **Bridge Daemon Autostart:**
   `terminal.service` launches the bridge daemon
   (`pi/terminal/bridge.py`), establishing serial
   at 115200 baud to the CYD `/dev/ttyUSB0`.
4. **Hardware Boot Splash:**
   Bridge blits full-screen 320x240 RGB565 splash
   image (opcode 0x05) to CYD display.
   Splash image holds on screen for exactly 3.0s.
5. **Clean Repaint Wipe:**
   Display clears to piiiiink blurple (`0x18C5`)
   background, wiping the splash completely before
   drawing the login gate.

### Login Gate Navigation
The CYD displays the interactive login gate:

```text
+-------------------------------------------+
|            WhiskerFrame Login             |
|                                           |
|   Select user:                            |
|   > neko                                  |
|     guest                                 |
|                                           |
|   Password: [                   ]         |
|                                           |
|   demo: guest / guest                     |
+-------------------------------------------+
```

- **Select Account:** Press `Up` or `Down` arrow
  on CardKB to highlight target account:
  * `neko`: Deck operator (full sudo, persistent).
  * `guest`: Untrusted sandbox (ephemeral tmpfs).
- **Enter Password:** Press `Enter` on user name,
  type password (echoed as `*`), press `Enter`.
- **Wipe / Reset Buffer:** Press `Esc` or `Left`
  arrow to wipe the password field and return to
  account selection.
- **Compact Prompts:**
  Upon PAM authentication, the terminal bridge forks
  a dedicated PTY bash login session:
  * `n~ `: Compact prompt for `neko`.
  * `g~ `: Compact prompt for `guest`.
  Preserves horizontal columns on 53-col screens.
- **Guest Autostart:**
  Logging in as `guest` automatically runs `wf demo`
  displaying deck telemetry and containment rules.

---

## 3. CardKB Keybindings & Input Engine

The M5Stack CardKB is a 50-key matrix keypad
connected to I2C bus 0 at address `0x5F`. It sends
single bytes over I2C at 100 kHz.

### Modifier Layers
- **Normal:** Lowercase letters `a`-`z`, numbers.
- **Shift (`Aa`):** Uppercase letters `A`-`Z`.
- **Sym:** Single ASCII punctuation symbols.
- **Fn:** Extended function chords and controls.

### Sticky Ctrl Modifier Latch (`Fn+Tab`)
The CardKB lacks a physical Ctrl key. Whiskerframe
implements a sequential sticky modifier latch:

```text
+-------------------------------------------+
|           STICKY CTRL STATE FLOW          |
+-------------------------------------------+
| [Idle]                                    |
|   |  Press Fn+Tab (0x8C)                  |
|   v                                       |
| [Armed]                                   |
|   * NeoPixel: BRIGHT YELLOW [255,200,0]   |
|   * Cursor Cell: YELLOW (#ffe08a, ANSI 11)|
|   * Timer: 3.0-second countdown           |
|   |                                       |
|   +--> Press Letter (a-z) -> Emits Ctrl   |
|   |    (c -> 0x03, d -> 0x04, z -> 0x1A)  |
|   |    NeoPixel OFF, Cursor returns cyan. |
|   |                                       |
|   +--> Press Fn+Tab again -> Toggle cancel|
|   +--> Non-letter pressed -> Emits key raw|
|   +--> Timeout expires (3s) -> Silent drop|
+-------------------------------------------+
```

### Essential Ctrl Chords
Press `Fn+Tab`, release, then press target key:

| Target | Byte | Action / Signal             |
|:-------|:-----|:----------------------------|
| `c`    | 0x03 | Ctrl-C (SIGINT / interrupt) |
| `d`    | 0x04 | Ctrl-D (EOF / exit shell)   |
| `z`    | 0x1A | Ctrl-Z (SIGTSTP / suspend)  |
| `l`    | 0x0C | Ctrl-L (clear screen)       |
| `u`    | 0x15 | Ctrl-U (erase entire line)  |
| `[`    | 0x1B | Ctrl-[ (Escape character)   |
| `\`    | 0x1C | Ctrl-\ (SIGQUIT core dump)  |
| `space`| 0x00 | Ctrl-Space (NUL byte)       |

### Display Geometry Cycling (`Fn+Backspace`)
Press `Fn+Backspace` (top-right key, labeled `del`,
scancode `0x8B`) to cycle terminal fonts on the fly:

| Font | Grid  | Cell Size | Primary Use Case    |
|:-----|:------|:----------|:--------------------|
| 1    | 53x30 | 6x8 px    | Default status/CLI  |
| 5    | 40x20 | 8x12 px   | Comic Mono readable |
| 2    | 26x15 | 12x16 px  | High legibility UI  |
| 3    | 17x10 | 18x24 px  | Stage presentation  |

Cycling sends a live `SIGWINCH` signal to the active
PTY, instantly reflowing bash, vim, and ncurses.

### Navigation Keys
- `Up` (`0xB5`): History previous (`\x1b[A`).
- `Down` (`0xB6`): History next (`\x1b[B`).
- `Left` (`0xB4`): Cursor left (`\x1b[D`).
- `Right` (`0xB7`): Cursor right (`\x1b[C`).
- `Del` (`0x08`): Backspace (erase char left).
- `Shift+Del` (`0x7F`): ASCII DEL.
- `Tab` (`0x09`): Shell path/command completion.
- `Esc` (`0x1B`): Escape / reset buffer.
- `Enter` (`0x0D`): Execute command (`\r`).

---

## 4. Multi-PTY Workspace Chords

Whiskerframe includes a lightweight, i3-style
multi-PTY workspace manager implemented in
`pi/terminal/workspaces.py`. It provides up to 4
concurrent workspaces (hard cap 10) while
protecting the 416MB RAM ceiling.

Each workspace maintains:
- Dedicated pseudo-terminal (PTY pair).
- Independent bash shell process.
- Separate working directory (retained on switch).
- Independent character grid and VT100 emulator.

### Workspace Switching Chords
- `Fn+1` (`0x81`): Switch to Workspace 1.
- `Fn+2` (`0x82`): Switch to Workspace 2.
- `Fn+3` (`0x83`): Switch to Workspace 3.
- `Fn+4` (`0x84`): Switch to Workspace 4.
- `Fn+n` (`0xA6`): Switch to Next workspace.
- `Fn+p` (`0x96`): Switch to Previous workspace.

### Status Bar Indicator
The terminal status line (row 0) shows the active
workspace badge without full-screen flicker:
`[1]`, `[2]`, `[3]`, or `[4]`.

### CLI Workspace Management
You can also inspect or switch workspaces via CLI:
```bash
# List all active workspaces
wf workspace list
# Output:
#   * [1] bash (PID 612, /home/neko) [ACTIVE]
#     [2] bash (PID 684, /mnt/250GB-SSD)

# Switch to workspace 2
wf workspace switch 2

# Create new workspace
wf workspace new

# Close workspace 2
wf workspace close 2
```

Socket path: `/run/whiskerframe/workspaces.sock`.

---

## 5. Wi-Fi Field Onboarding

### Hardware Radio Reality
- **Chipset:** Broadcom BCM43436 on Pi Zero 2W.
- **Driver:** `brcmfmac` (Linux upstream).
- **Supported Band:** **2.4 GHz ONLY** (Ch 1-13).
- **5 GHz Support:** **NONE**. Lacks 5 GHz mixer.
  5 GHz networks are 100% invisible to hardware.

### Unified Wi-Fi CLI (`wf wifi`)
The `wf wifi` tool manages NetworkManager within
the strict 53-column boundary:

```bash
# Show active connection, signal, and IP
wf wifi status

# Scan top 10 nearby 2.4 GHz networks
wf wifi scan

# Join network by scan index or SSID
wf wifi join 1 -p "SecretPass123"
wf wifi join "MyHotspot" -p "Passphrase"

# Join open network without password
wf wifi join "PublicWiFi"

# Forget/delete a saved network profile
wf wifi forget "OldNetwork"
```

### Mobile Phone Hotspot Tethering
When deploying in the field, tether via smartphone:
1. Open phone **Hotspot & Tethering** settings.
2. Select **2.4 GHz Band** (or enable
   "Maximize Compatibility" on iOS/Android).
   If set to 5 GHz, the deck will see zero beacons.
3. Set channel to **Channel 1** (2412 MHz).
4. Run `wf wifi scan` on deck, then join.

### Venue Edge Cases & Mitigations

#### Edge Case A: 802.1X Enterprise (eduroam/campus)
- **Problem:** Enterprise networks require phase 2
  EAP credentials that cannot be typed via CLI.
- **Fix:** Connect phone/laptop to 802.1X, share
  via 2.4 GHz mobile hotspot to the cyberdeck.

#### Edge Case B: Captive Portals
- **Problem:** Browser redirect prevents routing.
- **Fix 1:** Clone authenticated device MAC:
  ```bash
  sudo nmcli con mod <SSID> \
    802-11-wireless.cloned-mac-address <MAC>
  sudo nmcli con up <SSID>
  ```
- **Fix 2:** Bypass captive portal using phone
  hotspot mobile data.

#### Edge Case C: Venue AP Client Isolation
- **Problem:** AP blocks station-to-station SSH.
- **Fix 1:** Use NetBird WireGuard mesh:
  `ssh neko@100.86.1.20`.
- **Fix 2:** Use direct micro-USB OTG cable.
- **Fix 3:** Operate directly on CardKB + CYD.

### Autonomous Self-Healing Daemon
The `cyberdeck-net-heal.sh` timer checks connectivity
every 30 seconds:
- **Stage 1 (30s):**
  `rfkill unblock` + `nmcli con up`.
- **Stage 2 (>5m):**
  `systemctl restart NetworkManager`.
- **Stage 3 (>15m):**
  Reload `brcmfmac` kernel module.
- *Strict Invariant:* The watchdog NEVER reboots
  the Pi automatically for network loss.

---

## 6. Artwork & Image Blitting (`demo art`)

The CYD firmware supports high-speed binary image
blitting using opcode `0x05` (`DRAW_IMAGE`).

### Blitting Architecture
- **Format:** Raw RGB565 little-endian pixels.
- **Panel Dimensions:** 320 width x 240 height.
- **Frame Buffer:** 153,600 bytes per full frame.
- **Chunked Wire Streaming:** Images stream in
  2-row slices (1,280 bytes per packet) to avoid
  overflowing UART hardware FIFOs.
- **Terminal Restoration:** On exit, the bridge
  executes a full grid wash, repainting the shell
  prompt without leftover pixel artifacts.

### Commands
```bash
# List all registered artwork and aliases
wf demo art --list

# Display the Christmas Night Market art
wf demo art market

# Display the transparent Lyra doodle
wf demo art doodle

# Hold artwork on screen for 5 seconds
wf demo art doodle --hold 5.0

# Dry-run test chunk generation without UART
wf demo art market --dry-run
```

### Artwork Catalog Aliases
- `market`:
  `Lyra and Dreanne Christmas Night Market.png`
- `doodle`: `lyra-doodle-transparent.png`
- `cess/original`: `lyra-doodle-original.png`
- `splash/reboot`: `goodbye-reboot-preview.png`
- `splash/shutdown`: `goodbye-shutdown-preview.png`

### Path Traversal Defense
`resolve_safe_image_path()` strictly confines all
image loads within the repository tree. Paths with
`../` or symlink escapes raise `PermissionError`.

---

## 7. Multi-Tenant Guest Sandbox

For live demonstrations, untrusted users can handle
the cyberdeck without risk to operator data.

### Sandbox Security Boundaries
1. **Ephemeral tmpfs Home:** `/home/guest` is an 8MB
   in-memory filesystem (`nodev,nosuid,mode=0700`).
   All files are purged on logout by PAM hook.
2. **Kernel Network Egress Drop:**
   `nftables` netfilter matches `meta skuid "guest"`
   and drops 100% of guest egress packets.
3. **5-Second Process Reaper:** Daemon polls every
   second; any guest process exceeding 5s CPU time
   receives `SIGKILL`.
4. **0700 Privacy Isolation:** `/home/neko`, `/root`,
   and `/etc/NetworkManager` are strictly `0700`.
   Guest cannot read shell history, SSH keys, or
   saved Wi-Fi passwords.
5. **Cgroup Quotas:** Guest slice enforces 64MB RAM
   limit, 50% CPU quota, and 30 max tasks.

---

## 8. Shutdown, Reboot & Screen Sleep

Whiskerframe provides a graceful shutdown hook
(`pi/bin/goodbye_hook`) registered in systemd:

### Systemd Hook Ordering
Units `cyberdeck-goodbye-reboot.service` and
`cyberdeck-goodbye-shutdown.service` execute
`Before=shutdown.target umount.target final.target`,
guaranteeing Python runs before storage unmounts.

### Visual Farewell Sequences
- **Reboot (`sudo reboot`):**
  1. Panel clears to blurple (`#191a28`).
  2. Centered 128x128 doodle rendered at (96, 36).
  3. Text `"brb :3"` drawn at (160, 184).
  4. Holds for 3.5s before kernel reboot.
- **Shutdown (`sudo poweroff`):**
  1. Panel clears to blurple (`#191a28`).
  2. Centered 128x128 doodle rendered at (96, 36).
  3. Text `"bai baiii!"` drawn at (160, 184).
  4. Holds for 3.5s.
  5. Screen wipes black.
  6. Bridge sends opcode `0x06` (`SLEEP`).
  7. ESP32 pulls backlight GPIO 21 LOW and sleeps.
  8. Backlight draws 0 mA. Safe to flip power switch.

---

## 9. Emergency Recovery & Diagnostics

### ACT LED Diagnostic Decision Tree
Inspect the green Pi ACT LED through chassis vents:

```text
+-------------------------------------------+
|          ACT LED DIAGNOSTIC TREE          |
+-------------------------------------------+
| Check Green ACT LED through chassis vent: |
|                                           |
| 1. ACT LED OFF & Backlight OFF:           |
|    -> CLEAN HALT. Safe to switch OFF.     |
|                                           |
| 2. ACT LED SOLID ON & Screen Frozen:      |
|    -> KERNEL DEADLOCK / HANG.             |
|       Action: Cycle power switch.         |
|                                           |
| 3. ACT LED Blinking Specific Pattern:     |
|    * 4 flashes: start.elf not found       |
|    * 7 flashes: kernel.img not found      |
|    * 8 flashes: SDRAM failure             |
|    -> SD CARD FAULT. Swap spare card.     |
|                                           |
| 4. ACT LED OFF & Backlight ON:            |
|    -> SERIAL DESYNC / BRIDGE CRASH.       |
|       Action: SSH or CardKB recovery.     |
|                                           |
| 5. Zero LED activity on switch flip:      |
|    -> BATTERY HARD CUTOFF (<10.2V).       |
|       Action: Connect 12.6V DC charger.   |
+-------------------------------------------+
```

### Battery Voltage & Power Thresholds
Monitored via INA219 sensor on I2C-1 @ `0x41`:

| State   | Voltage | Level | Action / Status      |
|:--------|:--------|:------|:---------------------|
| Float   | 12.4-6V | 100%  | Full charge, 0mA net |
| Nominal | 11.5-3V | 30-90%| 15-19h runtime       |
| Warning | 11.1V   | ~15%  | Attach charger now   |
| Auto-Off| 10.5V   | ~5%   | Graceful poweroff    |
| Cutoff  | 10.2V   | 0%    | BMS hardware cutoff  |

*Live Power Injection:*
The internal UPS rail is **unswitched 5V**. You can
plug in an auxiliary USB-C power bank or 12.6V DC
charger live without rebooting the Pi.

### Thermal Operating Boundaries
- **< 62°C:** Normal fanless idle temperature.
- **70°C:** Throttling threshold. ARM cores clock
  down from 1000 MHz to 600 MHz.
- **75°C:** Hard safety limit. Pause workloads.
- **80°C:** Hardware automatic thermal trip.

### Serial Hang Recovery (CardKB)
If terminal output stalls:
1. Press `Fn+Tab` then `c` (interrupt stuck process).
2. Press `Fn+Backspace` (force grid reflow).
3. Via SSH or USB-OTG console:
   ```bash
   sudo systemctl restart terminal.service
   ```

### Zero-Network Direct Console Rescue
Connect a micro-USB data cable from a laptop to the
Pi Zero 2W **USB OTG** port (center micro-USB):
```bash
# On developer laptop:
screen /dev/ttyACM0 115200
```
Provides direct root/neko shell over USB CDC-ACM.

### Golden Image Disaster Restore
A complete golden image is stored on the SSD at:
`/mnt/250GB-SSD/backup/2026-10-14/`

To restore a corrupted or replacement MicroSD:
```bash
# Verify checksums first
cd /mnt/250GB-SSD/backup/2026-10-14/
sha256sum -c SHA256SUMS

# Stream decompress directly to MicroSD
zstd -d -c sdcard-mmcblk0.img.zst | \
  sudo dd of=/dev/mmcblk0 bs=4M status=progress \
  conv=fsync
```

---

## 10. Sealed Deck Protocols & Safety Rails

The cyberdeck is enclosed in an acrylic/MDF case.
Field operations follow strict safety invariants:

### The Sealed Deck Invariants
1. **Never Brick the Sealed Deck:**
   No physical disassembly in the field. All rescue
   paths must exist over serial, OTG, or Wi-Fi.
2. **Rescue Timers Before Risky Operations:**
   Before modifying network rules, firewall, or
   boot config, arm a detached rollback timer:
   ```bash
   systemd-run --unit=rescue-timer --on-active=90 \
     /usr/local/bin/cyberdeck-net-heal.sh
   ```
   If connection is lost, timer restores state.
3. **SD Card Wear Elimination:**
   - SD swap removed (`/var/swap` deleted).
   - Fast zram swap active (priority 100).
   - SSD swapfile at `/mnt/250GB-SSD/swapfile`
     (priority 10).
   - System logs buffered via `log2ram` in tmpfs.
   - Persistent journal stored on SSD:
     `/mnt/250GB-SSD/log/journal`.
4. **Firmware Flashing Gate:**
   - CYD firmware is flashed ON THE PI via
     the venv esptool.
   - **Stop terminal service first:**
     `sudo systemctl stop terminal.service`.
   - Never flash without a verified backup binary.
   - Flash command:
     ```bash
     /opt/cyd-display-link/pi/.venv/bin/python \
       -m esptool --chip esp32 \
       --port /dev/ttyUSB0 \
       --baud 230400 write-flash -z 0x10000 \
       firmware.bin
     ```
   - Restart service:
     `sudo systemctl start terminal`.
5. **Safe Autocommit & Push Policy:**
   - Always stage explicit paths (no `git add -a`).
   - Push ONLY via agent-push wrapper:
     `~/.config/agent-policy/bin/agent-push`.
   - Gitleaks check must report 0 secrets.
   - Public readiness:
     NEVER push passwords or tokens.

---

## 11. Operator Quick Reference (53 Columns)

```text
=====================================================
     WHISKERFRAME CYBERDECK FIELD CHEATSHEET
=====================================================
KEYBOARD CONTROLS (CardKB @ 0x5F):
  Fn+Tab        Sticky Ctrl latch (3s, Yellow LED)
  Fn+Tab c      Ctrl-C (Interrupt / SIGINT)
  Fn+Tab d      Ctrl-D (Exit shell / EOF)
  Fn+Tab z      Ctrl-Z (Suspend / SIGTSTP)
  Fn+Tab l      Ctrl-L (Clear terminal screen)
  Fn+Backspace  Cycle Font (53x30/40x20/26x15/17x10)

WORKSPACE CHORDS:
  Fn+1 .. Fn+4  Direct switch to Workspace 1..4
  Fn+n          Switch to Next workspace
  Fn+p          Switch to Previous workspace

UNIFIED CLI SHORTCUTS:
  wf help       Command reference overview
  wf man <top>  Offline manual (kb,wifi,demo,term,ws)
  wf wifi scan  Scan 2.4GHz Wi-Fi networks
  wf wifi join  Connect to Wi-Fi network
  wf demo       Display telemetry banner
  wf demo art   Display artwork on CYD display
  wf workspace  List and switch terminal workspaces

POWER TELEMETRY (3S Pack):
  12.4V - 12.6V Float / Full charge (0mA net)
  11.5V - 12.3V Safe operational window (15-19h)
  11.1V         Low battery warning (~15%)
  10.5V         Emergency auto-shutdown (~5%)
  10.2V         Hardware BMS cutoff (Hard trip)

EMERGENCY RESCUE:
  ACT LED Solid Reset power switch (Hang)
  ACT Blinking  4=bootloader, 7=kernel, 8=RAM
  OTG Serial    screen /dev/ttyACM0 115200 (OTG)
  Net Heal      cyberdeck-net-heal.sh (Auto 30s)
=====================================================
```
