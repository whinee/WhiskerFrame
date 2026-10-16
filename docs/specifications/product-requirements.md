# WhiskerFrame Product Requirements Document (PRD)

This document formalizes the product requirements for the WhiskerFrame Cyberdeck across hardware, firmware, operating system, security, networking, and user experience domains. Every requirement carries a formal identifier (`REQ-<domain>-<id>`), a target milestone (`[v0]`, `[v1]`, or `[v2+]`), normative requirement text (RFC 2119), rationale, and architectural cross-references.

---

## Specification Triad & Separation of Concerns

The WhiskerFrame engineering specification is partitioned into a three-document triad:

1. **`docs/specifications/architecture.md`**: Defines *system topology*, physical/electrical node matrices, hardware interfaces, protocol contracts, and RAM/swap memory budgets.
2. **`docs/specifications/tasks.md`**: Defines *implementation status* and tracking for engineering work packages (TSK-01 through TSK-16) across delivery waves.
3. **`docs/specifications/product-requirements.md` (this document)**: Defines *formal normative requirements* (`REQ-*`) tagged with release targets (`v0`, `v1`, `v2+`) and explicit physics/engineering arithmetic.

Supporting domain contracts reside in `contracts/wire-protocol.md` (serial framing), `terminal.md` (TUI & input line discipline), `storage-mount.md` (BTRFS generator), `display-color.md` (RGB565 encoding), and `orchestration.md` (agent boundaries). Architectural decisions (WHY) are chronologically recorded in `docs/dev/ai-decisions.md` (DEC-W1 through DEC-W30).

---

## Version Roadmap Summary Matrix

| Milestone | Target Horizon | Primary Focus | Key Architectural Invariants |
| --- | --- | --- | --- |
| **`v0`** | **Demo Prototype** (Current) | Public demonstration readiness, live terminal login, physical input, guest containment, storage stability. | CYD 320x240 LCD over 115200 UART, CardKB 50-key over I2C, 53-col VT100 bridge, PAM login (`neko`/`guest`), ephemeral 8MB tmpfs with `nftables` egress block, persistent SSD mount (`btrfs`), log2ram wear reduction, Wi-Fi persistence (rfkill default 1, regdom PH), 3-tier self-heal watchdog, INA219 battery telemetry, hybrid goodbye splash + sleep opcode `0x06`. |
| **`v1`** | **Field Hardened** | Autonomous off-grid operation, true timekeeping, zero standby battery drain, mesh networking. | Hardware RTC (DS3231 I2C @ `0x68`) for offline monotonic time, physical power button wired to Pi Zero 2W RUN pads, host-lost coprocessor heartbeat supervisor, `gpio-poweroff` load switch for CYD 5V rail, NetBird zero-config mesh overlay, dual-band (5 GHz) USB Wi-Fi upgrade. |
| **`v2+`** | **Commercial Kit** | WhiskerFrame production kits, mass reproducibility, integrated silicon, custom industrial design. | Custom PCB mainboard integrating Pi CM4/Zero 2W + ESP32-S3 coprocessor + integrated PMIC, MAX17048 hardware battery fuel gauge with ModelGauge algorithm, commercial art licensing transition from Cess non-commercial terms. |

---

## 1. REQ-CAP: User-Facing Capabilities

* **REQ-CAP-01 [v0/v1] (Offline Reading & Documentation)**: In `v0`, the system MUST provide core offline documentation (`man`, `bash-doc`, `python3-doc`) accessible via a 53-column helper (`wiki`). In `v1`, the deck MUST host an offline Kiwix repository (e.g., Simple English Wikipedia ~1GB ZIM) on loopback, isolated from the guest demo environment. (DEC-W29, TSK-15).
* **REQ-CAP-02 [v0] (Local Scripting & Development)**: The deck MUST support local shell scripting and Python execution on the host (`python3`, `bash`), optimized for small utilities due to the 50-key CardKB form factor. (DEC-W16, 2.09).
* **REQ-CAP-03 [v0] (Text-Only Operational Modality)**: The deck MUST operate strictly as a text-only platform. Local machine learning or large language model (LLM) inference on the Pi Zero 2W is strictly prohibited to protect the 416 MB RAM ceiling; agent orchestration occurs exclusively on external workstation nodes. (A.03, DEC-W16).

---

## 2. REQ-UX: Hardware UX & Ergonomics

