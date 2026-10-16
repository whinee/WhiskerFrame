## §1. System Architecture & Hardware Topology

The cyberdeck functions as an asymmetric dual-core system: a Linux host (Pi Zero 2W) handling storage, networking, PAM, and high-level agent logic, while an ESP32 coprocessor acts as a dedicated graphic/terminal rendering unit over serial.

```
                    +-------------------------------------------------+
                    |              Raspberry Pi Zero 2W               |
                    |               (Raspberry Pi OS)                 |
                    +---+--------------+--------------+---------------+
                        |              |              |               |
           USB-Serial   |        I2C-0 |        I2C-1 |       USB OTG |
           (CH340)      |        (Pin 27/28)    (Pin 3/5)             |
                        |              |              |       Unpowered Hub
                        v              v              v               v
               +----------------+ +----------+ +---------------+ +-----------+
               | ESP32-2432S028 | | M5Stack  | | UPS Module 3S | | ZTE LTE   |
               | (CYD Coproc)   | |  CardKB  | | (INA219 Sens) | | Modem &   |
               | ILI9341 Display| | Addr 0x5F| | Addr 0x41    | | RTL-SDR   |
               +----------------+ +----------+ +---------------+ +-----------+

```

### 1.1 Hardware Node Matrix

| Component | Interface / Port | Address / Node | Operational Parameters | Critical Constraints |
| --- | --- | --- | --- | --- |
| **CYD (ESP32)** | USB-Serial (CH340) | `/dev/ttyUSB0` (`usb-1a86_USB_Serial...`) | 115200 baud (runtime), 460800 baud (flash) | Hardware is sealed inside deck. Panel requires `tft.invertDisplay(true)`. Exclusive lock by `terminal.service`. |
| **M5Stack CardKB** | I2C-0 (Pins 27/28) | `/dev/i2c-0` @ `0x5F` | Polled ASCII byte stream (`0x00` = idle) | Requires `dtparam=i2c_vc=on` & `dtoverlay=i2c0,pins_0_1`. Self-healing via `robust_keys()`. |
| **UPS Module 3S** | I2C-1 (Pins 3/5) | `/dev/i2c-1` @ `0x41` | 3S Li-ion pack (9.0V–12.6V) | Managed by `battery-monitor.service`. Calibrates per poll; auto-shutdown trigger at 5%. |
| **Networking** | USB OTG Hub | `usb0` (Modem) / `/dev/swradio0` (SDR) | ZTE MF833V (LTE) + Generic SDR | Connected via unpowered hub. Max total draw 1.5A from Pi to prevent volt drop. |
| **Storage (SSD)** | USB 2.0 (SATA-to-USB) | `/dev/disk/by-uuid/98bb87d2-7128-470e-91d5-9e117df2ab1a` | **btrfs** (whole-disk, label `cyberdeck-ssd`); `@data` subvol → `/mnt/250GB-SSD` (`noatime,compress=zstd`); `@swap` subvol holds the swapfile (`nodatacow`) | Must use `nofail` + device timeout to prevent boot hangs. Reconciled ext4→btrfs 2026-10-07 (DEC-W12); old ext4 UUID `a6ca355e-…` is dead. Swap is `nodatacow`/uncompressed (CoW incompatible with swap). |

### 1.2 Communication Protocols & Bus Hierarchy

| Bus Tier | Interface / Port | Attached Devices | Link Parameters | Protocol Specification |
| --- | --- | --- | --- | --- |
| **Small Bus** | UART (CH340) | Host Pi Zero 2W -> ESP32-2432S028 CYD Coprocessor | 115200 baud (runtime), 460800 baud (flash) | Binary framing (`SOF 0xA5`, `LEN`, `OPCODE`, `CRC8`), opcodes `0x01`–`0x06`. See [contracts/wire-protocol.md](contracts/wire-protocol.md). |
| **Small Bus** | I2C-0 (`/dev/i2c-0`) | Host Pi (GPIO 0/1, Pins 27/28) -> M5Stack CardKB (`0x5F`) | 100 kHz standard mode | Polled ASCII byte stream, sequential sticky Ctrl latch (`0x8C`), SK6812 NeoPixel control (`0x13`/`0x11`). See [terminal.md](terminal.md). |
| **Small Bus** | I2C-1 (`/dev/i2c-1`) | Host Pi (GPIO 2/3, Pins 3/5) -> Waveshare UPS 3S (`0x41`), DS3231 RTC (`0x68` [v1]) | 100 kHz standard mode | INA219 voltage/current telemetry; DS3231 monotonic timekeeping. |
| **Medium Bus** | USB 2.0 Host | Pi Micro-USB OTG -> Unpowered 4-Port Hub | 480 Mbps high-speed shared | Host connections: Samsung 860 EVO SSD, ZTE MF833V LTE modem, RTL-SDR. |
| **Big Bus** | PCIe / NVMe | Deferred to v2+ (e.g. Pi CM4 / Pi 5 baseboard) | Gen 2/3 x1 | High-speed storage expansion (deferred). |

