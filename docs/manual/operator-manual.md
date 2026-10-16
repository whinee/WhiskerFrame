# WhiskerFrame Cyberdeck: Complete Operator Manual

**Document ID:** DOC-MANUAL-OPERATOR-v0.1.0  
**Target Hardware:** WhiskerFrame Cyberdeck (Model: Pi Zero 2W + ESP32 CYD Coprocessor)  
**Standard Display:** Cheap Yellow Display (320x240 LCD over USB-Serial)  
**Primary Grid:** 53 Columns x 30 Rows (Standard Font 1)  
**Operating System:** Raspberry Pi OS 64-bit (Linux kernel 6.6+ on BCM2837B0)  
**Security Level:** Sovereign Air-Gapped / Field Autonomous  

---

## Table of Contents

1. [System Overview & Hardware Topology](#1-system-overview--hardware-topology)
2. [Cold Boot, Login & Lifecycle Sequences](#2-cold-boot-login--lifecycle-sequences)
3. [The Terminal Display Subsystem](#3-the-terminal-display-subsystem)
4. [Input Ergonomics & CardKB Operation](#4-input-ergonomics--cardkb-operation)
5. [Virtual Workspaces & Multi-Session Management](#5-virtual-workspaces--multi-session-management)
6. [Offline Documentation & Knowledge Bases](#6-offline-documentation--knowledge-bases)
7. [Three-Tier Power Profiles & Battery Management](#7-three-tier-power-profiles--battery-management)
8. [Sensory Audio Presets & Overload Mitigation](#8-sensory-audio-presets--overload-mitigation)
9. [Networking, Wi-Fi & Mesh VPN Operations](#9-networking-wi-fi--mesh-vpn-operations)
10. [Storage Operations, BTRFS & Wear Mitigation](#10-storage-operations-btrfs--wear-mitigation)
11. [Public Hands-On Demonstrations: The Hardened Guest Sandbox](#11-public-hands-on-demonstrations-the-hardened-guest-sandbox)
12. [Mechanical Care, Transit & Aviation Compliance](#12-mechanical-care-transit--aviation-compliance)
13. [Hardware Expansion & Modular Sensors](#13-hardware-expansion--modular-sensors)
14. [Appendix A: Complete CardKB & Terminal Chord Reference](#14-appendix-a-complete-cardkb--terminal-chord-reference)
15. [Appendix B: Unified Management CLI Reference (`wf`)](#15-appendix-b-unified-management-cli-reference-wf)
16. [Appendix C: Field Troubleshooting & Emergency Runbook](#16-appendix-c-field-troubleshooting--emergency-runbook)

---

## 1. System Overview & Hardware Topology

The WhiskerFrame Cyberdeck is a sovereign, battery-powered, air-gapped terminal computer engineered for field operations, network security auditing, emergency computing, and offline development.

```text
+-----------------------------------------------------------------+
|                    WHISKERFRAME HARDWARE MAP                    |
+-----------------------------------------------------------------+
| Host Compute:     Raspberry Pi Zero 2W (64-bit ARM Cortex-A53)  |
| Memory Envelope:  512 MB LPDDR2 (~416 MB usable OS RAM)         |
| Terminal Coproc:  ESP32-2432S028R ("CYD") + ILI9341 320x240 LCD |
| Serial Link:      WCH CH340 USB-to-UART (/dev/ttyUSB0 @ 115200) |
| Primary Input:    M5Stack CardKB 50-Key Matrix (I2C-0 @ 0x5F)   |
| Battery Sensor:   Waveshare 3S UPS Module + INA219 (I2C-1 @ 0x41)|
| Battery Cells:    3x 18650 Li-ion Cells (11.1V nominal, 27.75Wh)|
| Persistent Drive: Samsung 860 EVO 250GB SSD (/mnt/250GB-SSD)   |
| Real-Time Clock:  DS3231 I2C RTC (I2C-1 @ 0x68) / fake-hwclock  |
| Wireless Radio:   Broadcom BCM43436 802.11b/g/n (2.4 GHz only)  |
| Host Accounts:    neko (system operator), guest (demo sandbox)  |
+-----------------------------------------------------------------+
```

### Physical Port Complement
The external casework exposes the following ports:
- **12.6V DC Barrel Jack (Center-Positive):** Dedicated battery charging input. Connect exclusively to a regulated 12.6V / 2A Li-ion balance charger. Supports run-while-charging.
- **2x USB-A 2.0 Host Ports:** External USB hub ports for high-power modular peripherals (e.g., LTE modem, RTL-SDR dongle, USB flash drives, external mice/keyboards).
- **1x Mini-HDMI Port:** Secondary auxiliary video output (mirrors standard console if connected).
- **1x Power Toggle Switch:** Master physical power disconnect switch isolating the 3S battery rail.
- **1x Momentary Reset Button:** Hardwired to the Pi Zero 2W `RUN` pads for halt recovery and cold reset.

### The 53-Column Rule
At standard Font 1 (6x8 pixel cell geometry), the CYD screen displays exactly **53 columns by 30 rows**. Every system utility (`wf`, `wifi`, `wiki`, `keys`, `power-profile`, `profile`) wraps output strictly at 53 columns. Commands that emit wide output should be piped through `wf` or formatted with compact flags to avoid unreadable wrapping.

---

## 2. Cold Boot, Login & Lifecycle Sequences

### Cold Boot Sequence
1. **Power Toggle ON:** Slide the main physical switch to ON. The Waveshare 3S UPS rail energizes the Raspberry Pi Zero 2W and the CYD coprocessor simultaneously.
2. **Firmware & Kernel Boot (~25 seconds):**
   - The Pi executes bootcode, mounts the root filesystem from the MicroSD card, mounts the `@data` and `@swap` subvolumes from the 250GB SSD, and initializes systemd services.
   - `battery-monitor.service` starts reading the INA219 sensor on I2C-1 (`0x41`) and writes initial state to `/run/battery_monitor/status.json`.
3. **Bridge Daemon Initialization:**
   - `terminal.service` launches the bridge daemon (`pi/terminal/bridge.py`), exclusively locking `/dev/ttyUSB0` at 115200 baud.
4. **Boot Splash Presentation (3.0 seconds):**
   - The bridge streams a full-screen 320x240 RGB565 binary splash image (`0x05 DRAW_IMAGE`) featuring the WhiskerFrame artwork.
   - The splash image holds on screen for 3.0 seconds.
5. **Display Blank Wipe & Login Presentation:**
   - The screen wipes clean with a full-panel background rectangle in piiiiink blurple (`#18C5`), preventing any splash bleed-through.
   - The interactive login gate renders centered on the screen.

```text
+-----------------------------------------------------+
|                 WhiskerFrame Login                  |
|                                                     |
|   Select user:                                      |
|   > neko                                            |
|     guest                                           |
|                                                     |
|   Password: [ * * * * * * * * * * ]                 |
|                                                     |
|   demo: guest / guest                               |
+-----------------------------------------------------+
```

### Logging In
1. **Select User:** Use the `Down Arrow` or `Up Arrow` keys on CardKB to move the selection cursor between `neko` (operator) and `guest` (demo sandbox).
2. **Press Enter:** The cursor advances into the `Password:` field.
3. **Enter Password:** Type your password. Keystrokes render as masked `*` characters. Backspace deletes previous characters.
   - To return to user selection from an empty password field, press `Backspace` or `Up Arrow`.
4. **Submit:** Press `Enter`. The bridge authenticates credentials via Linux PAM (`simplepam` / `su - <user>`).
5. **Interactive Console:** Upon authentication, the bridge allocates a dedicated pseudo-terminal (PTY) master/slave pair and launches a fullscreen `bash -l` login shell.

### Orderly Shutdown & Reboot
Never flip the master power switch while Linux is running; doing so risks BTRFS filesystem corruption and MicroSD card damage. Always initiate an orderly shutdown:

```bash
# Standard orderly poweroff
systemctl poweroff
# Or shortcut
poweroff

# Standard orderly reboot
systemctl reboot
# Or shortcut
reboot
```

### Goodbye Splashes & Low-Power Display Sleep
During shutdown and reboot, dedicated systemd hooks execute:
- **On Shutdown:** `cyberdeck-goodbye-shutdown.service` executes `pi/bin/goodbye_hook --action shutdown`. It blits a centered 128x128 doodle with the caption `"bai baiii!"`, holds for 3 seconds, and transmits wire opcode `0x06 SLEEP`. The CYD enters ultra-low-power display sleep (backlight off, ESP32 CPU 80 MHz, ~75 mW draw). The operator may then safely slide the physical power switch to OFF.
- **On Reboot:** `cyberdeck-goodbye-reboot.service` executes `pi/bin/goodbye_hook --action reboot`, blitting `"brb :3"` before the system restarts.

---

## 3. The Terminal Display Subsystem

### Display Specifications
- **Controller:** ESP32-2432S028R with ILI9341 320x240 TFT LCD.
- **Interface:** USB-Serial CH340 (`/dev/ttyUSB0`) running at 115200 baud, 8-N-1.
- **Color Depth:** 16-bit RGB565 (5 bits red, 6 bits green, 5 bits blue).
- **Panel Inversion:** Inverted color profile active (`tft.invertDisplay(true)`).

### Typography Engine & Geometry Switching
The WhiskerFrame terminal supports four runtime character geometries. You can dynamically cycle between these font sizes at any time during an active session using the CardKB chord **`Fn + Backspace`** (`Fn + Del` / scancode `0x8B`):

```text
+------+-----------+-----------+---------------------+----------------------+
| Size | Cell (px) | Grid Cols | Grid Rows (Payload) | Operational Use Case |
+------+-----------+-----------+---------------------+----------------------+
|  1   |   6 x 8   |    53     |       30 (29)       | Standard default, max|
|      |           |           |                     | information density  |
|  5   |   8 x 12  |    40     |       20 (19)       | Intermediate high-   |
|      |           |           |                     | legibility coding    |
|  2   |  12 x 16  |    26     |       15 (14)       | High-visibility field|
|      |           |           |                     | operations           |
|  3   |  18 x 24  |    17     |       10 (9)        | Extreme distance /   |
|      |           |           |                     | demo presentation    |
+------+-----------+-----------+---------------------+----------------------+
```

*Note: In all modes, the terminal bridge reserves row 0 (or row 29) for the low-flicker telemetry status line. Resizing automatically updates PTY `winsize` via `TIOCSWINSZ` and sends `SIGWINCH` to running programs.*

### Low-Flicker Telemetry Status Line
Row 0 of the display features a live telemetry bar updated every 2.0 seconds:
```text
[B:92% 12.3V] [T:54.2C] [WS:1] [PWR:ACT] [SENS:OFF]
```
- **`B:xx% xx.xV`**: Battery capacity and bus voltage read from the INA219 sensor.
- **`T:xx.xC`**: SoC core temperature from `/sys/class/thermal/thermal_zone0/temp`.
- **`WS:x`**: Active virtual workspace number (1 through 4).
- **`PWR:xxx`**: Active power profile (`ACT` = Active, `SAV` = Powersave, `AIR` = Airplane).
- **`SENS:xxx`**: Active sensory audio profile (`CLS` = Classroom, `OFF` = Office, `COM` = Commute, `OVL` = Overload Silence).

The status line reads asynchronously from cached telemetry in `/run/battery_monitor/status.json`. It never stalls the serial port or I2C bus and consumes <10 bytes per normal update tick.

### Compact Shell Prompts
To preserve horizontal space on the 53-column screen, standard shell prompts are constrained via `/etc/profile.d/cyd_prompt.sh`:
- Operator prompt (`neko`): `n~ `
- Sandbox prompt (`guest`): `g~ `
- Administrator prompt (`root`): `r# `

---

## 4. Input Ergonomics & CardKB Operation

The primary input device is the integrated **M5Stack CardKB v1.1** (50-key matrix driven by an ATmega328P coprocessor over I2C-0 at address `0x5F`).

```text
+---------------------------------------------------------------+
|                      CARDKB 50-KEY MATRIX                     |
+---+---+---+---+---+---+---+---+---+---+---+---+---+---+---+---+
|Esc| 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 0 | - | = |   BS     |
+---+---+---+---+---+---+---+---+---+---+---+---+---+---+---+---+
|Tab| q | w | e | r | t | y | u | i | o | p | [ | ] |   \      |
+---+---+---+---+---+---+---+---+---+---+---+---+---+---+---+---+
|Fn | a | s | d | f | g | h | j | k | l | ; | ' |     Enter     |
+---+---+---+---+---+---+---+---+---+---+---+---+---+---+---+---+
|Shf| z | x | c | v | b | n | m | , | . | / | Up|Dn |Lft|Rgt    |
+---+---+---+---+---+---+---+---+---+---+---+---+---+---+---+---+
```

### The Sequential Sticky Ctrl Latch
The CardKB v1.1 keyboard lacks a physical `Ctrl` key. To emit standard Unix control signals (`Ctrl-C`, `Ctrl-D`, `Ctrl-Z`, `Ctrl-L`), the terminal bridge implements a sequential sticky Ctrl latch:

1. **Arm the Latch:** Press **`Fn + Tab`** (scancode `0x8C`).
2. **Visual & Hardware Feedback:**
   - The terminal cursor immediately recolors to **bright yellow** (`theme.ansi[11]`).
   - The CardKB onboard **SK6812 NeoPixel LED illuminates yellow** (`RGB 255, 200, 0`).
3. **Press the Target Character:** Press the letter or symbol you wish to control-mask:
   - `Fn+Tab` then `c` $\rightarrow$ **`Ctrl-C`** (`0x03` SIGINT / cancel command)
   - `Fn+Tab` then `d` $\rightarrow$ **`Ctrl-D`** (`0x04` EOF / exit shell)
   - `Fn+Tab` then `z` $\rightarrow$ **`Ctrl-Z`** (`0x1A` SIGTSTP / suspend process)
   - `Fn+Tab` then `l` $\rightarrow$ **`Ctrl-L`** (`0x0C` Clear screen)
   - `Fn+Tab` then `u` $\rightarrow$ **`Ctrl-U`** (`0x15` Clear line)
   - `Fn+Tab` then `[` $\rightarrow$ **`Ctrl-[`** (`0x1B` Escape key)
4. **Automatic Discharge:** Once the target key is pressed, the latch applies the `& 0x1F` bitmask, emits the control byte, and immediately restores the cursor and NeoPixel LED to their normal colors.
5. **Safety Timeouts & Cancellation:**
   - If no valid key is pressed within **3.0 seconds**, the latch automatically times out and cancels.
   - Pressing **`Fn + Tab`** a second time immediately toggles and cancels the latch.
   - Pressing a non-alphanumeric key immediately cancels the latch without emitting corrupted input.

### Quick Key Cheatsheet (`keys`)
To view all keybindings and modifier combinations directly on the terminal, execute:
```bash
keys
# Or via the unified management tool:
wf man kb
```

---

## 5. Virtual Workspaces & Multi-Session Management

The WhiskerFrame terminal bridge incorporates an i3-inspired multi-session workspace manager. Up to four virtual workspaces (`WS1` through `WS4`) run concurrently, each maintaining its own isolated pseudo-terminal, login shell, working directory, and screen buffer, while consuming less than 100 KB total RAM.

### Switching Workspaces via CardKB Chords
You can instantly switch workspaces from anywhere in the terminal using dedicated hardware chords:
- **`Fn + 1`** (`0x81`): Switch to Workspace 1 (`main`)
- **`Fn + 2`** (`0x82`): Switch to Workspace 2
- **`Fn + 3`** (`0x83`): Switch to Workspace 3
- **`Fn + 4`** (`0x84`): Switch to Workspace 4
- **`Fn + n`** (`0xA6`): Switch to the Next workspace (cycles forward)
- **`Fn + p`** (`0x96`): Switch to the Previous workspace (cycles backward)

### Managing Workspaces via CLI (`workspace` / `wf workspace`)
Workspaces can also be managed programmatically from shell scripts or command prompts:

```bash
# List all active workspaces and show current selection
workspace list
# Output:
# === Cyberdeck Workspaces ===
# [*] [1] main (active)
#     [2] net
#     [3] logs
# Total: 3 workspace(s)

# Create a new named workspace
workspace new monitoring

# Switch to a workspace by name or number
workspace switch 2
workspace switch monitoring

# Close and terminate a workspace session
workspace close 3
```

---

## 6. Offline Documentation & Knowledge Bases

The cyberdeck is engineered to function autonomously without internet connectivity.

### The Offline Wiki Helper (`wiki`)
The `wiki` command (`pi/bin/wiki`) formats offline manuals, technical specifications, and documentation into clean, readable 53-column text:

```bash
# View available offline topics
wiki --list

# Read a specific technical topic
wiki arch          # System architecture & hardware specs
wiki keyboard      # CardKB chord & layout guide
wiki battery       # UPS curves, charging & power specs
wiki network       # Wi-Fi, 53-column helper & mesh VPN
wiki security      # Guest sandbox & containment invariants

# Read local Markdown or HTML files with automatic 53-col formatting
wiki /mnt/250GB-SSD/notes/field-report.md
```

### System Manual Pages (`man`)
Standard Linux man pages are installed and accessible:
```bash
man ls
man ip
man btrfs
```

---

## 7. Three-Tier Power Profiles & Battery Management

The power management subsystem (`pi/bin/power-profile` and `wf power`) allows operators to dynamically balance compute performance against battery runtime.

```text
+------------+----------+----------+----------+----------+-----------------------+
|  Profile   | CPU Freq | Display  | Radios   | SSD      | Typical Power & Life  |
+------------+----------+----------+----------+----------+-----------------------+
| ACTIVE     | 1.0 GHz  | 100% PWM | On       | Active   | ~3.2 W (~8.6 hours)   |
| POWERSAVE  | 600 MHz  | Dimmed   | On       | Spun down| ~1.8 W (~15.4 hours)  |
| AIRPLANE   | 600 MHz  | Sleep    | RFKill   | Spun down| ~0.55 W (~50.4 hours) |
+------------+----------+----------+----------+----------+-----------------------+
```

### Changing Power Profiles
```bash
# Check current power profile, battery voltage, and runtime estimate
wf power status

# Set to high-performance active mode
wf power set active

# Set to battery-saving field mode (spins down SSD, throttles CPU to 600 MHz)
wf power set powersave

# Set to deep-idle transit mode (kills radios, puts display to sleep)
wf power set airplane
```

### Battery Telemetry & State of Charge
The Waveshare 3S UPS module uses three 18650 Li-ion cells in series (11.1V nominal, 12.6V fully charged):
- **12.4V – 12.6V:** 90% – 100% (Fully charged)
- **11.5V – 12.0V:** 60% – 80% (Nominal cruising range)
- **10.8V – 11.2V:** 20% – 40% (Low battery range)
- **10.2V – 10.5V:** 5% – 10% (Critical battery range)
- **< 10.0V (<= 5%):** Emergency Cutoff Threshold. `battery-monitor.service` initiates an automatic clean `poweroff` to prevent lithium over-discharge and BTRFS metadata corruption.

### Charging Guidelines
- Connect the supplied **12.6V / 2A balance charger** to the rear barrel jack.
- The deck supports **run-while-charging**; you can continue typing while the pack charges.
- Full charging from 10% to 100% takes approximately 2.5 hours.

---

## 8. Sensory Audio Presets & Overload Mitigation

The cyberdeck incorporates environmental audio profiles (`pi/bin/profile` and `wf profile`) governing buzzer, haptic, and warning signals to suit varying field environments:

```bash
# View active sensory profile
wf profile status

# Classroom Mode: 0% buzzer (silent operation, suitable for lectures/libraries)
wf profile set classroom

# Office Mode: 25% buzzer (quiet confirmation chirps)
wf profile set office

# Commute Mode: 100% buzzer (loud alerts audible over transit noise)
wf profile set commute
```

### Instant Cognitive Sensory Overload Clamp
If alarms, buzzers, or auxiliary indicators become overwhelming or distracting in high-stress situations, execute the instant overload clamp:
```bash
# Instantly clamp buzzers and alerts to 0% silence
wf profile overload on
# Or:
wf profile silence

# Toggle overload mode off when ready
wf profile overload off
```

---

## 9. Networking, Wi-Fi & Mesh VPN Operations

### The 53-Column Wi-Fi Manager (`wifi`)
Standard network tools (`nmcli`, `ip`) produce wide outputs that overflow the 53-column CYD display. Always use the built-in `wifi` command (`pi/bin/wifi` or `wf wifi`):

```bash
# Check Wi-Fi radio status, current SSID, IP address, and signal strength
wifi status

# Scan for available Wi-Fi access points (shows signal bars & 2.4/5GHz band)
wifi scan

# Join a known network by SSID or by scan list number
wifi join 1 -p "SecretPassword"
wifi join "HomeNet" -p "SecretPassword"

# Join a hidden network
wifi join "StealthNet" -p "SecretPassword" --hidden

# Forget a stored network profile
wifi forget "OldNetwork"
```

### Captive Portal Detection
When joining public Wi-Fi networks (cafes, transit hubs, university campuses), `wifi status` automatically detects captive portals and displays an alert:
```text
[!] Captive Portal Detected!
Run 'w3m http://neverssl.com' to authenticate.
```
Use the lightweight text-mode browser `w3m` to navigate and submit portal landing pages directly from the CYD console.

### Wi-Fi Cold Boot Persistence
The network subsystem enforces immediate Wi-Fi radio availability upon cold boot:
- `/etc/modprobe.d/rfkill_default.conf` sets `options rfkill default_state=1` (unblocked).
- Regulatory domain is pinned to `PH` (`cfg80211.ieee80211_regdom=PH`).
- Known network profiles are assigned connection priority `100`, reconnecting within 2.0 seconds of boot.

### The 3-Tier Self-Healing Network Watchdog
If Wi-Fi connectivity drops, `/usr/local/bin/cyberdeck-net-heal.sh` automatically executes recovery tiers:
- **Tier 1 (Every 30s):** Unblocks rfkill and issues `nmcli device wifi connect`.
- **Tier 2 (After 5 minutes of failure):** Restarts `NetworkManager.service`.
- **Tier 3 (After 15 minutes of failure):** Unloads and reloads the Broadcom kernel module (`modprobe -r brcmfmac && modprobe brcmfmac`).
- *System Invariant:* The network watchdog **never** reboots the cyberdeck.

### NetBird Sovereign Mesh VPN
The deck includes a native NetBird client connecting to the operator's self-hosted coordination server (`100.86.0.0/16`). Once Wi-Fi is established, the deck securely meshes with workstation nodes, permitting peer-to-peer SSH access without opening public firewall ports.

---

## 10. Storage Operations, BTRFS & Wear Mitigation

### Storage Architecture
- **MicroSD Card (Root Filesystem):** Hosts the OS kernel, libraries, and base system binaries. Protected against write wear via `log2ram` (32MB RAM ring buffer) and redirection of persistent systemd logs.
- **Samsung 860 EVO 250GB SSD:** Primary high-speed persistent storage formatted with **BTRFS** (UUID: `98bb87d2-7128-470e-91d5-9e117df2ab1a`):
  - **`@data` Subvolume:** Mounted at `/mnt/250GB-SSD` with `noatime,compress=zstd:3,nofail,x-systemd.device-timeout=5s`.
  - **`@swap` Subvolume:** Hosts an uncompressed `nodatacow` 2GB swapfile at `/mnt/250GB-SSD/swapfile` configured with priority `100`.

### Safe Media Inspection
```bash
# Check SSD mount status and BTRFS disk utilization
btrfs filesystem usage /mnt/250GB-SSD

# Inspect active swap allocation
swapon --show
```

### Automated Backup Synchronization (`scripts/backup-sync.sh`)
To protect project files without draining battery on cellular links, the backup synchronization tool runs strictly when connected to trusted networks:
```bash
# Manually trigger backup synchronization to the homelab server
/opt/cyd-display-link/scripts/backup-sync.sh
```

---

## 11. Public Hands-On Demonstrations: The Hardened Guest Sandbox

The WhiskerFrame Cyberdeck is designed to be handed to strangers, conference attendees, and peers for public hands-on interaction without compromising operator security.

### The Guest Account (`guest` / `guest`)
The system provides a dedicated `guest` user account engineered under the assumption of **adversarial code execution**:

1. **Authentication Gate:** The `guest` user is permitted to log in **only** through the physical CYD terminal PAM service. The account is explicitly blocked in SSH (`DenyUsers guest`), blocked from `su`, and blocked on physical TTY consoles.
2. **Ephemeral In-Memory Home Directory:** `/home/guest` resides on an **8MB tmpfs** RAM disk. When the guest logs out (or times out), PAM triggers a clean wipe and re-populates the directory from `/etc/skel`. No files saved by the guest persist across logins.
3. **5-Second Process Reaper:** The background service `cyberdeck-guest-reaper.service` scans every second. Any process owned by UID `guest` (other than the interactive login shell `bash -l`) that runs for more than **5.0 seconds** is immediately terminated with `SIGKILL`. Fork bombs and background miners are neutralized instantly.
4. **Kernel-Level Network Blackhole:** Kernel `nftables` rules drop all outbound network packets from UID `guest` (`skuid "guest" counter drop`). The guest cannot communicate with loopback (`127.0.0.1`), local LAN nodes, or the public Internet.
5. **Filesystem Isolation:** The guest account has zero read access to `/home/neko`, `/root`, `/mnt/250GB-SSD`, or system network secrets.

### Demo Artwork Display (`wf demo art`)
To demonstrate the coprocessor's 16-bit color rendering capabilities to viewers, run:
```bash
wf demo art
```
This blits full-color 320x240 illustrations by artist Cess to the CYD display. When the demonstration ends, pressing any key restores the fullscreen terminal grid without corruption.

---

## 12. Mechanical Care, Transit & Aviation Compliance

### Physical Envelope & Ergonomics
- **Dimensions:** 110 mm x 180 mm x 70 mm (fits cleanly within an A5 perimeter).
- **Two-Thumb Typing Posture:** Hold the cyberdeck between both palms with fingers wrapped around the rubberized side bumpers. Use both thumbs to actuate the CardKB switches.
- **Drop Bumpers & Shock Mounts:** The chassis incorporates +10 mm exterior silicone corner bumpers and internal silicone dampeners isolating the SATA SSD.

### Passive Thermal Management
The cyberdeck has **no cooling fans**. Heat generated by the BCM2837B0 SoC conducts through a high-efficiency thermal pad ($k \ge 3.0\text{ W}/(\text{m}\cdot\text{K})$) to an external aluminum heatsink plate.
- **Operating Limit:** Keep the exterior heatsink plate unobstructed during heavy compilation.
- **Thermal Thresholds:** Nominal operating temperature is 45°C–60°C. If temperature reaches 75°C, the terminal status bar displays a warning. At 80°C, the system throttles CPU frequency to 600 MHz.

### Aviation Carry-On Compliance
The cyberdeck's 3S 18650 lithium battery pack provides **27.75 Wh nominal energy**, well below the **100 Wh ceiling** enforced by the FAA, ICAO, and CAAP for passenger aircraft carry-on baggage.
- **Transit Stance:** Always place the physical power switch in the **OFF** position before stowing the cyberdeck in carry-on luggage.
- Never pack lithium battery-powered devices in checked baggage.

---

## 13. Hardware Expansion & Modular Sensors

### The Three-Tier Bus Architecture
- **Small Bus (I2C / UART):** Dedicated to onboard telemetry and low-speed sensors. Features TVS transient protection and 100 mA PTC resettable fuses.
- **Medium Bus (USB 2.0):** External USB hub for high-power devices (LTE modems, SDR receivers).
- **Big Bus (PCIe):** Deferred to future compute upgrades.

### STEMMA QT / Qwiic Modular Sensor Header
The cyberdeck exposes a 4-pin JST-SH (1.0 mm) STEMMA QT / Qwiic expansion port connected to **I2C-1**:
- **Pin 1 (Black):** Ground (GND)
- **Pin 2 (Red):** 3.3V Power (100 mA fused)
- **Pin 3 (Blue):** I2C SDA (GPIO 2 / Pin 3)
- **Pin 4 (Yellow):** I2C SCL (GPIO 3 / Pin 5)

Field sensors (environmental temperature/humidity, GPS, magnetometers) plugged into this port are instantly accessible on bus `/dev/i2c-1`.

---

## 14. Appendix A: Complete CardKB & Terminal Chord Reference

```text
+-----------------------+------------+---------------------------------------+
| Key / Chord           | Scancode   | Function / Action                     |
+-----------------------+------------+---------------------------------------+
| Fn + Tab              | 0x8C (140) | Arm Sequential Sticky Ctrl Latch      |
|                       |            | (Recolors cursor & NeoPixel YELLOW)   |
| Fn + Tab (while armed)| 0x8C (140) | Cancel / Disarm Sticky Ctrl Latch     |
| Fn + Backspace (Del)  | 0x8B (139) | Cycle Font Geometry (53x30 -> 40x20   |
|                       |            | -> 26x15 -> 17x10 -> 53x30)           |
| Fn + 1                | 0x81 (129) | Switch to Workspace 1 (main)          |
| Fn + 2                | 0x82 (130) | Switch to Workspace 2                 |
| Fn + 3                | 0x83 (131) | Switch to Workspace 3                 |
| Fn + 4                | 0x84 (132) | Switch to Workspace 4                 |
| Fn + n                | 0xA6 (166) | Switch to Next Workspace              |
| Fn + p                | 0x96 (150) | Switch to Previous Workspace          |
| Up Arrow              | 0xB5 (181) | Shell History Up / Cursor Up          |
| Down Arrow            | 0xB6 (182) | Shell History Down / Cursor Down      |
| Left Arrow            | 0xB4 (180) | Cursor Left                           |
| Right Arrow           | 0xB7 (183) | Cursor Right                          |
| Esc                   | 0x1B (27)  | Terminal Escape / Vim Normal Mode     |
| Tab                   | 0x09 (9)   | Command / File Path Auto-Completion   |
| Enter                 | 0x0D (13)  | Execute Command / Newline             |
| Backspace             | 0x08 (8)   | Delete Previous Character             |
+-----------------------+------------+---------------------------------------+
```

---

## 15. Appendix B: Unified Management CLI Reference (`wf`)

The `wf` command (`pi/bin/wf`) is the primary operational management interface:

```text
Usage: wf <command> [arguments]

Commands:
  wf help [cmd]              Show command reference or detailed command help
  wf man [topic]             View offline documentation (kb, wifi, demo, power)
  wf wifi <subcommand>       Manage Wi-Fi network (status, scan, join, forget)
  wf power <subcommand>      Manage power profiles (status, set active|powersave|airplane)
  wf profile <subcommand>    Sensory audio profiles (status, set classroom|office|commute)
  wf profile overload [on]   Instant cognitive sensory overload silence clamp
  wf workspace <subcommand>  Manage multi-session workspaces (list, switch, new, close)
  wf demo art                Display demo color artwork on CYD display
```

---

## 16. Appendix C: Field Troubleshooting & Emergency Runbook

### Problem 1: Screen is Frozen or Blank
- **Cause A: Terminal service crashed or stopped.**
  - *Fix:* Connect via SSH or switch workspaces:
    ```bash
    sudo systemctl restart terminal
    ```
- **Cause B: Display is in Airplane sleep mode.**
  - *Fix:* Press any key on CardKB or wake via CLI:
    ```bash
    wf power set active
    ```
- **Cause C: Hardware watchdog triggered.**
  - *Fix:* If the host froze >60s, the ESP32 renders a warning banner. Press the momentary `RUN` button on the chassis to hard-reset the Pi Zero 2W.

### Problem 2: CardKB Keys Produce No Characters
- **Cause A: I2C bus stall.**
  - *Fix:* The CardKB reader automatically re-opens the bus on error. If frozen, verify address `0x5F` is visible:
    ```bash
    i2cdetect -y 0
    ```
- **Cause B: Sticky Ctrl latch accidentally armed.**
  - *Fix:* Check if the NeoPixel LED is glowing yellow. If so, press `Fn + Tab` once to cancel the latch.

### Problem 3: Battery Level Dropping Rapidly
- **Cause:** System is running in `ACTIVE` profile under heavy CPU load with external USB peripherals attached.
- **Fix:** Switch immediately to `powersave` profile:
  ```bash
  wf power set powersave
  ```
  Unplug external high-power USB devices (LTE modem, SDR).

### Problem 4: Cannot Connect to Wi-Fi
- **Cause A: Radio blocked by rfkill.**
  - *Fix:* Run `sudo rfkill unblock wifi`.
- **Cause B: Access point is 5 GHz only.**
  - *Fix:* The internal Broadcom BCM43436 radio supports **2.4 GHz only**. Connect a dual-band USB Wi-Fi dongle or reconfigure your mobile hotspot to emit a 2.4 GHz band.
