# Product Requirements

## REQ-CAPABILITIES (User-Facing)

* **REQ-CAP-01 [v1] (Offline reading)**: The deck MUST support an offline repository of articles (e.g. Wikipedia).
* **REQ-CAP-02 [v0] (Local coding)**: The deck MUST support local coding and offline access to Python/Bash manuals, acknowledging the limitation of the small 320x240 screen.
* **REQ-CAP-03 [v0] (Text-Only TUI)**: The deck MUST operate strictly as a text-only platform without an LLM running locally.

## REQ-UX (Hardware UX & Ergonomics)

* **REQ-UX-01 [v0] (Form Factor)**: The deck MUST fit within an A5 perimeter (148 x 210 mm) and MUST be thinner than 65 mm.
* **REQ-UX-02 [v0] (Tactile Input)**: The deck MUST feature physical keys (not glass) to mitigate thumb-typing constraints of standard phones.
* **REQ-UX-03 [v0] (Zero Distraction)**: The deck MUST have no push-notification system or ad-supported software interrupting the terminal experience.
* **REQ-UX-04 [v0] (UI Customization)**: The UI MUST allow full user-configurable customization from the host (`.whiskerframe.yaml`) and from the device itself for color themes, font family/style, status line fields, and layout configuration (5.01, 5.11).
* **REQ-UX-05 [v0] (User-Facing Splash)**: The device SHOULD display a customizable splash screen on boot, rendered within 1-2 seconds of terminal initialization (5.09).
* **REQ-UX-06 [v1] (Physical Alerts & Switches)**: The system MUST include dedicated physical toggle switches for radio (Wi-Fi/LTE) kill, master audio mute, and auxiliary alert (buzzer) mute to ensure operational silence in sensitive environments (3.08, 4.07, env-req).
* **REQ-UX-07 [v2+] (LED Matrix Deferred)**: The MAX7219 LED matrix is deferred to v2 to maintain physical chassis thinness (F-05.02).
* **REQ-UX-08 [v0] (Resource-Efficient Glyphs)**: The font subsystem MUST use a reduced ASCII/necessary-symbol-only glyph cache to fit within CYD memory constraints, rather than full Unicode support (F-05.03).

## REQ-STORAGE (Storage Lifecycle & Remote Access)

* **REQ-STORAGE-01 [v1] (Automated Data Lifecycle)**: The device SHOULD implement a backup mechanism (e.g. backrest) for critical project data to an external home server, synchronized only when connected to a trusted, non-LTE network (7.07, 7.10, F-07.02).
* **REQ-STORAGE-02 [v1] (Secure Self-Hosted Sharing)**: File access, including SMB/File Browser, MUST be authenticated and traffic encrypted (smb encrypt = required) with firewall restrictions (F-07.01).
* **REQ-STORAGE-03 [v0] (Zero Uncurated Deletion)**: Working project data on the persistent SSD MUST NOT be deleted automatically; local cleanups are manual, with authoritative copies retained on the home server / git remotes (7.13).

## REQ-HW (Hardware Enclosure & Peripherals)

* **REQ-HW-01 [v1] (RTC)**: The architecture MUST include an I2C DS3231 Real-Time Clock module so logs and git timestamps sync correctly while off-grid.
* **REQ-HW-02 [v1] (Weatherproofing)**: The case MUST be fully enclosed to prevent humidity from damaging the components in tropical (PH) climates.
* **REQ-HW-05 [v1] (Physical Alerts & Switches)**: The system MUST include dedicated physical toggle switches for radio (Wi-Fi/LTE) kill, master audio mute, and auxiliary alert (buzzer) mute to ensure operational silence in sensitive environments (3.08, 4.07).
* **REQ-HW-06 [v0] (Keyboard & Input MVP)**: The initial version MUST utilize the off-the-shelf CardKB v1.1 module, deferring custom custom PCB/PCB-case design to v2+ (4.02, 4.04).
* **REQ-HW-07 [v1] (Rotary Encoder Controls)**: The system SHOULD feature a hardware rotary encoder wired to ESP32 coprocessor mapping rotary position to terminal volume/brightness/font-size/scrolling (4.03, 4.07).

## REQ-ENV (Environmental & Operating Contexts)