### 1.3 Memory & Resource Budgets

| Resource / Subsystem | Physical Ceiling | Allocated Budget | Safety Floor / Threshold | Management Mechanism |
| --- | --- | --- | --- | --- |
| **Pi Zero 2W System RAM** | 512 MB (LPDDR2) | ~416 MB (usable after `gpu_mem=16`) | Broken below 50 MB free (`REQ-OPS-02`) | No Docker/heavy DBs (`REQ-OPS-01`), `earlyoom` daemon, per-service `MemoryMax=` |
| **Swap Space (SSD)** | 250 GB SSD | 1024 MB swapfile on `@swap` (`nodatacow`) | Priority -2 (fallback only) | `swappiness=10`, memory-safety role |
| **Compressed RAM (zram)** | 416 MB RAM | 208 MB zram0 (`zstd`/`lzo-rle`) | Priority 100 (fast burst swap) | `zram-tools` / kernel zram |
| **Ephemeral Guest RAM** | 416 MB RAM | 8 MB tmpfs at `/home/guest` | Max 64 MB cgroup slice | `systemd user-.slice`, `MemoryMax=64M`, auto-cleaned on logout |
| **Log & Buffer Wear** | 416 MB RAM | 32 MB log2ram tmpfs buffer | Max 200 MB on persistent SSD | `log2ram` hourly commit + SSD journald diversion |
| **CYD ESP32 SRAM** | 520 KB SRAM | ~328 KB internal SRAM | Free heap > 80 KB | Font glyph subset caching (ASCII only), no Unicode bloat |

### 1.4 Workspace & Multi-PTY Architecture

The terminal bridge (`pi/terminal/bridge.py`) implements a lightweight, in-process session multiplexer that manages up to 4 concurrent virtual workspaces (`WS1` through `WS4`) without the high memory footprint or escape-chord collisions of `tmux` or `screen`:

* **Process Isolation:** Each workspace maintains an independent pseudo-terminal master file descriptor (`master_fd`), child shell PID (`su - <user>`), and `VTEmulator` virtual character grid (`53x30` default).
* **Asynchronous PTY Pump:** Background workspaces continue executing concurrently. Output is parsed non-blocking via `select.select()` into the corresponding background grid without serial bus activity.
* **Navigation Chords:** Workspace switching is mapped to CardKB chords (`Fn + 1` through `Fn + 4` or sequential `Fn + Left` / `Fn + Right`).
* **Differential Screen Swapping:** Switching workspaces binds active user input to the new workspace's PTY master and triggers a differential repaint (`grid.diff(prev_active)`) across UART, rendering only differences between the two buffers.
* **Lifecycle Boundary:** Exiting an active shell closes only that workspace's PTY; sibling workspaces remain active. When all workspaces exit, the bridge drops back to the PAM login view.

### 1.5 Status Line & Telemetry Architecture

To provide operators with continuous situational awareness without display tearing or serial bus saturation:

* **Grid Placement:** Row 0 (or bottom row 29) is allocated as an active telemetry status line displaying: `[WS:1] [WIFI:SSID] [12.4V 95%] [61.2°C] [CTRL:ARM]`.
* **Asynchronous Data Source:** Telemetry is read strictly from pre-cached files: `/run/battery_monitor/status.json` (produced by `battery-monitor.service`), `/sys/class/thermal/thermal_zone0/temp` (sysfs), and NetworkManager state. No direct I2C transactions are performed within the terminal thread.
* **Cell-Differential Rendering:** Updates are throttled to a 2.0-second interval. Grid diffing ensures only changed numbers or indicator glyphs generate `DRAW_CELLS` packets (<10 bytes per normal tick), eliminating UART queue congestion and visible screen flicker.
* **Transport Comparison (Wired UART vs Wireless):**
  * *Wired UART (115,200 baud):* Consumes ~0.08% of link capacity for telemetry, operates with deterministic sub-millisecond bus timing, generates zero RF emissions, and maintains link integrity during radio reset.
  * *ESP32 Wi-Fi / BLE (Rejected for v0/v1):* Introduces 15–60 ms network packet jitter, draws 80–120 mA continuous RF current (sacrificing 1.5h battery runtime), and risks 2.4 GHz co-channel interference with Pi Zero 2W Wi-Fi.

### 1.6 Typography & Display Geometry Engine

The display subsystem supports 4 distinct character grid geometries tailored for varying operational postures:

| Geometry | Grid Dimensions | Cell Size | Font ID | Target Use Case |
|---|---|---|---|---|
| **Font 1** | **53 columns x 30 rows** | 6x8 pixels | `1` | High-density terminal, full-screen editors, logs. |
| **Font 5** | **40 columns x 20 rows** | 8x12 pixels | `5` | Intermediate Comic Mono / monospace readable text. |
| **Font 2** | **26 columns x 15 rows** | 12x16 pixels | `2` | Large glanceable mobile transit view. |
| **Font 3** | **17 columns x 10 rows** | 18x24 pixels | `3` | Maximum size emergency cockpit telemetry view. |

