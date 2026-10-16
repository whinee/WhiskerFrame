# WhiskerFrame Cyberdeck: Complete System Documentation Manuals

**Document Version:** 1.0.0 (Release Candidate v0.1.0)  
**System Target:** WhiskerFrame Cyberdeck (Raspberry Pi Zero 2W + ESP32-2432S028R CYD Coprocessor)  
**Security Level:** Sovereign Air-Gapped / Field Deployable  
**Status:** Canonical Reference

---

## 1. Documentation Architecture & Organization

The WhiskerFrame Cyberdeck manual suite provides comprehensive operational and engineering documentation covering all 12 formal technical specification domains. Documentation is partitioned into two companion master manuals supported by twelve deep-dive domain chapters:

```text
docs/manual/
├── README.md                      # This master index, system matrix, and navigation guide
├── operator-manual.md             # Complete field operator and system administration manual
├── developer-manual.md            # Complete developer engineering and architecture manual
└── domains/                       # Deep-dive domain reference manuals (12 domains)
    ├── 01-capabilities.md         # Capabilities & Offline Applications (REQ-CAP)
    ├── 02-hardware-ux.md          # Hardware UX, Aesthetics & Ergonomics (REQ-UX)
    ├── 03-terminal-display.md     # Terminal Display Subsystem & Wire Protocol (REQ-TERM)
    ├── 04-input-subsystem.md      # Input Subsystem, CardKB & Sticky Ctrl Latch (REQ-INP)
    ├── 05-storage-lifecycle.md    # Storage Architecture, BTRFS & Wear Mitigation (REQ-STORAGE)
    ├── 06-hardware-enclosure.md   # Hardware Nodes, Buses & Peripherals (REQ-HW)
    ├── 07-environmental-transit.md# Environmental, Thermal & Transit Boundaries (REQ-ENV)
    ├── 08-compute-os-containment.md# Compute, OS, Memory Safety & Guest Sandbox (REQ-OPS)
    ├── 09-power-battery.md        # Power Profiles, UPS & Battery Telemetry (REQ-PWR)
    ├── 10-networking-mesh.md      # Networking, Wi-Fi Persistence & Mesh VPN (REQ-NET)
    ├── 11-mechanical-thermal.md   # Mechanical Casework & Conduction Cooling (REQ-MECH)
    └── 12-modularity-expansion.md # Bus Hierarchy, Protection & Modular Sensors (REQ-MOD)
```

---

## 2. The 12 Specification Domains Master Matrix