* **REQ-UX-01 [v0] (Physical Envelope)**: The assembled cyberdeck MUST fit within an A5 perimeter (148 x 210 mm) and SHOULD NOT exceed 70 mm in thickness (inclusive of rubber drop bumpers and SSD shock mounts). (10.01, F10.01, DEC-W17, DEC-W22).
* **REQ-UX-02 [v0] (Tactile Hardware Input)**: The deck MUST feature physical switches with positive tactile feedback (not capacitive glass) to support thumb-typing during mobile transit. (1.07, 3.02).
* **REQ-UX-03 [v0] (Anti-Distraction Environment)**: The operating system MUST NOT install or run notification daemons, push services, or advertising engines that interrupt the fullscreen terminal workflow. (1.04).
* **REQ-UX-04 [v0] (Declarative UI Customization)**: The terminal subsystem MUST support user-configurable color themes, typography, status-line fields, and screen geometry via `.whiskerframe.yaml` and on-device configuration files. (A.02, 5.01, DEC-W19).
* **REQ-UX-05 [v0] (Boot Splash Display)**: The device MUST display a boot splash screen composited with the WhiskerFrame visual identity, rendered within 1–2 seconds of terminal initialization, holding for 3.0 seconds before presenting the login interface. (5.09, DEC-W19, DEC-W30).
* **REQ-UX-06 [v1] (Physical Control Switches)**: The system MUST provide dedicated physical toggle switches for hardware radio kill (Wi-Fi/Bluetooth), master audio mute, and buzzer silence to enforce silent operation in sensitive settings. (3.08, 4.07, 4.11).
* **REQ-UX-07 [v2+] (LED Matrix Deferral)**: Mounting of an auxiliary MAX7219 8x8 LED matrix is formally deferred to `v2+` to preserve chassis thinness and prevent RF/EMI interference inside the enclosure. (F-05.02, DEC-W19).
* **REQ-UX-08 [v0] (Resource-Efficient Glyph Caching)**: The CYD coprocessor font subsystem MUST restrict SPI RAM glyph caching to essential 7-bit ASCII, punctuation, and standard VT100 box-drawing characters, rejecting full Unicode/emoji glyph sets to prevent coprocessor heap exhaustion. (F-05.03, DEC-W19).
* **REQ-UX-09 [v0] (Orderly Goodbye & Reboot Splash)**: The system MUST execute an orderly goodbye sequence on systemd shutdown/reboot targets (`cyberdeck-goodbye-shutdown.service` rendering `"bai baiii!"`, `cyberdeck-goodbye-reboot.service` rendering `"brb :3"`), blitting a centered 128x128 doodle within a hard 8.0-second execution window before blanking the display. (WS-3, DEC-W29, DEC-W30).

---

## 3. REQ-TERM: Terminal & Display Subsystem

* **REQ-TERM-01 [v0] (CYD Display Interface)**: The terminal display MUST be driven by an ESP32-2432S028 (CYD) module running an ILI9341 320x240 LCD over USB-Serial (CH340) at 115200 baud runtime, locked exclusively by `terminal.service`. (DEC-W5, DEC-W14).
* **REQ-TERM-02 [v0] (53-Column VT100 Character Grid)**: The host Python bridge (`whiskerframe.terminal`) MUST maintain terminal state via a 53-column by 30-row VT100 grid emulator (6x8 font cells), transmitting incremental cell runs (`DRAW_CELLS`, opcode `0x03`) to minimize UART bandwidth. (DEC-W6, DEC-W29).
* **REQ-TERM-03 [v1] (Intermediate Typography & 8x12 Font)**: The firmware MUST support compile-time intermediate font geometries (e.g. 8x12 font yielding 40 columns by 20 rows) using anti-aliased bitmap fonts to improve legibility over raw 6x8 bitmap scaling. (DEC-W30).
* **REQ-TERM-04 [v0] (Compact Interactive Prompts)**: Interactive shell prompts in the CYD terminal MUST NOT exceed 3 characters (`n~ ` for neko, `g~ ` for guest, `r# ` for root) via `/etc/profile.d/cyd_prompt.sh`, preventing line-wrap truncation on the 53-column display. (DEC-W30).

---

## 4. REQ-INP: Input Subsystem & CardKB Ergonomics

* **REQ-INP-01 [v0] (CardKB Hardware Interface & Debounce)**: The input subsystem MUST read the M5Stack CardKB 50-key matrix via I2C-0 (`0x5F`) using `/dev/i2c-0` (Pins 27/28), filtered by a 30 ms identical-byte debounce window and a C0/ASCII/Fn-layer whitelist to eliminate power-rail ripple artifacts. (DEC-W6, TSK-01).
* **REQ-INP-02 [v0] (Key-to-Glyph Interactive Latency)**: End-to-end latency from physical CardKB keypress to display glyph illumination MUST NOT exceed 50 ms under nominal typing loads. (4.13).
* **REQ-INP-03 [v0] (Sequential Sticky Ctrl Latch)**: To resolve the physical absence of a Control key on CardKB, the input bridge MUST implement a sequential sticky Ctrl state machine triggered by `Fn+Tab` (`0x8C` or `Fn+Backspace` `0x8B`), masking the next alphanumeric key with `& 0x1F` to emit standard C0 control codes (`Ctrl+C` = `0x03`, `Ctrl+D` = `0x04`). The armed state MUST automatically expire after 3.0 seconds, on toggle press, or on invalid key entry. (WS-2, DEC-W29).
* **REQ-INP-04 [v0] (Visual & NeoPixel Latch Feedback)**: The armed Ctrl latch state MUST be visually indicated simultaneously by recoloring the terminal cursor cell to bright yellow (`theme.ansi[11]`) and illuminating the CardKB onboard SK6812 NeoPixel LED yellow (`RGB 255, 200, 0` via I2C opcode `0x13`), clearing immediately upon latch release. (DEC-W29, DEC-W30, TSK-16).
* **REQ-INP-05 [v0] (53-Column Key Cheatsheet)**: The system MUST provide an on-demand, 53-column CLI reference tool (`keys`) displaying all CardKB keybindings, modifier combinations, and symbol chords without requiring external documentation. (DEC-W29, TSK-12).
* **REQ-INP-06 [v1] (Modal Rotary Encoder)**: The input subsystem SHOULD support a hardware rotary encoder wired to the ESP32 coprocessor with a push-button cycle for terminal volume, backlight brightness, and font size adjustment. (4.07, DEC-W17).
* **REQ-INP-07 [v1] (Tactile Haptic & Piezo Alerts)**: The deck SHALL support a vibration motor and piezo buzzer for critical system state warnings (battery <5%, earlyoom kills, emergency thermal shutdown) governed by configurable audio profiles. (4.09, 4.10, REQ-ENV-04).
* **REQ-INP-08 [v1] (Cognitive Sensory Overload Toggle)**: The UI and alert system MUST provide a single-action chord/switch to instantly silence all auxiliary displays, tickers, and audible buzzers, restricting output to the primary terminal prompt. (4.12).
* **REQ-INP-09 [v1] (External Bluetooth Input)**: The system MAY support pairing external Bluetooth keyboards or input mice via the onboard Broadcom Bluetooth 4.2 controller. (4.15).