* **Bitmap Compilation:** Intermediate fonts are compiled into coprocessor flash using `scripts/generate_font_8x12.py`, extracting 95 ASCII glyphs (32..126) into compact PROGMEM bitmask arrays (`kFont8x12Glyphs[95][12]`).
* **Runtime Cycling:** Pressing `Fn + Backspace (labeled 'del')` (`0x8B`) cycles sequentially through `(1, 5, 2, 3)`, updates `TerminalGeometry`, triggers `TIOCSWINSZ` on the active PTY, and issues a clean full repaint.

---

### 1.7 Power Management & Three-Tier Profiles Architecture

Whiskerframe enforces a coordinated three-tier power profile management hierarchy (`REQ-PWR-01`, `DEC-W39`) executed via `pi/bin/power-profile` and `wf power`:

| Profile | CPU Governor | Frequency | Radios (`rfkill`) | SATA SSD (`hdparm`) | Display State | Estimated Power | Target Operational Stance |
|---|---|---|---|---|---|---|---|
| **ACTIVE** | `ondemand` / `schedutil` | 1.0 GHz | Unblocked | Active | Awake | ~3.2 W load | Full computing, compilations, interactive editing |
| **POWERSAVE** | `powersave` | 600 MHz | Unblocked | Standby (`-y`) | Active | ~1.8 W idle | Extended fieldwork, offline reading, light terminal work |
| **AIRPLANE** | `powersave` | 600 MHz | Blocked all | Standby (`-y`) | Sleep (`0x06`) | ~0.55 W sleep | Mobile transit, air-gapped security, low-power stow |

* **Hardware Abstractions & Mock Fallbacks:** In live environments, `power-profile` manipulates `/sys/devices/system/cpu/cpu*/cpufreq/scaling_governor`, invokes `/usr/sbin/rfkill`, and issues `/usr/sbin/hdparm -y`. In container/virtual test environments, mock fallbacks ensure full deterministic testing without requiring real hardware.
* **Persistent State:** Power profile state is recorded to `/run/whiskerframe/power_state.json` (overridable via `WHISKERFRAME_POWER_STATE`).

---

### 1.8 Sensory Audio Presets & Cognitive Overload Mitigation Architecture

The sensory audio architecture (`REQ-ENV-04`, `REQ-INP-08`, `DEC-W39`) provides deterministic audio volume levels and cognitive sensory overload protection via `pi/bin/profile` and `wf profile`:

| Preset | Buzzer Volume | Haptics Enabled | Audible Alerts | Bell Mode | Operational Environment |
|---|---|---|---|---|---|
| **CLASSROOM** | `0%` | `False` | `False` | `visual` | Library, lecture, exam, quiet workspace |
| **OFFICE** | `25%` | `True` | `True` | `both` | Standard indoor office, lab, home |
| **COMMUTE** | `100%` | `True` | `True` | `both` | Bus, train, street transit, noisy outdoor venue |

* **Single-Action Overload Mitigation:** In high-stress or sensory overload conditions, the operator triggers overload mitigation (`wf profile overload` or `profile overload on`). This immediately clamps effective buzzer volume to 0%, silences tickers and buzzers, and sets bell mode to visual-only.
* **Non-Destructive Restoration:** Deactivating overload mode restores the exact calibrated volume and haptics associated with the currently selected base preset. State is tracked at `/run/whiskerframe/sensory_state.json`.

---

### 1.9 Hardware Supervisory Watchdog & Critical Alert Engine

To safeguard against silent system failures and hazardous hardware conditions:

* **Firmware Supervisory Watchdog (`REQ-HW-07`):** The ESP32 coprocessor firmware maintains a hardware link watchdog timer (`kHostWatchdogTimeoutMs = 60000`). If no valid framed packet is received over UART for >60 seconds after initial link establishment, the coprocessor draws an alert banner across the top display rows: `! HOST LINK LOST (>60s) - RECOVERY` in white on red. Receipt of any valid packet immediately clears the warning.
* **Tri-Axial Alert Evaluation (`REQ-INP-07`):** `whiskerframe/alerts.py` evaluates system telemetry against critical safety thresholds:
  * **Battery:** Voltage / capacity <= 5.0% triggers `CRITICAL` shutdown warning; <= 15.0% triggers `WARNING` recharge alert.
  * **Thermals:** Core temperature >= 80.0°C triggers `CRITICAL` thermal trip alert; >= 75.0°C triggers `WARNING` throttling alert.
  * **Memory:** Free usable RAM < 50.0 MB triggers `CRITICAL` earlyoom alert; < 100.0 MB triggers `WARNING` headroom alert.
* **Sensory Filtering:** All alert events are arbitrated through the sensory profile engine. If sensory overload is active or the silent `CLASSROOM` profile is selected, audible alerts are suppressed, routing notifications strictly to visual terminal indicators.


