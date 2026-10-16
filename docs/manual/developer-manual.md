# WhiskerFrame Cyberdeck: Complete Developer Manual

**Document ID:** DOC-MANUAL-DEVELOPER-v0.1.0  
**Target Hardware:** WhiskerFrame Cyberdeck (Raspberry Pi Zero 2W + ESP32-2432S028R CYD Coprocessor)  
**Primary Host Language:** Python 3.13 (`uv`-managed project)  
**Coprocessor Language:** C++ (Arduino Framework + TFT_eSPI, PlatformIO)  
**Keyboard Firmware:** ATmega328P I2C Matrix Driver  
**Security Level:** Sovereign Air-Gapped / Production Release Candidate  

---

## Table of Contents

1. [Architectural Overview & System Blueprints](#1-architectural-overview--system-blueprints)
2. [Hardware Interconnects, Bus Hierarchy & Pinouts](#2-hardware-interconnects-bus-hierarchy--pinouts)
3. [The Host-to-Coprocessor Wire Protocol](#3-the-host-to-coprocessor-wire-protocol)
4. [Terminal Emulation, Grid Diffing & Rendering Pipeline](#4-terminal-emulation-grid-diffing--rendering-pipeline)
5. [Input Subsystem & CardKB Driver Implementation](#5-input-subsystem--cardkb-driver-implementation)
6. [Storage Subsystem: BTRFS, Generators & SD-Card Protection](#6-storage-subsystem-btrfs-generators--sd-card-protection)
7. [Operating System Architecture, Memory Safety & Sandboxing](#7-operating-system-architecture-memory-safety--sandboxing)
8. [Power & Sensory Core Subsystems](#8-power--sensory-core-subsystems)
9. [Coprocessor Firmware Architecture & Flashing Gate](#9-coprocessor-firmware-architecture--flashing-gate)
10. [Automated Testing Strategy & Acceptance Suite](#10-automated-testing-strategy--acceptance-suite)
11. [CI/CD Pipeline, Release Gating & Distribution](#11-cicd-pipeline-release-gating--distribution)
12. [Contribution Workflow, Rules & Code Conventions](#12-contribution-workflow-rules--code-conventions)

---

## 1. Architectural Overview & System Blueprints

The WhiskerFrame Cyberdeck partitions functionality across two distinct physical compute nodes:
1. **Host Compute Node (Raspberry Pi Zero 2W):** Runs 64-bit Linux, executes system services, hosts pseudo-terminals (PTYs), emulates VT100 grids, evaluates system alerts, and arbitrates power and network states.
2. **Display Coprocessor Node (ESP32-2432S028R CYD):** Directly controls the ILI9341 320x240 LCD, blits fonts and RGB565 bitmaps over high-speed hardware SPI (40 MHz), manages PWM backlight dimming, and executes a host-lost supervisory watchdog.

```text
+---------------------------------------------------------------------------------+
|                               SYSTEM ARCHITECTURE                               |
+---------------------------------------------------------------------------------+
|                                                                                 |
|  +------------------------+      USB-Serial (CH340)      +-------------------+  |
|  |  Raspberry Pi Zero 2W  | <==========================> |   ESP32-2432S028R |  |
|  |  (BCM2837B0 Cortex-A53)|     /dev/ttyUSB0 (115200)    |   ("CYD" Coproc)  |  |
|  |                        |                              |                   |  |
|  |  - Python Bridge       |   Wire Protocol:             | - FrameDecoder    |  |
|  |  - VT100 Grid Diffing  |   0xA5 [LEN] [OP] [DATA] CRC | - Glyph Renderer  |  |
|  |  - Multi-PTY Manager   |                              | - SPI ILI9341 LCD |  |
|  |  - Battery Monitor     |                              | - Backlight PWM   |  |
|  |  - Alert Engine        |                              | - 60s Watchdog    |  |
|  +------------------------+                              +-------------------+  |
|         ^          ^                                                            |
|         | I2C-0    | I2C-1 (3.3V)                                               |
|         v          v                                                            |
|  +------------+  +----------------------------------+                           |
|  |   CardKB   |  | - Waveshare 3S UPS (INA219 0x41) |                           |
|  |  (ATmega)  |  | - DS3231 RTC (0x68)              |                           |
|  |  Addr 0x5F |  | - STEMMA QT Expansion Header     |                           |
|  +------------+  +----------------------------------+                           |
|                                                                                 |
+---------------------------------------------------------------------------------+
```

### Separation of Concerns
- **Zero Graphic Logic on Serial Link:** The host never renders full-screen graphical bitmaps for terminal text. It diffs character cells and emits compact ASCII/attribute runs.
- **Pure Host Library (`whiskerframe`):** Core protocol framing and command generation do not depend on Pillow or display hardware; serialization is pure Python, bit-reproducible, and verified by property tests.

---

## 2. Hardware Interconnects, Bus Hierarchy & Pinouts

### The Three-Tier Bus Hierarchy
1. **Small Bus (I2C / UART):**
   - **I2C-0 (`/dev/i2c-0`):** GPIO 0 (SDA) / GPIO 1 (SCL), Pins 27/28. Dedicated to the M5Stack CardKB (`0x5F`). Pulled up to 3.3V. Filtered by a 30ms software debounce window.
   - **I2C-1 (`/dev/i2c-1`):** GPIO 2 (SDA) / GPIO 3 (SCL), Pins 3/5. Dedicated to the Waveshare 3S UPS INA219 sensor (`0x41`), DS3231 RTC (`0x68`), and external STEMMA QT / Qwiic sensor expansion. Fused at 100 mA with TVS transient suppression.
   - **UART (Serial):** Connected via internal micro-USB host cable to the CYD WCH CH340 USB-UART bridge at `/dev/ttyUSB0` (115200 baud).
2. **Medium Bus (USB 2.0 Host):**
   - Pi Zero 2W USB-OTG port wired to an internal 4-port USB 2.0 hub controller (Terminus FE1.1s).
   - Port 1: CYD CH340 serial bridge.
   - Port 2: SATA-to-USB bridge (JMS578) driving the Samsung 860 EVO 250GB SSD.
   - Ports 3 & 4: Exposed external USB-A ports for LTE modem, RTL-SDR, or flash storage.
3. **Big Bus:** High-speed PCIe interconnect formally deferred to future compute module upgrades.

---

## 3. The Host-to-Coprocessor Wire Protocol

The communication link between the Python host library (`whiskerframe/protocol.py`) and the ESP32 firmware (`firmware/cyd_display_link/frame.h`) is governed by an endian-safe, length-prefixed binary frame protocol:

```text
+-------+--------+--------+---------------------+--------+
|  SOF  |  LEN   | OPCODE |  PAYLOAD (LEN - 1)  |  CRC8  |
| 0xA5  | uint16 | uint8  |   Opcode-Specific   | uint8  |
+-------+--------+--------+---------------------+--------+
```

### Wire Fields
1. **`SOF` (Start of Frame):** Constant byte `0xA5` (165). Used by the firmware state machine to hunt and resynchronize stream framing after transmission glitches.
2. **`LEN` (Length):** 16-bit unsigned integer in **Little-Endian** byte order. Represents the exact byte count of `OPCODE + PAYLOAD`. Maximum frame length is 4096 bytes.
3. **`OPCODE`:** 8-bit command selector.
4. **`PAYLOAD`:** Command-specific binary parameters and data payload of length `LEN - 1` bytes.
5. **`CRC8`:** 8-bit CRC-8/SMBUS checksum calculated over all bytes from `OPCODE` through the end of `PAYLOAD`.

### The CRC-8/SMBUS Algorithm
- **Polynomial:** $0\text{x}07$ ($x^8 + x^2 + x + 1$)
- **Initial Value:** $0\text{x}00$
- **Input Reflection:** False
- **Output Reflection:** False
- **Check Value:** `crc8(b"123456789") == 0xF4` (244)

```python
def crc8(data: bytes) -> int:
    crc = 0x00
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x80:
                crc = ((crc << 1) ^ 0x07) & 0xFF
            else:
                crc = (crc << 1) & 0xFF
    return crc
```

### Opcode Registry

| Opcode | Hex | Name | Payload Structure | Description |
|---|---|---|---|---|
| `0x01` | `0x01` | `DRAW_TEXT` | `<HHBHHBBHH` + text | Render arbitrary text at (x, y) with anchor alignment |
| `0x02` | `0x02` | `DRAW_RECT` | `<HHHHHB` | Render solid or outlined rectangle (x, y, w, h, color, flags) |
| `0x03` | `0x03` | `DRAW_CELLS`| `<HHHHBH` + glyphs | Render a horizontal run of fixed-width character cells |
| `0x04` | `0x04` | `SCROLL` | `<bHHH` | Hardware scroll row band up/down by N rows |
| `0x05` | `0x05` | `DRAW_IMAGE`| `<HHHH` + RGB565 | Blit raw 16-bit RGB565 bitmap chunk (x, y, w, h) |
| `0x06` | `0x06` | `SLEEP` | `None` (0 payload) | Put ILI9341 into sleep mode and drop ESP32 CPU to 80 MHz |

---

## 4. Terminal Emulation, Grid Diffing & Rendering Pipeline

The terminal subsystem (`pi/terminal/`) connects Linux PTY output to the CYD display link through a four-stage pipeline:

```text
[PTY Master] ---> [VTEmulator] ---> [Grid (cols x rows)] ---> [Grid.diff()] ---> [SerialTransport]
```

### 1. PTY Management & VTEmulator (`vt.py`)
- Master/slave PTY pairs are allocated via `pty.openpty()`.
- The `VTEmulator` processes incoming ANSI/VT100 escape sequences:
  - Cursor movement (`\x1b[H`, `\x1b[<r>;<c>H`)
  - SGR color attributes (16-color ANSI mapping to RGB565 via active theme)
  - Erase in display (`\x1b[2J` / clean clear) and erase in line (`\x1b[K`)
  - Line wraps and scrolling boundaries

### 2. Double-Buffered Grid Diffing (`grid.py`)
The terminal bridge maintains two character grids: `current_grid` and `previous_grid`. Each cell stores:
- `char`: 1-byte ASCII/CP437 character code
- `fg`: 16-bit RGB565 foreground color
- `bg`: 16-bit RGB565 background color
- `flags`: Cell attribute bitmask (inverted, bold, underlined)

During each render tick, `Grid.diff(previous_grid)` compares cell buffers and yields minimal `CellRun` slices:
- Contiguous modified cells with identical `fg`, `bg`, and `font_size` are coalesced into a single `DRAW_CELLS` wire packet.
- Unchanged cells transmit zero bytes over serial. Under idle conditions, the serial line generates 0 bytes/second.

---

## 5. Input Subsystem & CardKB Driver Implementation

### I2C Bus Driver (`pi/cardkb/reader.py`)
The CardKB matrix controller periodically publishes pressed key scancodes over I2C:
- **I2C Read Protocol:** Reading a single byte from address `0x5F`. A return byte of `0x00` indicates no key is pressed.
- **Transient Recovery:** If the I2C bus stalls due to power rail ripple, the reader catches `OSError`, sleeps for 100ms, re-opens `/dev/i2c-0`, and resumes without dropping the daemon.
- **30ms Debounce Filter:** Identical consecutive non-zero bytes arriving within 30 milliseconds are deduplicated to eliminate key-chatter artifacts.

### Sticky Ctrl Latch State Machine
Implemented in `pi/terminal/bridge.py`:
- `CTRL_LATCH_CHORD = 0x8C` (`Fn + Tab`)
- Armed state records `_ctrl_latched = True`, `_ctrl_latched_at = time.monotonic()`.
- The bridge immediately transmits a command updating the cursor cell to yellow (`theme.ansi[11]`) and emits I2C packet `[0x13, 255, 200, 0]` to the CardKB SK6812 NeoPixel.
- When the next valid key arrives, it evaluates `key & 0x1F`, disarms the latch, restores the cursor color, and sends NeoPixel turn-off `[0x13, 0, 0, 0]`.

---

## 6. Storage Subsystem: BTRFS, Generators & SD-Card Protection

### Systemd Mount Generator (`pi/storage/install_mount.py`)
Generates `/etc/systemd/system/mnt-250GB\x2dSSD.mount` from declarative rules in `.whiskerframe.yaml`:
```ini
[Unit]
Description=WhiskerFrame Persistent 250GB SSD Mount
DefaultDependencies=no
After=local-fs-pre.target
Before=local-fs.target

[Mount]
What=/dev/disk/by-uuid/98bb87d2-7128-470e-91d5-9e117df2ab1a
Where=/mnt/250GB-SSD
Type=btrfs
Options=subvol=@data,noatime,compress=zstd:3,nofail,x-systemd.device-timeout=5s

[Install]
WantedBy=local-fs.target
```

### Swapfile Topology & BTRFS Safety
Swap on BTRFS requires specific filesystem attributes to prevent corrupted writes:
1. Created within dedicated `@swap` subvolume.
2. Formatted with Copy-on-Write explicitly disabled:
   ```bash
   chattr +C /mnt/250GB-SSD/@swap/swapfile
   dd if=/dev/zero of=/mnt/250GB-SSD/@swap/swapfile bs=1M count=2048
   chmod 600 /mnt/250GB-SSD/@swap/swapfile
   mkswap /mnt/250GB-SSD/@swap/swapfile
   ```
3. Configured in `/etc/fstab` with priority `100`.

---

## 7. Operating System Architecture, Memory Safety & Sandboxing

### Memory Envelope (416 MB RAM)
To prevent out-of-memory thrashing on the single-channel 512 MB LPDDR2 RAM:
1. **`earlyoom` Configuration:** Set to trigger `SIGTERM` when available RAM drops below 10%, and `SIGKILL` at 5%.
2. **Cgroup Slice Limits:** System daemons run under `whiskerframe.slice` with strict `MemoryMax=` caps:
   - `terminal.service`: `MemoryMax=48M`
   - `battery-monitor.service`: `MemoryMax=24M`
   - `guest` user slice: `MemoryMax=64M`, `TasksMax=30`, `CPUQuota=50%`

### Hardened Guest Sandbox Architecture
Managed via `ansible/roles/guest_demo/`:
- **Kernel Egress Blocking:**
  ```nftables
  table inet filter {
      chain output {
          type filter hook output priority 0; policy accept;
          meta skuid "guest" counter drop
      }
  }
  ```
- **Process Reaper Daemon (`cyberdeck-guest-reaper.service`):**
  Monitors `/proc` every second. Scans all processes owned by UID `guest`. If process elapsed time exceeds 5.0 seconds and the process is not the primary login shell (`bash -l`), it immediately issues `SIGKILL`.

---

## 8. Power & Sensory Core Subsystems

### Power Profiles Subsystem (`pi/bin/power-profile`)
Governed by `REQ-PWR-01` and `DEC-W39`:
- **`ACTIVE`:** CPU governor `ondemand` (1.0 GHz max), display active, radios enabled, SSD active (~3.2W).
- **`POWERSAVE`:** CPU governor `powersave` (600 MHz pinned), display dimmed, SSD spun down via `hdparm -y /dev/sda` (~1.8W).
- **`AIRPLANE`:** Radios blocked via `rfkill block all`, display put to sleep via opcode `0x06`, CPU 600 MHz (~0.55W).

### Centralized Alert Engine (`whiskerframe/alerts.py`)
Continuously samples system health:
- **Battery Thresholds:** $\le 5\%$ CRITICAL (triggers emergency shutdown), $\le 15\%$ WARNING.
- **Thermal Thresholds:** $\ge 80^\circ\text{C}$ CRITICAL, $\ge 75^\circ\text{C}$ WARNING.
- **Memory Thresholds:** $< 50\text{ MB}$ CRITICAL, $< 100\text{ MB}$ WARNING.

Alert events pass through sensory arbitration:
- If active sensory profile is `CLASSROOM`, audible alerts are forced to `False`.
- If `OVERLOAD` clamp is active, all audio and haptics are suppressed, emitting visual alerts only.

---

## 9. Coprocessor Firmware Architecture & Flashing Gate

### Firmware Source Tree (`firmware/cyd_display_link/`)
- `main.cpp`: Arduino setup, main serial loop, watchdog supervisor, opcode dispatch.
- `frame.h`: Header-only byte-at-a-time `FrameDecoder` state machine and CRC-8 validator.
- `render.h`: Rendering routines wrapping `TFT_eSPI` for fonts, primitives, image chunks, and display sleep.
- `font_6x8.h`, `font_8x12.h`, `font_12x16.h`, `font_18x24.h`: Anti-aliased glyph bitmaps.

### Flashing Safety Gate (`scripts/flash_cyd_display_link.py`)
The CYD is flashed directly from the Raspberry Pi Zero 2W over USB-Serial:
```bash
# Verify factory backup is intact before flashing
python3 scripts/flash_gate.py --verify

# Flash firmware safely via esptool
python3 scripts/flash_cyd_display_link.py --dry-run
python3 scripts/flash_cyd_display_link.py
```
*Safety Protocol:* `flash_cyd_display_link.py` automatically terminates `terminal.service` to release `/dev/ttyUSB0`, verifies binary checksums, flashes at 460800 baud, executes a hardware reset, and restarts `terminal.service`.

---

## 10. Automated Testing Strategy & Acceptance Suite

The codebase enforces a comprehensive multi-tier testing strategy:

```bash
# 1. Unit & Property Tests (Pytest + Hypothesis)
pytest test/

# 2. Typography Geometry & Font Specimen Verification
python3 scripts/verify_comic_mono_fonts.py

# 3. Transport Throughput Benchmarks across 4 Baud Rates
python3 scripts/benchmark_transport.py

# 4. Security Audit (16 automated verification checks)
python3 scripts/verify_security_audit.py

# 5. Master Acceptance Test Plan (ATP-01 through ATP-13)
python3 scripts/run_all_acceptance_tests.py
```

### Master Acceptance Suite (ATP-01 .. ATP-13)
The automated runner (`scripts/run_all_acceptance_tests.py`) validates all 13 core subsystems against physical and emulated boundary conditions, producing `docs/dev/acceptance-test-report.md`:
- `ATP-01-TERM-LOGIN`: PAM login gate, circular navigation, password masking.
- `ATP-02-INP-CTRL-LATCH`: Sticky Ctrl latch timing, cancellation, NeoPixel opcode `0x13`.
- `ATP-03-TYPO-GEOMETRY`: Multi-geometry font cycling and 8x12 typography.
- `ATP-04-SEC-GUEST-CONTAINMENT`: Guest sandbox tmpfs wipe, process reaper, and nftables.
- `ATP-05-LIFE-GOODBYE`: Shutdown/reboot goodbye hooks and sleep opcode `0x06`.
- `ATP-06-NET-WIFI-HELPER`: 53-column Wi-Fi CLI and captive portal detection.
- `ATP-07-STOR-BTRFS-SWAP`: BTRFS subvolumes, systemd mount generator, swap priority.
- `ATP-08-NET-SELF-HEAL`: Cold boot Wi-Fi persistence and 3-tier network watchdog.
- `ATP-09-HW-BATTERY-THERMAL`: INA219 battery daemon, SoC thermals, and kernel power_supply.
- `ATP-10-DISP-DRAW-IMAGE`: Binary image blitting (`0x05 DRAW_IMAGE`) and post-render grid repaint.
- `ATP-11-TERM-WORKSPACES`: Multi-PTY workspaces, CardKB chords, and memory bounds.
- `ATP-12-CAP-OFFLINE-WIKI`: 53-column offline documentation helper.
- `ATP-13-PWR-SENSORY-PROFILES`: Three-tier power profiles, sensory audio presets, and overload clamp.

---

## 11. CI/CD Pipeline, Release Gating & Distribution

### GitHub Actions Workflows (`.github/workflows/`)
1. **`ci.yml` (Continuous Integration):**
   - Triggered on PRs and pushes to `main`.
   - Runs Ruff linter and code formatter.
   - Runs Mypy static type checker.
   - Executes Pytest unit and property test suites.
   - Executes `scripts/verify_security_audit.py`.
   - Executes typography verification and transport benchmarks.
   - Executes full master acceptance test suite (`scripts/run_all_acceptance_tests.py`).
   - Builds clean Python wheel and sdist distributions.
2. **`release.yml` (Release Gating & Publication):**
   - Triggered strictly on version tags (`v*.*.*`).
   - Re-runs all test gates in release mode.
   - Verifies firmware binary checksums (`firmware/dist/checksums.sha256`).
   - Extracts release notes from `docs/dev/changelog.md`.
   - Publishes GitHub Release with verified distribution assets.

---

## 12. Contribution Workflow, Rules & Code Conventions

### The Documentation Triad (Mandatory Invariant)
Every architectural or design decision MUST be recorded simultaneously in three views:
1. **`docs/dev/ai-decisions.md` (WHY):** Clinical technical rationale (`DEC-*`).
2. **`docs/specifications/` (WHAT IS):** The active system contract (`architecture.md`, `contracts/`, `tasks.md`).
3. **`docs/dev/changelog.md` (WHEN):** Chronological historical record under Keep a Changelog formatting.

### Git Autocommit & Push Policy
- **Explicit Paths Only:** Always use `git add <explicit-file>`. Never use `git add -a` or `git add .`.
- **Protected Files:** Never delete or overwrite protected release files (`cyd_factory_backup.bin`, `ai-decisions.md`, `changelog.md`, `uv.lock`).
- **Safe Push Protocol:** Push operations must occur exclusively via `~/.config/agent-policy/bin/agent-push`.