---

## 5. REQ-STORAGE: Storage Lifecycle, Mounts & Media

* **REQ-STORAGE-01 [v0] (Non-Destructive Mount Generator)**: The persistent SSD mount MUST be managed via a systemd `.mount` generator (`pi/storage/install_mount.py`) rendering from `.whiskerframe.yaml`. The generator MUST default to `--dry-run` and MUST NOT execute destructive partition or filesystem operations. (DEC-W7, TSK-02).
* **REQ-STORAGE-02 [v0] (BTRFS Whole-Disk Topology)**: The 250GB Samsung 860 EVO SSD MUST be formatted with BTRFS (label `cyberdeck-ssd`, UUID `98bb87d2-7128-470e-91d5-9e117df2ab1a`) hosting two distinct subvolumes: `@data` mounted at `/mnt/250GB-SSD` (`noatime,compress=zstd:3,nofail,x-systemd.device-timeout=5s`) and `@swap` hosting an uncompressed `nodatacow` swapfile. (DEC-W12, TSK-02a).
* **REQ-STORAGE-03 [v0] (SD Card Wear Mitigation)**: The OS root filesystem on the MicroSD card MUST be protected against write wear via `log2ram` (allocating a 32MB RAM ring buffer) and diverting persistent `systemd-journald` log storage to `/mnt/250GB-SSD/log/journal`. (DEC-W14, DEC-W25, TSK-03).
* **REQ-STORAGE-04 [v0] (Zero Uncurated Data Deletion)**: Project and user repositories on the persistent SSD MUST NOT be automatically purged; local cleanups remain manual, with primary copies retained on external git remotes or the operator's home server. (7.13, DEC-W20).
* **REQ-STORAGE-05 [v1] (Network-Gated Automated Snapshots)**: Automated backup mechanisms (e.g. Backrest / restic) for project repositories MUST synchronize only when connected to trusted, non-LTE networks to preserve battery and cellular data budgets. (7.07, 7.10, F-07.02, DEC-W20).
* **REQ-STORAGE-06 [v1] (Encrypted Authenticated File Sharing)**: File sharing over SMB or File Browser MUST require mandatory user authentication and wire encryption (`smb encrypt = required`) bounded by firewall isolation. (F-07.01, DEC-W20).

---

## 6. REQ-HW: Hardware Enclosure, Buses & Peripherals

* **REQ-HW-01 [v1] (Hardware Real-Time Clock)**: The system MUST incorporate an I2C DS3231 Real-Time Clock module (I2C-1 @ `0x68`) with backup battery to ensure monotonic timekeeping across cold boots without network access, eliminating TLS validation failures and git timestamp drift. (A.09, F-A.02, DEC-W15, DEC-W26).
* **REQ-HW-02 [v1] (Weatherproof Sealed Enclosure)**: Casework MUST provide a sealed, gasketed barrier protecting internal electronics from high ambient humidity and direct rain exposure typical of tropical Philippine transit. (1.10, 3.05, DEC-W17).
* **REQ-HW-03 [v0] (Modular External USB Peripherals)**: To maintain the <=70 mm chassis thickness ceiling and prevent thermal concentration inside the sealed enclosure, high-power USB peripherals (ZTE MF833V LTE modem, RTL-SDR dongle) MUST connect externally via exposed USB hub ports rather than being sealed internally. (C-03, DEC-W17).
* **REQ-HW-04 [v0] (3S 18650 UPS Power Supply)**: The internal battery subsystem MUST utilize a 3S 18650 UPS module (11.1V nominal, ~27.75 Wh energy) with an integrated I2C INA219 sensor (`0x41`) and dedicated 12.6V DC barrel charging. (DEC-W17, DEC-W21).
* **REQ-HW-05 [v1] (Physical Power Button via RUN Pads)**: The chassis MUST incorporate a momentary push button wired directly to the Raspberry Pi Zero 2W `RUN` pads, enabling clean hardware power-on from halt state and emergency hard reset when held.
* **REQ-HW-06 [v0] (Stock CardKB v1.1 Integration)**: Hardware input for `v0` MUST standardize on the stock M5Stack CardKB v1.1 unit, deferring custom keyboard PCB fabrication to `v2+`. (4.01, F-04.02).
* **REQ-HW-07 [v1] (Host-Lost Hardware Supervisory Watchdog)**: The ESP32 coprocessor MUST supervise host heartbeats over the UART link; if the host freezes for >60s without servicing the link, the coprocessor MUST display a crash recovery warning without false-triggering during normal boot. (6.10, DEC-W18).
* **REQ-HW-08 [v1] (GPIO-Poweroff Rail Load Switch)**: The system MUST incorporate a P-channel MOSFET load switch on the CYD 5V power rail driven by the Pi `gpio-poweroff` device-tree overlay, disconnecting display and backlight power when the Pi halts to eliminate standby battery drain.
* **REQ-HW-09 [v2+] (Custom WhiskerFrame Integrated Mainboard PCB)**: The `v2+` commercial revision MUST integrate the Raspberry Pi compute module (CM4 or Zero 2W), ESP32-S3 coprocessor, battery charger, and power management IC (PMIC) onto a single custom PCB, eliminating internal jumper wiring. (11.03, F11.02).