* **REQ-ENV-01 [v1] (Fanless Rain Resistance)**: The chassis MUST operate with passive (fanless) cooling and incorporate weather-resistant sealing to protect internal electronics during transit exposure (3.05).
* **REQ-ENV-02 [v0] (Two-Thumb Handheld Posture)**: The physical chassis balance and keyboard placement MUST support two-thumb typing while handheld without requiring a desk or lap rest (3.02).
* **REQ-ENV-03 [v1] (Ambient Light Compensation)**: The display subsystem SHOULD utilize the CYD on-board LDR (light sensor) to dynamically adjust backlight PWM and select high-contrast palettes in bright environments (3.06).
* **REQ-ENV-04 [v1] (Multi-Environment Audio Profiles)**: The audio and buzzer alert subsystems MUST support configurable operational profiles (e.g. silent/classroom, quiet/library, outdoor) with an immediate software/hardware mute switch (3.08).
* **REQ-ENV-05 [v1] (Multi-Network Roaming)**: The networking subsystem MUST support profile-based management across home WPA2, enterprise 802.1X, mobile hotspots, and captive portals via a mix of iwd client automation and w3m/curl-based portal handling (3.10).
* **REQ-ENV-06 [v0] (Air Travel Pack Compliance)**: The onboard battery pack MUST remain strictly under 100 Wh (3S 18650 pack ~35 Wh) to comply with FAA/ICAO passenger aircraft cabin carry-on regulations (3.09).
* **REQ-ENV-07 [v0] (Daily Use Duration)**: The deck MUST support a daily use pattern of 6 hours active usage and 18 hours idle (3.11).

## REQ-INP (Input Subsystem)

* **REQ-INP-01 [v0] (CardKB Terminal Control Mapping)**: The input subsystem MUST map terminal control characters (Ctrl, Alt, Esc, Tab, Arrow keys, Function keys) via software modifier layers and sequential sticky chords on the CardKB matrix (4.01).
* **REQ-INP-02 [v0] (Key-to-Glyph Latency)**: Keypress-to-terminal display latency MUST remain imperceptible (<50 ms) under normal typing load (4.13).
* **REQ-INP-03 [v1] (Modal Rotary Encoder)**: The input subsystem SHALL support a hardware rotary encoder with a push-button modal cycle (volume, brightness, scroll, font size) and visual mode indicator (4.07).
* **REQ-INP-04 [v1] (Tactile Haptics & Audible Alerts)**: The system SHALL support a vibration motor and piezo buzzer for critical system state warnings (battery <5%, earlyoom kills, critical system alarms) bounded by active audio profiles (4.09, 4.10, REQ-ENV-04).
* **REQ-INP-05 [v1] (Sensory Management Mode)**: The UI and alert system MUST provide a single-action toggle to silence auxiliary alerts and prevent cognitive sensory overload (4.12).
* **REQ-INP-06 [v1] (Ambidextrous Layout)**: Physical chassis controls and button positions SHOULD maintain bilateral symmetry for equal left- and right-handed reachability (4.16).
* **REQ-INP-07 [v1] (Auxiliary Bluetooth Input)**: The system MAY support pairing external Bluetooth keyboards or input devices via the host Bluetooth controller (4.15).

## REQ-LIC (Licensing)

* **REQ-LIC-01 [v0] (Artwork Distribution)**: The `assets/images/cess` directory MAY be distributed publicly inside the open-source repository. The artist explicitly permitted non-commercial redistribution (C-01).

## REQ-PF (Purposes & Features)

* **REQ-PF-01 [v1] (Daily Driver)**: The unit MUST serve as a daily driver replacement for a smartphone (2.01).
* **REQ-PF-02 [v0] (Core Binaries)**: The base OS MUST successfully execute and prioritize `ssh`, `git`, `nmcli`, `nmap` and `nano` (2.04).
* **REQ-PF-03 [v2+] (Text Discord Client)**: The deck MAY include or support a custom text-only Discord integration, bounded by API TOS terms (2.06).
* **REQ-PF-04 [v1] (Text Web Browser)**: The deck MUST support text-only web browsing with minimal JS execution (2.07).
* **REQ-PF-05 [v1] (Markdown Renderer)**: The terminal layer MUST support a custom Markdown viewer parsing basic markers into VT100 bold/color sequences (2.08).
* **REQ-PF-06 [v0] (Python & Bash)**: The development environment MUST support Bash and Python, optimized for small scripts due to the restrictive physical keyboard (2.09).
* **REQ-PF-07 [v1] (Audio playback)**: The deck MUST support streaming/MP3 audio playback out over the Type-C 3.5mm adapter interface. To preserve CPU and UART bandwidth for TUI rendering, audio MUST operate as a background asynchronous process with minimal UI feedback (2.11).
* **REQ-PF-08 [v1] (OTP & Passwords)**: The deck MUST feature offline credential and OTP management (2.14).
* **REQ-PF-09 [v1] (Text Gaming)**: The deck MAY include low-bandwidth text-mode games (e.g., Snake, Nethack, Zork), strictly bound by the ~11.5 KB/s text-only serial throughput constraint (2.17).
* **REQ-PF-10 [v2+] (Hardware Hacking)**: The deck MAY integrate serial consoles, logic analyzer software, or JTAG firmware programmers at a later date (Non-priority, 2.15).
* **REQ-PF-11 [v1] (Mathematical Suite)**: The deck SHOULD include a CLI interface for programmable plotting and math processing (2.16).
* **REQ-PF-12 [v0] (On-Demand Dashboard)**: The device MUST NOT run an always-on dashboard to save power, but MUST offer a terminal command or key-chord to display battery, network, and git status instantly (2.18).
* **REQ-PF-13 [v1] (Mobile Hotspot Integration)**: The deck MUST support connecting to smartphone-hosted Wi-Fi hotspots for external service access (2.01).
* **REQ-PF-14 [v2+] (Discord Messaging)**: The deck SHALL support text-based communication via official Discord webhook APIs for private messaging (2.06).
* **REQ-PF-16 [v0] (Resource-Efficient Icons)**: Icons in the status bar or dashboard SHOULD be rendered efficiently, acknowledging the serial link speed limitations of the UART bridge (5.02, 5.03).