| Domain | Formal Prefix | Scope & Responsibility | Primary Code Implementation | Key System Interfaces & Services | Primary Acceptance Plans |
|---|---|---|---|---|---|
| **01. Capabilities** | `REQ-CAP` | Offline documentation, local scripting, text-only operational modality | `pi/bin/wiki`, `pi/bin/wf` | `wiki`, `wf man`, Python 3.13 standard library | ATP-12-CAP-OFFLINE-WIKI |
| **02. Hardware UX** | `REQ-UX` | Physical envelope, tactile input, anti-distraction, boot/goodbye splashes, themes | `pi/terminal/theme.py`, `pi/bin/goodbye_hook` | `cyberdeck-goodbye-*.service`, `piiiiink-a11y.json`, `mono-high-contrast.json` | ATP-05-LIFE-GOODBYE |
| **03. Terminal & Display** | `REQ-TERM` | CYD 320x240 LCD, wire protocol framing, VT100 cell diffing, multi-geometry fonts, multi-PTY workspaces | `whiskerframe/protocol.py`, `pi/terminal/bridge.py`, `firmware/cyd_display_link/` | `terminal.service`, `/dev/ttyUSB0` (115200 baud), `workspace` CLI | ATP-01-TERM-LOGIN, ATP-03-TYPO-GEOMETRY, ATP-10-DISP-DRAW-IMAGE, ATP-11-TERM-WORKSPACES |
| **04. Input Subsystem** | `REQ-INP` | CardKB 50-key matrix, I2C debouncing, sticky Ctrl latch, NeoPixel feedback, sensory alert arbitration | `pi/cardkb/reader.py`, `whiskerframe/alerts.py` | `/dev/i2c-0` (`0x5F`), NeoPixel opcode `0x13`, `keys` CLI, `profile overload` | ATP-02-INP-CTRL-LATCH |
| **05. Storage Lifecycle** | `REQ-STORAGE` | 250GB Samsung SSD, BTRFS subvolumes, systemd mount generator, log2ram wear mitigation, backup sync | `pi/storage/install_mount.py`, `scripts/backup-sync.sh` | `/mnt/250GB-SSD` (`@data`), `/mnt/250GB-SSD/swapfile` (`@swap`), `log2ram.service` | ATP-07-STOR-BTRFS-SWAP |
| **06. Hardware Enclosure** | `REQ-HW` | Node matrix, DS3231 RTC, external USB peripherals, 3S UPS, RUN button, host-lost watchdog | `firmware/cyd_display_link/main.cpp`, `pi/battery_monitor/ina219.py` | Pi Zero 2W, CYD ESP32, CardKB, INA219 (`0x41`), DS3231 (`0x68`) | ATP-09-HW-BATTERY-THERMAL |
| **07. Environmental & Transit** | `REQ-ENV` | Passive conduction cooling, two-thumb posture, sunlight theme, audio presets, aviation 27.75Wh compliance | `pi/bin/profile`, `whiskerframe/alerts.py` | Aluminum heatsink, LDR sensor, `profile` (`CLASSROOM`, `OFFICE`, `COMMUTE`) | ATP-13-PWR-SENSORY-PROFILES |
| **08. Compute, OS & Sandbox** | `REQ-OPS` | Native systemd services, 416MB RAM bounds, earlyoom, hardened guest sandbox (PAM/nftables/tmpfs/reaper), net watchdog | `pi/terminal/login.py`, `ansible/roles/guest_demo/`, `/usr/local/bin/cyberdeck-net-heal.sh` | PAM `terminal`, `cyberdeck-guest-reaper.service`, `nftables` isolation | ATP-04-SEC-GUEST-CONTAINMENT, ATP-08-NET-SELF-HEAL |
| **09. Power & Battery** | `REQ-PWR` | Three-tier power profiles (ACTIVE/POWERSAVE/AIRPLANE), INA219 telemetry, 5% cutoff, sleep opcode 0x06 | `pi/bin/power-profile`, `pi/battery_monitor/` | `battery-monitor.service`, `/run/battery_monitor/status.json`, `wf power` | ATP-09-HW-BATTERY-THERMAL, ATP-13-PWR-SENSORY-PROFILES |
| **10. Networking & Mesh** | `REQ-NET` | 53-col Wi-Fi CLI (`wifi`), rfkill cold boot persistence (regdom PH), NetBird WireGuard mesh, dual-band USB | `pi/bin/wifi`, `/etc/modprobe.d/rfkill_default.conf`, `ansible/roles/netbird/` | NetworkManager, NetBird (`100.86.0.0/16`), `wifi` CLI | ATP-06-NET-WIFI-HELPER, ATP-08-NET-SELF-HEAL |
| **11. Mechanical & Casework** | `REQ-MECH` | A5 physical envelope (<110x180x70mm), laser-cut acrylic/MDF, shock mounting, passive thermal pad ($k \ge 3.0\text{ W}/(\text{m}\cdot\text{K})$) | `3D Models/`, casework CAD | External 12.6V DC barrel, 2x USB-A ports, mini-HDMI, silicone bumpers | ATP-13-PWR-SENSORY-PROFILES |
| **12. Modularity & Expansion** | `REQ-MOD` | 3-tier bus hierarchy (Small/Medium/Big), TVS diode & 100mA PTC protection, STEMMA QT / Qwiic sensor expansion | `docs/Pinouts.md`, `docs/Schematics.md` | I2C-1 STEMMA QT header, external USB 2.0 hub, TVS diode rails | ATP-09-HW-BATTERY-THERMAL |

---

## 3. Which Manual Should You Read?