---

## 7. REQ-ENV: Environmental, Posture & Transit Boundaries

* **REQ-ENV-01 [v1] (Fanless Conduction Cooling)**: The cyberdeck MUST operate with 100% passive fanless cooling to preserve acoustic silence and prevent dust/water ingress, conducting heat from the SoC directly to an external aluminum plate. (3.05, DEC-W17, DEC-W22).
* **REQ-ENV-02 [v0] (Two-Thumb Handheld Posture)**: The physical balance and center-of-gravity of the chassis MUST support two-thumb typing while standing or commuting without requiring a table rest. (3.02, DEC-W17).
* **REQ-ENV-03 [v1] (Ambient Light Contrast Compensation)**: The display subsystem SHOULD sample the CYD on-board light-dependent resistor (LDR) to dynamically scale backlight PWM and automatically invert palettes to a high-contrast mono theme in direct sunlight. (3.06, 5.08, DEC-W19).
* **REQ-ENV-04 [v1] (Configurable Environmental Audio Profiles)**: The audio subsystem MUST provide three profile presets (`classroom/silent`, `office/quiet`, `commute/loud`) toggling haptics and buzzer volumes via hotkey or CLI. (3.08, DEC-W17).
* **REQ-ENV-05 [v1] (Multi-Network Profile Roaming)**: The network stack MUST support seamless roaming across home WPA2, campus 802.1X, mobile hotspots, and captive portals using `iwd`/NetworkManager profile automation and `w3m` portal landing. (3.10, DEC-W29).
* **REQ-ENV-06 [v0] (Passenger Aircraft Cabin Compliance)**: The internal 3S lithium-ion battery pack MUST NOT exceed 100 Wh (actual pack: 27.75 Wh nominal), complying strictly with FAA, ICAO, and CAAP regulations for passenger cabin carry-on baggage. (3.09, DEC-W17).
* **REQ-ENV-07 [v0] (Operational Duty Cycle)**: The deck MUST support an operational daily profile of at least 6.0 hours of active terminal usage and 18.0 hours of low-power idle. (3.11, DEC-W21).

---

## 8. REQ-OPS: Compute, OS, Memory Safety & Multi-Tenant Containment

* **REQ-OPS-01 [v0] (Strict Lightweight Native Services)**: The host OS MUST NOT run container runtimes (Docker, Podman, LXC) or heavy database engines (Postgres, FerretDB) to remain within the 416 MB RAM envelope; all services run as native systemd units. (6.03, DEC-W10, TSK-07).
* **REQ-OPS-02 [v0] (Memory Safety Floor & Cgroup Bounds)**: The system MUST enforce a 50 MB minimum free-RAM safety floor. Background daemons MUST be bounded by systemd `MemoryMax=` directives, with `earlyoom` configured to terminate non-critical processes before swap thrashing triggers kernel panic. (6.05, DEC-W11, TSK-07).
* **REQ-OPS-03 [v1] (Hardware Watchdog Supervision)**: The BCM2835 hardware watchdog (`/dev/watchdog0`) MUST be pet continuously by systemd (`RuntimeWatchdogSec=60s`), forcing an automatic board reset if the Linux kernel deadlocks. (6.10, DEC-W26, TSK-09).
* **REQ-OPS-04 [v0] (Multi-Tenant Hardened Guest Demo Sandbox)**: The system MUST provide an unprivileged `guest` account (password: `guest`) engineered for public hands-on demonstration under the assumption of arbitrary adversarial code execution:
  1. **Authentication Gate**: `guest` MUST NOT possess `sudo` rights or auxiliary groups; MUST be blocked in `sshd` (`DenyUsers guest`), `su`, and console ttys; and MUST authenticate strictly via the CYD `terminal` PAM service. (DEC-W27, TSK-10).
  2. **Kernel Network Isolation**: Outbound network traffic from UID `guest` MUST be dropped at the kernel netfilter layer via `/etc/nftables.d/guest_isolation.nft` (`skuid "guest" counter drop`), severing loopback (`127.0.0.1`), LAN, and WAN egress. (DEC-W27).
  3. **Resource & Cgroup Ceilings**: Resource consumption MUST be bounded via systemd slice limits (`MemoryMax=64M`, `TasksMax=30`, `CPUQuota=50%`), disabling core dumps and limiting open file descriptors. (DEC-W27).
  4. **5-Second Process Reaper**: A background supervisor (`cyberdeck-guest-reaper.service`) MUST poll every second and issue `SIGKILL` to any process owned by `guest` (excluding the interactive login shell `bash -l`) exceeding 5.0 seconds of elapsed execution time. (DEC-W27).
  5. **Ephemeral In-Memory Home Directory**: The `guest` home directory MUST reside on an 8MB `tmpfs` volume, automatically wiped and re-populated from `/etc/skel` upon session logout via PAM `pam_exec.so`. `guest` MUST NOT have read access to `/home/neko`, `/root`, `/mnt/250GB-SSD`, or network credentials. (DEC-W27).
  6. **Restricted Shell Environment**: `guest` MUST NOT be permitted to execute system poweroff/reboot via polkit or logind, and shell prompt MUST render as `g~ `. (DEC-W27, DEC-W30).