## REQ-OPS (Compute, OS & Performance)

* **REQ-OPS-01 [v0] (Strict Lightweight Runtime)**: The operating system and service stack MUST avoid containerization (Docker/LXC) and heavy databases to stay within the 416MB RAM envelope of the Pi Zero 2W (6.03, 6.04).
* **REQ-OPS-02 [v0] (Memory Safety Bounds)**: System services MUST operate with `MemoryMax=` ceilings to prevent swap-thrash and system-wide OOM panics; the system SHALL be considered broken below 50MB free RAM (6.05).
* **REQ-OPS-03 [v1] (Live Hardware Watchdog)**: The system MUST utilize a hardware watchdog for auto-rebooting on kernel hangs and notify the user of any crash recovery events upon the next login (6.10).
* **REQ-OPS-04 [v0] (Multi-tenant Security & Guest Demo Hardening)**: The system MUST provide an unprivileged `guest` demo user account (password: `guest`) engineered for public crowd interaction where arbitrary code execution is assumed (6.09). Security MUST be strictly enforced at the kernel and OS level:
  1. **Privilege & Authentication Gate**: `guest` MUST have no `sudo` rights, no auxiliary groups, and MUST be denied in `sshd` (`DenyUsers guest`), `su`, `sudo`, and standard console login. PAM MUST permit `guest` authentication exclusively within the CYD `terminal` PAM service.
  2. **Network Isolation**: All network traffic for `guest` MUST be completely dropped via `nftables` (`skuid "guest"`), including local loopback interfaces (`lo`), preventing access to local services (File Browser, Syncthing, NetBird, etc.).
  3. **Resource & Slice Ceilings**: Systemd slice limits MUST bound `guest` resource consumption (`MemoryMax=64M`, `TasksMax=30`, `CPUQuota=50%`), enforce single-session limits, set `nofile`/`fsize` ulimits, and prohibit core dumps.
  4. **Process Reaper**: A dedicated systemd reaper daemon MUST SIGKILL any process owned by `guest` (excluding the top-level login shell session) whose wall-clock age exceeds 5 seconds. A PATH shim for `python3` and `node` with a timeout SHOULD serve as an advisory layer.
  5. **Ephemeral Storage & Privacy**: The `guest` home directory MUST reside on an in-memory `tmpfs` (max 8MB) that is automatically wiped upon logout. `guest` MUST NOT have read access to `/home/neko`, `/root`, `/mnt/250GB-SSD`, Wi-Fi/iwd credentials, NetBird tokens, SSH keys, Ansible files, or vault secrets. `/proc` MUST enforce `hidepid=2` so other users' processes are invisible.
  6. **Power & System Integrity**: `guest` MUST NOT be permitted to execute `poweroff`, `reboot`, or `suspend` via `polkit`/`logind`, and MUST NOT be able to write outside its ephemeral tmpfs.
  7. **Demo Tooling & Mode**: The environment MUST provide a `demo` command presenting safe, lightweight utilities (fastfetch, light toys, one-liners). A `demo_mode` configuration flag MUST ensure the login UI defaults to the guest account while preserving a documented escape path to `neko` or `root`.
* **REQ-OPS-05 [v0] (System Configuration)**: The system MUST support user-configurable timezone, keyboard layout, and idle timeout settings, persisting across sessions via `.whiskerframe.yaml` or user-space configuration (6.11, 6.13).
* **REQ-OPS-06 [v1] (Dotfile Parity)**: The environment MUST support declarative configuration synchronization (e.g., Ansible or chezmoi) to match the operator’s existing laptop dotfile ecosystem (6.12).