### For Field Operators and Sysadmins
Read **`operator-manual.md`**:
- Practical daily operation of the deck in mobile, transit, and off-grid settings.
- Cold boot progression, logging into `neko` or `guest` accounts, and understanding screen layouts.
- Typing techniques on the 50-key CardKB, using the sequential sticky Ctrl latch (`Fn+Tab`).
- Multi-PTY virtual workspace switching (`Fn+1`..`Fn+4` or `wf workspace`).
- Cycling font geometries for varying lighting or legibility conditions (`Fn+Backspace`).
- Managing power states (`wf power active|powersave|airplane`) and battery health.
- Changing sensory audio profiles (`wf profile classroom|office|commute`) and triggering instant overload silence (`wf profile overload`).
- Scanning, joining, and troubleshooting Wi-Fi networks and captive portals via `wifi`.
- Conducting public hands-on demonstrations using the hardened `guest` sandbox.
- Field maintenance, battery charging safety, and emergency recovery checklists.

### For Software, Firmware, and Hardware Engineers
Read **`developer-manual.md`**:
- Comprehensive architectural blueprints across the Linux host, Python library, ESP32 firmware, and ATmega328P keyboard controller.
- The bit-for-bit wire protocol specification (`SOF`, `LEN`, `OPCODE`, `PAYLOAD`, `CRC8`).
- Opcode definitions: `0x01 DRAW_TEXT`, `0x02 DRAW_RECT`, `0x03 DRAW_CELLS`, `0x04 SCROLL`, `0x05 DRAW_IMAGE`, `0x06 SLEEP`.
- The cell-differential rendering engine (`grid.diff`) and VT100 terminal emulation state machine.
- I2C bus arbitration, 30ms debounce algorithms, and NeoPixel LED telemetry.
- BTRFS storage topology, systemd mount generator internals, and log2ram wear mitigation.
- ESP32 coprocessor firmware compilation, memory safety, and flashing protocols via the Pi Zero 2W.
- Test suites: Pytest unit tests, Hypothesis property tests, ATP-01..13 master acceptance harness, security audits, and benchmarks.
- CI/CD workflow automation, package distribution, and release gating.

### For Domain Specialists
Read the corresponding chapter in **`domains/`** for targeted, deep-dive specifications, physics arithmetic, circuit schematics, register maps, and component part numbers.

---

## 4. Key System Invariants (Must Never Be Broken)

1. **416 MB RAM Envelope Invariant:**
   The Raspberry Pi Zero 2W has approximately 416 MB of usable system RAM. Heavy container engines (Docker, Podman, LXC) and database engines (PostgreSQL, MongoDB) are strictly prohibited on the physical deck. All system services run as native systemd units bounded by cgroup `MemoryMax=` directives.
2. **Sealed-Deck Flashing Invariant:**
   The CYD ESP32 coprocessor is permanently installed inside the sealed casework and wired to the Raspberry Pi Zero 2W via USB-Serial (`/dev/ttyUSB0`). Flashing the coprocessor MUST be performed directly on the Pi via `scripts/flash_cyd_display_link.py` using `esptool` at 460800 baud after stopping `terminal.service`. The 4MB validated factory flash backup (`cyd_factory_backup.bin`) must NEVER be deleted.
3. **53-Column Display Boundary Invariant:**
   At standard Font 1 (6x8 px cells), the CYD 320x240 LCD displays 53 columns by 30 rows. All command output, status lines, help tools, and interactive utilities must format text strictly within 53 columns to prevent display wrapping and character buffer corruption.
4. **Non-Destructive Storage Invariant:**
   The persistent 250GB SSD mount generator (`pi/storage/install_mount.py`) must default to `--dry-run` and must never execute destructive partition operations (`fdisk`, `mkfs`) on existing file systems.
5. **Safe Autocommit & Push Policy:**
   All git commits must use explicit file paths (`git add <file>`). Global staging (`git add -a` or `git add .`) is strictly prohibited. Git push operations must occur only through authorized wrappers (`~/.config/agent-policy/bin/agent-push`).