* **REQ-OPS-05 [v0] (System Configuration & Locales)**: System configuration defaults MUST standardize on UTC+0 and American English (`en_US.UTF-8`), configurable via `.whiskerframe.yaml`. (6.11).
* **REQ-OPS-06 [v1] (Declarative Dotfile Synchronization)**: The environment MUST support automated configuration management (via Ansible or chezmoi) to maintain parity with the operator's primary workstation dotfiles. (6.12, DEC-W14).
* **REQ-OPS-07 [v0] (PAM Login & PTY Bridge)**: Terminal authentication MUST use standard Linux PAM services (`simplepam`) to spawn isolated PTY sessions for `root`, `neko`, or `guest`, rendering a demo banner when `terminal.login.demo_mode` is enabled. (DEC-W29, TSK-11).
* **REQ-OPS-08 [v0] (Clock Monotonicity via `fake-hwclock`)**: In the absence of a hardware RTC in `v0`, the OS MUST utilize `fake-hwclock` to save and restore timestamps on boot and shutdown, preventing the system clock from regressing to the 1970 UNIX epoch. (DEC-W26, TSK-09).
* **REQ-OPS-09 [v0] (3-Tier Self-Healing Network Watchdog)**: The system MUST run `/usr/local/bin/cyberdeck-net-heal.sh` every 30 seconds via systemd timer to detect gateway ping failure. Escalation MUST proceed through Tier 1 (`rfkill unblock wifi` + reconnect), Tier 2 (restart NetworkManager after 5m), and Tier 3 (reload kernel module `brcmfmac` after 15m), and MUST NEVER issue a system reboot. (DEC-W26, TSK-09).

---

## 9. REQ-PWR: Power Profiles & Battery Management

* **REQ-PWR-01 [v1] (Three-Tier Power Management Profiles)**: The power management subsystem MUST implement three software profiles:
  1. `ACTIVE`: Full CPU frequency (1.0 GHz), display backlight on, radios active, SSD active (~3.2W typical load).
  2. `IDLE/POWERSAVE`: CPU governor set to `powersave` (600 MHz), display dimmed, SSD spun down via `hdparm -y`, auxiliary polling paused (~1.8W idle).
  3. `AIRPLANE/DEEP-IDLE`: All radios disabled via `rfkill`, display unpowered via opcode `0x06`, CPU 600 MHz (~0.55W sleep). (9.08, F09.08, DEC-W21).
* **REQ-PWR-02 [v0] (Low-Battery Emergency Cutoff)**: The battery monitoring daemon MUST initiate an orderly emergency shutdown when remaining battery capacity drops to 5%, preventing lithium cell over-discharge and BTRFS metadata corruption. (9.05, 9.06, DEC-W21).
* **REQ-PWR-03 [v0] (Telemetry Capacity Profiling)**: Pack voltage, current, and capacity MUST be continuously sampled and logged from the Waveshare UPS I2C INA219 sensor (`0x41`) by `battery-monitor.service`, characterizing discharge curves in software without external test bench instruments. (9.07, F09.01, DEC-W21).
* **REQ-PWR-04 [v0] (Dedicated 3S DC Charging)**: The internal 3S 18650 pack MUST be charged via a dedicated 12.6V DC barrel jack; simultaneous operation while charging (run-while-charging) MUST be supported. (9.02, DEC-W21).
* **REQ-PWR-05 [v0] (Always-On Mobile Operational Stance)**: The cyberdeck MUST operate as an always-on mobile terminal, entering low-power idle rather than performing cold boot cycles when carried. (9.09, DEC-W21).
* **REQ-PWR-06 [v0] (Firmware Sleep Opcode `0x06`)**: The wire protocol and ESP32 firmware MUST support opcode `0x06` (`SLEEP`) to place the display controller in low-power sleep (DISPOFF/SLPIN, backlight PWM 0%, CPU 80 MHz, ~75 mW draw) while remaining awake on the serial RX pin to wake instantly on the next frame. (WS-3, DEC-W29).
* **REQ-PWR-07 [v1] (Unswitched Rail Standby Drain Elimination)**: The hardware power architecture MUST eliminate unswitched standby current drain on the CYD 5V rail by incorporating a load switch controlled via GPIO poweroff signals.
* **REQ-PWR-08 [v2+] (Hardware Battery Fuel Gauge)**: The `v2+` mainboard MUST incorporate an integrated MAX17048 I2C fuel gauge utilizing the ModelGauge algorithm to track state-of-charge, eliminating voltage-sag estimation errors during CPU bursts.

---

## 10. REQ-NET: Networking, Wi-Fi Persistence & Mesh Overlays

* **REQ-NET-01 [v0] (53-Column Terminal Wi-Fi Helper)**: The deck MUST provide a dedicated CLI utility (`wifi`) formatted for 53-column displays wrapping NetworkManager (`status`, `scan`, `join`, `forget`), with profile lookup and `wpa-psk` validation. (WS-4, DEC-W29, DEC-W30, TSK-14).
* **REQ-NET-02 [v0] (Wi-Fi Cold Boot Persistence & Radio Unblock)**: The networking subsystem MUST automatically restore Wi-Fi connectivity within 2.0 seconds of cold boot by setting `options rfkill default_state=1` in `/etc/modprobe.d/rfkill_default.conf`, enforcing `cfg80211.ieee80211_regdom=PH`, setting `wifi.powersave=2` (disabled), and assigning priority 100 to known connections. (DEC-W25, TSK-08).
* **REQ-NET-03 [v1] (NetBird Zero-Config Mesh VPN)**: The deck MUST integrate a native NetBird client connecting to the operator's self-hosted coordination server (`100.86.0.0/16`), allowing seamless peer-to-peer SSH access across roaming networks without opening firewall ports. (5.49, 8.06, DEC-W11, DEC-W14).
* **REQ-NET-04 [v1] (Dual-Band Wi-Fi Upgrade)**: The networking subsystem MUST support an optional USB dual-band (2.4 GHz / 5 GHz) Wi-Fi adapter to enable connectivity with 5 GHz-only mobile hotspots (such as Redmi Note 12). (8.02, F-08.01, DEC-W29).