## REQ-PWR (Power & Battery Management)

* **REQ-PWR-01 [v1] (Three-Tier Power Profiles)**: The power management subsystem MUST implement three defined profiles: `ACTIVE` (standard clocking, display on, radios active), `IDLE/POWERSAVE` (CPU governor 600MHz, display blanked/dimmed, SSD spindown via `hdparm -y`), and `AIRPLANE/DEEP-IDLE` (all radios disabled via `rfkill`, display off, CPU 600MHz, ~0.55W idle target) (9.08, F09.08).
* **REQ-PWR-02 [v0] (Hardware Low-Battery Cutoff)**: The system MUST trigger an orderly emergency shutdown at 5% battery capacity to protect lithium cell chemistry from over-discharge and prevent BTRFS filesystem corruption (9.05, 9.06).
* **REQ-PWR-03 [v0] (Telemetry-Based Capacity Profiling)**: The system SHALL sample and log voltage/current telemetry from the Waveshare UPS I2C interface (INA219) to characterize cell capacity and runtime curves in software, without requiring external testing hardware (9.07, F09.01).
* **REQ-PWR-04 [v0] (Dedicated DC Pack Charging)**: The internal 3S 18650 UPS pack MUST be charged via its dedicated DC barrel jack / bundled charger; run-while-charging MUST be supported; USB-PD pack charging is deferred to v2 (9.02, 10.04).
* **REQ-PWR-05 [v0] (Always-On Mobile Idle)**: The system SHALL maintain an always-on low-power idle state rather than cold boot cycles when stationary (9.09).

## REQ-MECH (Mechanical, Chassis & Fabrication)

* **REQ-MECH-01 [v0] (Chassis Envelope)**: The physical chassis MUST measure approximately 110 x 180 x 70 mm or smaller, fitting strictly within an A5 perimeter (148 x 210 mm) (10.01, F10.01).
* **REQ-MECH-02 [v1] (Laser-Cut Fabrication)**: Case components SHALL be laser-cut from black acrylic and MDF using the in-house Ortur Laser Master 3; complex 3D-printed brackets SHALL be outsourced (10.02, 10.03).
* **REQ-MECH-03 [v1] (Drop Resistance & Structural Cushioning)**: Mechanical design MUST prioritize shock/drop protection over sub-centimeter thickness, allocating up to +10 mm protective buffer and shock mounting for the SSD (10.09, F10.09).
* **REQ-MECH-04 [v0] (Exposed Port Complement)**: The chassis MUST expose a DC barrel charging jack, 2x USB-A host ports from the internal hub, and an optional mini-HDMI extension to full HDMI (10.04).
* **REQ-MECH-05 [v0] (Passive Conduction Thermal Path)**: Thermal dissipation MUST rely strictly on passive conduction from the Pi Zero 2W SoC to an external aluminum plate or heatsink bracket (10.06).
* **REQ-MECH-06 [v0] (Sealed Deck Philosophy)**: The chassis MUST remain a sealed enclosure with no required physical maintenance ports under normal field conditions (10.07).
* **REQ-MECH-07 [v0] (WhiskerFrame Brand Identity)**: Case engraving, physical badging, and terminal UI MUST prominently express the WhiskerFrame identity and cat-themed personality (10.11, 10.12).

## REQ-MOD (Modularity & Bus Architecture)

* **REQ-MOD-01 [v0] (Tiered Bus Hierarchy)**: System buses MUST follow a 3-tier hierarchy: Small Bus (UART to CYD, I2C-0 to CardKB, I2C-1 to UPS/RTC), Medium Bus (USB 2.0 via hub), and Big Bus (PCIe/NVMe deferred to future host upgrades) (11.01, 11.02).
* **REQ-MOD-02 [v1] (Modular Peripheral Isolation & Protection)**: Small-bus auxiliary rails (3.3V/5V) MUST incorporate TVS transient voltage suppression and PTC overcurrent protection capped at 100mA for sensor interfaces (11.04). High-power modular peripherals (LTE, SDR) MUST operate exclusively over USB 2.0 host ports (11.04).
* **REQ-MOD-03 [v1] (Standardized Interface Adoption)**: Custom edge-card slot connectors, EEPROM auto-detection (`VID:PID` + UUIDv7), and multi-protocol pin negotiation are deferred to v2. Modular expansion in v1 MUST adopt standard open standards: Qwiic/STEMMA QT (I2C) for small-bus sensors and standard USB 2.0 Type-A for medium-bus peripherals (10.08, 11.03, 11.10).