---

## 11. REQ-MECH: Mechanical, Casework & Thermal Conduction

* **REQ-MECH-01 [v0] (Chassis Envelope Bounds)**: The mechanical enclosure MUST measure approximately 110 x 180 x 70 mm or smaller, remaining within an A5 perimeter (<148 x 210 mm). (10.01, F10.01, DEC-W22).
* **REQ-MECH-02 [v1] (Acrylic & MDF Laser Fabrication)**: Casework components MUST be laser-cut from black acrylic and MDF using an Ortur Laser Master 3; complex internal brackets and card guides MAY be 3D printed. (10.02, 10.03, DEC-W22).
* **REQ-MECH-03 [v1] (Drop Protection & Shock Isolation)**: Casework design MUST allocate up to +10 mm of external protective bumper thickness and internal silicone shock mountings for the SATA SSD, prioritizing physical drop survival over sub-centimeter thickness. (10.09, F10.09, DEC-W22).
* **REQ-MECH-04 [v0] (External Port Complement)**: The chassis casework MUST expose: 1x DC barrel charging jack (12.6V), 2x USB-A 2.0 host ports, and an optional mini-HDMI extension port. (10.04, DEC-W22).
* **REQ-MECH-05 [v0] (Passive Thermal Conduction Path)**: The BCM2837B0 SoC MUST dissipate heat via a direct thermal conduction pad ($k \ge 3.0\text{ W}/(\text{m}\cdot\text{K})$) coupled to an internal aluminum bracket/exterior heatsink plate, maintaining junction temperatures below 75°C without cooling fans. (10.06, DEC-W17, DEC-W22).
* **REQ-MECH-06 [v0] (WhiskerFrame Cat-Themed Branding)**: Casework engraving, badging, and terminal UI MUST prominently express the WhiskerFrame brand identity and cat-themed aesthetic. (10.11, 10.12, DEC-W22).

---

## 12. REQ-MOD: Modularity & Expansion Interfaces

* **REQ-MOD-01 [v0] (Three-Tier Bus Hierarchy)**: System interconnects MUST follow a 3-tier hierarchy: Small Bus (UART to CYD, I2C-0 to CardKB, I2C-1 to UPS/RTC), Medium Bus (USB 2.0 via hub), and Big Bus (PCIe/NVMe deferred to future compute upgrades). (11.01, 11.02, DEC-W23).
* **REQ-MOD-02 [v1] (Small-Bus Electrical Protection)**: Small-bus auxiliary power rails (3.3V/5V) MUST incorporate TVS transient voltage suppression and a 100 mA PTC resettable fuse. High-power peripherals (LTE, SDR) are strictly prohibited from small-bus rails and MUST connect via USB 2.0. (11.04, DEC-W23).
* **REQ-MOD-03 [v1] (Open Modular Interface Standardization)**: Custom edge-card modular backplanes, EEPROM auto-detection (`VID:PID`), and dynamic pin negotiation are deferred to `v2+`. Modular sensor expansion in `v1` MUST adopt standard SparkFun Qwiic / Adafruit STEMMA QT (4-pin JST-SH 1.0mm) I2C connectors. (10.08, 11.03, 11.10, DEC-W23).

---

## 13. REQ-LIC: Intellectual Property & Artwork Distribution

* **REQ-LIC-01 [v0] (Non-Commercial Community Artwork)**: Third-party artistic assets in `assets/images/cess/` MAY be distributed in the public git repository under the artist's explicit personal, non-commercial permission grant (dated 2026-10-15). Commercial redistribution and unauthorized derivative modifications remain strictly prohibited. (A.12, C-01, DEC-W28).
* **REQ-LIC-02 [v2+] (Commercial Artwork Licensing Transition)**: Artwork under `assets/images/cess/` MUST NOT ship in commercial hardware kits or commercial sales. For any `v2+` commercial kit release, replacement bespoke artwork MUST be procured or formal commercial licensing terms executed with the artist prior to sale. (C-01, DEC-W28).

---

## 14. Engineering & Physics Arithmetic

This section establishes the empirical calculations and physical boundary conditions governing WhiskerFrame hardware design.

### 14.1 System Power Budget & Rail Allocation

All voltages, currents, and power figures are derived from manufacturer datasheets and empirical measurement across operational states:

| Subsystem / Component | Nominal Rail | Idle Current | Idle Power | Active/Load Current | Active Power | Sleep Current | Sleep Power |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **Raspberry Pi Zero 2W** (BCM2837B0) | 5.0 V | 120 mA | 0.60 W | 350–500 mA | 1.75–2.50 W | 80 mA (600MHz idle) | 0.40 W |
| **CYD Display + Backlight** (ESP32) | 5.0 V | 130 mA | 0.65 W | 160–180 mA | 0.80–0.90 W | <15 mA (opcode `0x06`) | 0.075 W |
| **M5Stack CardKB** (ATmega328P) | 3.3 V | 5 mA | 0.016 W | 5 mA | 0.016 W | 5 mA | 0.016 W |
| **Samsung 860 EVO SSD** (250GB) | 5.0 V | 100 mA | 0.50 W | 400 mA | 2.00 W | 50 mA (`hdparm -y`) | 0.25 W |
| **USB 2.0 Hub + Bus Logic** | 5.0 V | 10 mA | 0.05 W | 16 mA | 0.08 W | 10 mA | 0.05 W |
| **System Total (Idle Profile)** | **5.0 V** | **~365 mA** | **~1.82 W (≈ 1.8 W)** | — | — | — | — |
| **System Total (Typical Active Demo)**| **5.0 V** | — | — | **~640 mA** | **~3.20 W (≈ 3.2 W)** | — | — |
| **System Total (Maximum Peak Stress)**| **5.0 V** | — | — | **~1100 mA** | **~5.50 W (≈ 5.5 W)** | — | — |

*Summary*: Continuous system power draw is **~1.8 W** in Idle, **~3.2 W** in Typical Active Demonstration, and **~5.5 W** in Maximum Quad-Core Peak Stress with concurrent disk I/O.

---

### 14.2 Battery Energy & Runtime Calculations

The onboard energy storage subsystem comprises three 18650 lithium-ion cells connected in series (3S1P configuration):

* **Pack Configuration**: 3S Li-ion (nominal cell voltage $V_{\text{cell}} = 3.7\text{ V}$, fully charged $4.2\text{ V}$, cutoff $3.0\text{ V}$).
* **Nominal Pack Voltage**: $V_{\text{pack}} = 3 \times 3.7\text{ V} = 11.1\text{ V}$.
* **Nominal Cell Capacity**: $C_{\text{pack}} = 2500\text{ mAh} = 2.50\text{ Ah}$.
* **Nominal Total Pack Energy**:
  $$E_{\text{total}} = V_{\text{pack}} \times C_{\text{pack}} = 11.1\text{ V} \times 2.50\text{ Ah} = 27.75\text{ Wh}$$
* **DC-DC Step-Down Buck Converter Efficiency**: $\eta = 85\% = 0.85$ (Waveshare 3S UPS module converting 11.1V to 5.0V system rail).
* **Effective Usable Energy Delivered to 5V Rail**:
  $$E_{\text{eff}} = E_{\text{total}} \times \eta = 27.75\text{ Wh} \times 0.85 = 23.5875\text{ Wh}$$

#### Runtime Projections Across Operational States:

1. **Idle Runtime (1.8 W draw)**:
   $$T_{\text{idle}} = \frac{E_{\text{eff}}}{P_{\text{idle}}} = \frac{23.5875\text{ Wh}}{1.80\text{ W}} \approx 13.10\text{ hours (13.1 h)}$$
2. **Active Demo Runtime (3.2 W typical load)**:
   $$T_{\text{active}} = \frac{E_{\text{eff}}}{P_{\text{active}}} = \frac{23.5875\text{ Wh}}{3.20\text{ W}} \approx 7.37\text{ hours (7.4 h)}$$
3. **Worst-Case Maximum Load Runtime (5.5 W peak stress)**:
   $$T_{\text{max}} = \frac{E_{\text{eff}}}{P_{\text{max}}} = \frac{23.5875\text{ Wh}}{5.50\text{ W}} \approx 4.29\text{ hours (4.3 h)}$$

Accounting for the mandatory 5% emergency cutoff buffer ($E_{\text{reserve}} = 1.18\text{ Wh}$), usable field runtimes are **12.5 hours** in Idle and **7.0 hours** in continuous interactive demonstration.

---

### 14.3 Serial Link Bandwidth & Frame Rate Calculation

Communication between the Raspberry Pi Zero 2W host and the CYD ESP32 coprocessor travels over a dedicated USB-Serial UART bridge (CH340):

* **UART Line Encoding**: 8-N-1 (1 start bit, 8 data bits, 1 stop bit = 10 physical bits per transmitted byte).
* **Terminal Geometry**: 320x240 pixels. Character font cell: 6x8 pixels.
* **Character Grid Dimensions**:
  $$\text{Columns} = \left\lfloor\frac{320}{6}\right\rfloor = 53, \quad \text{Rows} = \left\lfloor\frac{240}{8}\right\rfloor = 30, \quad \text{Total Cells} = 53 \times 30 = 1590\text{ cells}$$
* **Text Frame Payload**: Optimized row-diff streaming in `whiskerframe.protocol` requires an average of **782 bytes** per full-screen text refresh (spanning text data and attribute headers).

#### Baud Rate and Throughput Limits:

1. **Standard Runtime Link (115200 baud)**:
   $$\text{Throughput}_{115200} = \frac{115,200\text{ bits/s}}{10\text{ bits/byte}} = 11,520\text{ bytes/s} = 11.52\text{ KB/s}$$
   $$\text{Frame Rate (Text Grid)} = \frac{11,520\text{ bytes/s}}{782\text{ bytes/frame}} \approx 14.73\text{ fps (≈ 14.7 fps)}$$
2. **High-Speed Link (230400 baud)**:
   $$\text{Throughput}_{230400} = \frac{230,400\text{ bits/s}}{10\text{ bits/byte}} = 23,040\text{ bytes/s} = 23.04\text{ KB/s}$$
   $$\text{Frame Rate (Text Grid)} = \frac{23,040\text{ bytes/s}}{782\text{ bytes/frame}} \approx 29.46\text{ fps (≈ 29.4 fps)}$$

#### Mathematical Comparison with Uncompressed Graphical RGB565 Bitmaps:
A full uncompressed 320x240 RGB565 image contains $320 \times 240 \times 2 = 153,600\text{ bytes}$.
* At 115200 baud: Transfer time is $\frac{153,600\text{ B}}{11,520\text{ B/s}} = 13.33\text{ seconds/frame}$ ($0.075\text{ fps}$).
* At 230400 baud: Transfer time is $\frac{153,600\text{ B}}{23,040\text{ B/s}} = 6.67\text{ seconds/frame}$ ($0.150\text{ fps}$).

*Engineering Takeaway*: Full graphical frame blitting over UART is completely unviable for interactive terminal usage, mathematically dictating VT100 character-cell differential updates (`DRAW_CELLS`, yielding 14.7–29.4 fps) and restricting bitmap operations strictly to static boot/goodbye splash sequences.

---

### 14.4 Thermal Dissipation & Passive Cooling Delta-T Analysis

The cyberdeck operates in a completely sealed, fanless enclosure to withstand tropical humidity (Philippine ambient $T_{\text{amb}} = 35^\circ\text{C}$):

* **Enclosure Internal Dimensions**: $110\text{ mm} \times 180\text{ mm} \times 70\text{ mm}$.
* **Internal Volume**: $V = 0.11 \times 0.18 \times 0.07\text{ m}^3 = 0.001386\text{ m}^3 = 1.386\text{ L}$.
* **Total Exterior Surface Area**:
  $$A_{\text{case}} = 2 \times (0.11 \times 0.18 + 0.11 \times 0.07 + 0.18 \times 0.07) = 2 \times (0.0198 + 0.0077 + 0.0126) = 0.0802\text{ m}^2$$
* **Internal Heat Dissipation ($Q$) Under Sustained Load**:
  * Pi Zero 2W SoC (BCM2837B0 at 1.0 GHz quad-core load): $P_{\text{SoC}} = 2.00\text{ W}$.
  * Samsung 860 EVO SSD (active read/write): $P_{\text{SSD}} = 1.50\text{ W}$.
  * UPS DC-DC converter losses ($P_{\text{conv}} = 3.2\text{ W} \times (1 - 0.85)/0.85$): $P_{\text{conv}} \approx 0.56–0.80\text{ W}$.
  * Total internal thermal dissipation: $Q = 2.00 + 1.50 + 0.80 \approx 4.30\text{ W}$ peak load, $\sim 1.80\text{ W}$ nominal idle.

#### Thermal Resistance and Uncoupled Trapped-Air Failure:
* Convective heat transfer coefficient in still indoor air: $h_{\text{conv}} \approx 8.0–10.0\text{ W}/(\text{m}^2\cdot\text{K})$.
* Convective thermal resistance of outer chassis:
  $$R_{\text{th,case-amb}} = \frac{1}{h \cdot A_{\text{case}}} = \frac{1}{10.0 \times 0.0802} \approx 1.25\text{ K/W}$$
* Conduction resistance of 3.0 mm acrylic walls ($k_{\text{acrylic}} = 0.19\text{ W}/(\text{m}\cdot\text{K})$):
  $$R_{\text{th,wall}} = \frac{0.003}{0.19 \times 0.0802} \approx 0.20\text{ K/W}$$
* If the SoC is uncoupled and radiates into stagnant trapped air, air thermal resistance is high ($R_{\text{th,air}} \approx 10.0\text{ K/W}$):
  $$\Delta T_{\text{uncoupled}} = Q \times (R_{\text{th,air}} + R_{\text{th,case-amb}}) = 4.30\text{ W} \times (10.0 + 1.45)\text{ K/W} \approx 49.2^\circ\text{C}$$
  $$T_{\text{SoC,uncoupled}} = T_{\text{amb}} + \Delta T_{\text{uncoupled}} = 35^\circ\text{C} + 49.2^\circ\text{C} = 84.2^\circ\text{C}$$
  *Result*: The BCM2837B0 SoC throttles at $80.0^\circ\text{C}$ and hard-halts at $85.0^\circ\text{C}$. Uncoupled operation in a sealed box guarantees severe thermal throttling.

#### Conduction Thermal Path Solution:
A solid conduction path couples the SoC to an internal aluminum bracket/external heatsink:
* Thermal interface pad ($14 \times 14\text{ mm}$, thickness $1.5\text{ mm}$, $k = 3.0\text{ W}/(\text{m}\cdot\text{K})$):
  $$R_{\text{th,pad}} = \frac{0.0015}{3.0 \times (0.014 \times 0.014)} \approx 2.55\text{ K/W}$$
* Aluminum heatsink bracket ($A_{\text{sink}} \approx 0.015\text{ m}^2$, $R_{\text{th,sink}} \approx 4.50\text{ K/W}$):
* Overall junction-to-ambient thermal resistance:
  $$R_{\text{th,J-A}} = R_{\text{th,junction-case}} + R_{\text{th,pad}} + R_{\text{th,sink}} \approx 2.00 + 2.55 + 4.50 = 9.05\text{ K/W}$$
* Delta-T for Pi SoC ($2.0\text{ W}$ load):
  $$\Delta T_{\text{SoC}} = P_{\text{SoC}} \times R_{\text{th,J-A}} = 2.00\text{ W} \times 9.05\text{ K/W} \approx 18.1^\circ\text{C}$$
* Peak SoC Junction Temperature in $35^\circ\text{C}$ Ambient:
  $$T_{\text{SoC}} = T_{\text{amb}} + \Delta T_{\text{SoC}} + \Delta T_{\text{box-rise}} (6.5^\circ\text{C}) \approx 35^\circ\text{C} + 18.1^\circ\text{C} + 6.5^\circ\text{C} = 59.6^\circ\text{C}–61.2^\circ\text{C}$$

*Empirical Verification*: Confirmed live on Pi Zero 2W in DEC-W29 (WS-7): cold boot nominal idle temperature stabilized at **61.2°C**, maintaining a 18.8°C margin below the 80.0°C thermal throttle limit without cooling fans.
