# Whiskerframe Cyberdeck Demo Day Field Guide & Stage Manual

**Event:** DICT HACK4GOV 5 Stage Demo  
**Date:** October 17, 2026  
**Target Hardware:** Whiskerframe Cyberdeck v0.1 (Raspberry Pi Zero 2W + Cheap Yellow Display + CardKB v1.1 + 3S UPS Module)  
**Document ID:** DOC-DEMO-DAY-2026-10-17  

---

## 1. 3-Minute Stage Demo Script

### Timeline Overview
* **0:00 - 0:30:** The Hook & Hardware Tour
* **0:30 - 2:00:** Live Demo Actions
* **2:00 - 2:45:** Resilience & Multi-Tenant Containment
* **2:45 - 3:00:** Closing & Sovereign Edge Computing Vision

---

### [0:00 - 0:30] The Hook & Hardware Tour

#### Spoken Script
> "Judges, mentors, and guests: in an era of centralized cloud dependencies and fragile connectivity, what does sovereign personal computing actually look like?
>
> This is the **Whiskerframe Cyberdeck v0.1**. It is not an emulation or a toy shell. It is a fully independent, air-gapped, battery-powered sovereign computing terminal engineered for field operations, disaster response, and offline security analysis.
>
> Let's look at the hardware:
> 1. **Form Factor & Custom Chassis:** Tailored handheld enclosure housing a 64-bit quad-core Raspberry Pi Zero 2W.
> 2. **Display Architecture:** A 320x240 RGB565 Cheap Yellow Display (CYD) driven by an onboard ESP32 coprocessor over high-speed UART, bypassing the Linux framebuffer completely.
> 3. **Input Interface:** A 50-key M5Stack CardKB matrix keyboard communicating over hardware I2C bus 0 at address `0x5F`.
> 4. **Power System:** An unswitched 5V UPS rail energized by a 3S 18650 Li-ion battery pack (~35 Wh capacity) delivering 15 to 19 hours of continuous runtime, monitored via an I2C INA219 telemetry sensor."

#### Physical Actions
* Hold cyberdeck up with both hands, tilted toward judges.
* Point to the CYD display and CardKB keyboard.
* Point out the rear ventilation ports and physical toggle power switch.

---

### [0:30 - 2:00] Live Demo Actions

#### 1. Boot Hold & Login Screen (0:30 - 0:45)
* **Action:** Toggle power switch ON (or awaken from screen sleep).
* **Observe:** The 320x240 full-color RGB565 boot splash holds on screen for exactly 3.0 seconds, then cleanly transitions to the custom login gate.
* **Point out:** The piiiiink retro accessibility theme, user selector showing `neko` (sysadmin) and `guest` (sandbox), and bottom demo prompt hint (`demo: guest / guest`).
* **Spoken:**
  > "Notice the boot sequence: instant hardware splash, clean transition to our login gate, and clear user delineation. We provide two isolated worlds: 'neko' for the deck operator, and 'guest' for untrusted third parties."

#### 2. PTY Session Fork & Compact Prompts (0:45 - 1:00)
* **Action:** Press `Down` or `Tab` on CardKB to highlight `guest`. Press `Enter`.
* **Action:** Type `guest` for the password (characters masked with `*`). Press `Enter`.
* **Observe:** Instant PTY fork into an unprivileged `su - guest` session. The prompt appears immediately as `g~ `.
* **Spoken:**
  > "Upon login, the terminal bridge forks a dedicated PTY session. Notice our compact 3-character shell prompt: `g~ ` for guest, or `n~ ` for neko. On a 53-column display, standard Linux prompt strings like `guest@whiskerdeck:~$ ` eat 20 columns before you type a single character. Our compact prompts preserve every precious horizontal column."

#### 3. CardKB Sticky Ctrl Latch & NeoPixel Visual Feedback (1:00 - 1:20)
* **Action:** Press `Fn + Tab` (`0x8C`).
* **Observe:**
  * The CardKB onboard NeoPixel LED illuminates **bright yellow** via I2C opcode `0x13 [255, 200, 0]`.
  * The screen cursor cell immediately recolors to bright yellow (`#ffe08a` / ANSI 11).
* **Action:** Press `c`.
* **Observe:** The latch resolves `c` into `0x03` (`Ctrl-C`), cancelling any running input. The NeoPixel turns off, and cursor background reverts to standard cyan (`#2dd8ff`).
* **Spoken:**
  > "The CardKB keyboard lacks a physical Control key. Instead of clumsy workarounds, we engineered a state machine with hardware-synchronized feedback: pressing `Fn+Tab` latches Ctrl for exactly one key. The CardKB NeoPixel illuminates yellow, the screen cursor recolors to bright yellow, and pressing any letter masks it to standard ASCII control codes like Ctrl-C, Ctrl-D, or Ctrl-Z. It automatically cancels after 3 seconds or on a repeat toggle."

#### 4. Dynamic Display Geometry Cycling (1:20 - 1:35)
* **Action:** Press `Fn + Backspace` (top-right key, labeled `del` on CardKB, scancode `0x8B`).
* **Observe:** Terminal switches instantly from Font 2 (26x15, 12x16 px) to Font 1 (53x30, 6x8 px). Press again to show Font 3 (17x10, 18x24 px), then return to Font 1.
* **Spoken:**
  > "Pressing `Fn+Backspace` cycles through our display geometries on the fly: 53x30 for full data density, 26x15 for standard readability, and 17x10 for large-format presentations. The PTY receives a live SIGWINCH signal and reflows instantly."

#### 5. Deck Telemetry Banner & Wi-Fi Management (1:35 - 1:50)
* **Action:** Type `demo` and press `Enter`.
* **Observe:** The 53-column demo banner prints live uptime, INA219 battery voltage and percentage, SoC thermals, available RAM, and active security boundaries.
* **Action:** Type `wifi status` and press `Enter`.
* **Observe:** The 53-column Wi-Fi status shows interface `wlan0`, connection state, SSID, signal quality, and IP address without line-wrapping.
* **Spoken:**
  > "Running `demo` displays live telemetry: battery voltage, SoC temperature, and memory constraints. All our CLI utilities—including our custom NetworkManager wrapper `wifi`—strictly enforce a 53-column boundary so output never wraps or corrupts screen layout."

#### 6. Sovereign Offline Knowledge Retrieval (1:50 - 2:00)
* **Action:** Type `wiki ls` and press `Enter`. Type `wiki search "security"` and press `Enter`.
* **Observe:** Instant 53-column formatted documentation without external network access.
* **Spoken:**
  > "Even with radios killed, the deck carries full technical documentation, manual pages, and offline encyclopedic references accessible through our `wiki` helper."

---

### [2:00 - 2:45] Resilience & Multi-Tenant Containment

#### Spoken Script
> "Now for the critical question: how do you let an untrusted stranger hold your computer without compromising your credentials or the host?
>
> We implemented four strict kernel-level containment layers:
>
> 1. **Ephemeral 8MB tmpfs Home:** Guest files exist purely in RAM (`size=8M,nodev,nosuid`). The moment the session closes, the PAM `close_session` hook runs `guest-session-cleanup.sh`, completely purging the directory.
> 2. **Kernel Network Egress Drop:** An `nftables` netfilter rule matches `meta skuid "guest"` and drops 100% of outbound traffic. The guest cannot ping, query DNS, or touch local subnet services. Let's demonstrate: `ping 1.1.1.1` -> Operation not permitted.
> 3. **5-Second Process Reaper:** Runaway background forks, crypto-miners, or infinite loops are terminated: our systemd reaper service scans the guest cgroup every second and sends `SIGKILL` to any process running longer than 5 seconds.
> 4. **Resource Ceilings & Boundary Permissions:** 64MB memory limit, 50% CPU quota, and strict `0700` permissions on `/home/neko`, `/root`, and `/etc/NetworkManager`.
>
> Finally, power resilience: watch what happens on shutdown."

#### Physical Actions & Graceful Shutdown
* In the guest shell, type `exit`.
* Select `neko`, log in, and execute:
  ```bash
  sudo poweroff
  ```
* **Observe:**
  1. The bridge hands off cleanly to `pi/bin/goodbye_hook`.
  2. CYD display clears to blurple (`#191a28`).
  3. Centered 128x128 pixel doodle renders with `"bai baiii!"` subtitle.
  4. Frame holds for 3.5 seconds.
  5. Screen wipes black, and the ESP32 receives opcode `0x06` (`SLEEP`), pulling ILI9341 backlight GPIO 21 LOW and issuing display sleep commands to draw 0 mA.

---

### [2:45 - 3:00] Closing & Sovereign Edge Computing Vision

#### Spoken Script
> "To close: the Whiskerframe Cyberdeck represents our vision for sovereign edge computing.
>
> It does not require AWS, Azure, or an internet uplink to function. It is repairable, auditable, physically inspectable, and secure against physical multi-tenant handover. In an emergency, during a disaster, or on a critical field deployment, this machine stays functional when everything else goes dark.
>
> Thank you, and we welcome your questions!"

---

## 2. Printable 53-Column Key Cheat Sheet

*Format Target:* Exactly <= 53 characters wide. Suitable for raw terminal display (`cat` / `pi/bin/keys`), CYD Font 1 display, and pocket card printing.

```text
=== CARDKB CHEATSHEET (50-Key I2C 0x5F) ===

STICKY CTRL LATCH (Fn+Tab):
  Fn+Tab        Arm sticky Ctrl for NEXT single key
                NeoPixel turns YELLOW [255, 200, 0]
                Cursor cell highlights in bright
                yellow (#ffe08a / theme.ansi[11])
                3.0s timeout auto-cancels latch
  Fn+Tab again  Toggle cancel (LED & cursor reset)
  Non-letter    Cancels latch and emits key as-is

COMMON CTRL CHORDS:
  Fn+Tab c      Ctrl-C (SIGINT / kill hung process)
  Fn+Tab d      Ctrl-D (EOF / exit shell session)
  Fn+Tab z      Ctrl-Z (SIGTSTP / suspend job)
  Fn+Tab l      Ctrl-L (clear terminal screen)
  Fn+Tab u      Ctrl-U (clear current line)
  Fn+Tab [      Ctrl-[ (Escape)
  Fn+Tab \      Ctrl-\ (SIGQUIT / core dump kill)
  Fn+Tab space  Ctrl-Space (NUL byte / 0x00)

DISPLAY GEOMETRY CHORD (Fn+Backspace):
  Fn+Backspace  Cycle font & grid geometry
                (top-right key, labeled 'del')
                Font 1: 53x30 (6x8 px, full status)
                Font 2: 26x15 (12x16 px, default UI)
                Font 3: 17x10 (18x24 px, large type)

TERMINAL NAVIGATION:
  Up / Down     History navigation (VT100 \x1b[A/B)
  Left / Right  Line edit cursor move (\x1b[D/C)
  Tab           Shell path/command auto-completion
  Del           Backspace (\x08, delete char left)
  Shift+Del     ASCII DEL (\x7F)
  Enter         Carriage return / execute (\r)
  Esc           Cancel / reset password buffer

MODIFIER LAYERS:
  Sym           Single ASCII punctuation layer
  Aa / Shift    Uppercase alphabetic characters
  Fn            Extended functions / custom chords

EMERGENCY RESCUE SHORTCUTS:
  Fn+Tab c      Interrupt stuck process / script
  Fn+Tab d      Clean logout from guest / subshell
  Fn+Backspace  Enlarge font if unreadable on stage
  Esc / Left    Reset password field on login gate
```

---

## 3. Failure Playbooks

Structured operational procedures for stage incidents.

---

### Playbook A: Frozen CYD Display / UI Hang

#### Symptoms
* Terminal screen stops updating.
* Cursor stops blinking.
* Key presses on CardKB do not echo on the CYD screen.

#### Immediate Action
1. Look at the Raspberry Pi Zero 2W **ACT LED** through chassis vent:
   * **ACT LED blinks intermittently:** Pi kernel is alive. The hang is isolated to the serial bridge or UART link.
   * **ACT LED solid ON or completely unblinking:** Pi SoC lockup or kernel panic.
2. If ACT LED is active, attempt soft reset from CardKB:
   * Press `Fn + Tab` then `c` (interrupt stuck foreground process).
   * Press `Fn + Backspace` (force display geometry rebuild and full grid repaint).
3. If connected to venue Wi-Fi / hotspot, execute SSH rescue from laptop:
   ```bash
   ssh neko@10.0.0.212 "sudo systemctl restart terminal.service"
   ```

#### Root Cause
* High-baud UART buffer overrun on `/dev/ttyAMA0` (921600 baud desync).
* ESP32 firmware frame parser stalled on incomplete frame packet.
* Memory exhaustion on 512MB RAM ceiling (416MB usable) causing swapping thrash.

#### Rollback / Workaround
* **Watchdog Auto-Recovery:** If Pi kernel is completely frozen, hardware BCM2835 watchdog triggers a full hardware reboot within 15 seconds.
* **Hard Power Toggle:** If watchdog is disabled or unresponsive, toggle physical power switch OFF, wait 3 seconds, toggle ON.
* **Zero-Infrastructure Console:** Connect micro-USB cable from laptop to Pi USB OTG port:
  ```bash
  screen /dev/ttyACM0 115200
  ```

---

### Playbook B: CardKB Input Dead / Keys Unresponsive

#### Symptoms
* Key presses do not register.
* `Fn + Tab` does not light up the CardKB NeoPixel.
* Terminal remains interactive via SSH, but local input is ignored.

#### Immediate Action
1. Inspect the 4-pin STEMMA QT / Grove I2C cable connector on CardKB:
   * Gently press connector into the socket to reseat loose pins.
2. Test if Sticky Ctrl latch is in a desynced state:
   * Press `Fn + Tab` twice to toggle latch clear.
   * Wait 3.5 seconds for the hardware latch timeout to disarm.
3. Test if Shift/Sym layer is stuck in CardKB MCU:
   * Press `Sym`, then press `Aa` twice to reset keyboard microcontroller state.

#### Root Cause
* I2C bus lockup: SDA line held low by CardKB slave microcontroller (`0x5F`).
* Kernel `i2c_bcm2835` controller driver entered timeout state.
* CardKB microcontroller brownout caused by mechanical cable flex.

#### Rollback / Workaround
* **Bus Scan / Wakeup:** From SSH or remote console, probe I2C bus 0:
  ```bash
  sudo i2cdetect -y 0
  ```
* **Module Reload:**
  ```bash
  sudo modprobe -r i2c_bcm2835 && sudo modprobe i2c_bcm2835
  sudo systemctl restart terminal.service
  ```
* **Hardware Re-plug:** Unplug CardKB Grove cable, count to 2, reconnect. `bridge.py` poll loop will catch `OSError: [Errno 121] Remote I/O error` and automatically resume once the device responds at `0x5F`.

---

### Playbook C: Login Failure / Lockout

#### Symptoms
* Red `login failed` message appears below password prompt.
* Password `guest` or `neko` rejected repeatedly.
* User locked out by PAM authentication security policy.

#### Immediate Action
1. Press `Esc` or `Left` arrow on CardKB to wipe the password buffer and return to user selection.
2. Verify Shift / CapsLock state:
   * Press `Aa` once or twice to ensure lowercase input.
   * Re-enter `guest` deliberately, observing character asterisks.
3. If locked out, switch to fallback user `neko`.

#### Root Cause
* PAM `faillock` module triggered by > 3 incorrect password attempts on CardKB (caused by thumb typing errors on small keys).
* CardKB modifier state stuck in uppercase or punctuation mode.

#### Rollback / Workaround
* **Reset PAM Faillock via SSH / Console:**
  ```bash
  sudo faillock --user guest --reset
  sudo faillock --user neko --reset
  ```
* **Emergency Sudo Rule Verification:**
  The `neko` account has full sudo privileges (`/etc/sudoers.d/010_neko-nopasswd` or standard wheel group).
* **Direct Root Shell via USB Gadget:**
  Connect USB cable to laptop and log in directly through CDC ACM serial console (`/dev/ttyACM0`).

---

### Playbook D: Wi-Fi Dropped / Venue Client Isolation

#### Symptoms
* `wifi status` displays `disconnected`.
* Cyberdeck cannot be reached via SSH from developer laptop.
* Ping fails; venue network enables AP Client Isolation blocking P2P traffic.

#### Immediate Action
1. Run local Wi-Fi diagnosis directly on cyberdeck screen:
   ```bash
   wifi status
   wifi scan
   ```
2. Enable personal Android 2.4 GHz hotspot:
   * Hotspot SSID: `Redmi Note 12`
   * Channel: `1` (2412 MHz)
   * Band: `2.4 GHz` (or toggle "Maximize compatibility" ON)
3. Join hotspot from cyberdeck terminal:
   ```bash
   wifi join "Redmi Note 12"
   ```

#### Root Cause
* **5 GHz Invisibility:** Raspberry Pi Zero 2W BCM43436 wireless chip is strictly 2.4 GHz only (Channels 1-13). It physically cannot see 5 GHz networks.
* **Venue AP Client Isolation:** Hotel/conference Wi-Fi drops Layer 2 station-to-station packets. Devices get IP addresses but cannot talk to each other.
* **Captive Portal:** Headless browserless OS cannot pass venue splash pages.

#### Rollback / Workaround
* **Workaround 1 (NetBird Mesh VPN):** Outbound UDP tunnel to STUN/TURN relays bypasses local subnet client isolation:
  ```bash
  ssh neko@100.86.1.20
  ```
* **Workaround 2 (USB Tethering via adb-safe):** Connect phone to laptop, run restricted wrapper:
  ```bash
  ~/.local/bin/adb-safe shell svc wifi enable
  ```
* **Workaround 3 (100% Offline Fallback):** The cyberdeck does not need internet. Demo scripts, offline `wiki`, and telemetry run completely offline without an IP address.

---

### Playbook E: Low Battery / Power Emergency

#### Symptoms
* Battery voltage reported by `demo` drops below 11.1V.
* `cat /run/battery_monitor/status.json` reports `"status": "Discharging"` and capacity < 15%.
* System journal logs `battery_monitor: WARNING low battery`.

#### Immediate Action
1. **Immediately attach auxiliary USB-C power bank** or 12.6V DC barrel charger to the cyberdeck power input.
2. The internal UPS rail is **unswitched 5V**: external power can be attached live without interrupting the Pi, resetting USB devices, or rebooting.

#### Telemetry Thresholds
| State | Pack Voltage | Percent | Action Required |
| :--- | :--- | :--- | :--- |
| **Float / 100%** | **12.4V - 12.6V** | 95-100% | Normal operation; charge current drops to 0 mA. |
| **Nominal Operating** | **11.5V - 12.3V** | 30-90% | Safe for multi-hour stage presentations. |
| **Warning Threshold** | **11.1V** | **~15%** | Attach external power bank immediately. |
| **Critical Cutoff** | **10.5V** | **~5%** | Graceful shutdown imminent (`auto_shutdown` arm). |
| **BMS Hardware Cutoff** | **10.2V** | 0% | Battery protection circuit cuts raw pack rail. |

#### Root Cause
* Continuous display backlight draw (~80 mA), Pi Zero 2W active CPU draw (~120-180 mA), and Wi-Fi transmission pulling battery down after extended unplugged standby.

#### Rollback / Workaround
* Connect external USB-C PD battery bank (minimum 5V 2.4A or 9V PD).
* If battery reaches 10.5V and no charger is available, execute graceful shutdown to preserve ext4 filesystem integrity:
  ```bash
  sudo poweroff
  ```
* Do NOT allow the battery to hit 10.2V BMS hard cutoff while writing to disk.

---

### Playbook F: Thermal Throttle / Overheat

#### Symptoms
* SoC temperature exceeds 70°C.
* `vcgencmd get_throttled` returns non-zero (`0x20000` or `0x80000`).
* Visible typing latency or slowed command execution.

#### Immediate Action
1. Inspect chassis vents: ensure cyberdeck is sitting on a hard, flat surface (not soft cloth, notebook, or leg).
2. Check live thermal reading:
   ```bash
   cat /sys/class/thermal/thermal_zone0/temp
   # Divide value by 1000 for degrees Celsius
   ```
3. Terminate any heavy computational tasks or looping scripts:
   ```bash
   killall -9 python3 2>/dev/null
   ```

#### Thermal Thresholds
* **< 62°C:** Normal fanless idle temperature.
* **70°C:** Throttling warning threshold. BCM2710A1 throttles ARM cores from 1000 MHz down to 600 MHz.
* **75°C:** Hard safety limit. Prepare for thermal cooldown or shutdown.
* **80°C:** Hardware automatic thermal trip.

#### Root Cause
* Compact fanless 3D-printed enclosure under ambient stage lighting.
* Uncontrolled loop or compilation task saturating all 4 Cortex-A53 cores.

#### Rollback / Workaround
* Allow 2 minutes of idle time; CPU temperature drops ~5°C within 60 seconds of load cessation.
* The guest containment cgroup limits CPU quota to 50%, preventing untrusted guest users from overheating the deck.

---

## 4. Pre-Departure Checklist

Complete this checklist on the morning of October 17, 2026, before leaving for the DICT HACK4GOV venue.

### Hardware & Gear Bag
- [ ] **Whiskerframe Cyberdeck Unit:** Cleaned, chassis screws snug, screen free of smudges.
- [ ] **Battery Charge Level:** 3S battery pack charged to float voltage (>= 12.4V).
- [ ] **Auxiliary Power:** 10,000+ mAh USB-C PD power bank (100% charged).
- [ ] **AC Charger:** 12.6V 2A DC barrel charger + wall plug adapter.
- [ ] **Cables:**
  - 1x USB-C to USB-C cable (power bank tethering).
  - 1x USB-A to micro-USB data cable (for direct laptop USB OTG serial rescue).
  - 1x USB-C to micro-USB cable.
- [ ] **Spare MicroSD Card:** Pre-imaged with verified golden backup image, stored in antistatic case.
- [ ] **Android Phone (Redmi Note 12):**
  - Hotspot verified on 2.4 GHz Channel 1 (2412 MHz).
  - "Maximize compatibility" / 2.4 GHz AP Band confirmed ON.
  - WPA2 passphrase memorized and tested.
- [ ] **Printed Pocket Card:** 53-column cheatsheet printed and slipped into deck travel pouch.

---

### Golden Image Verification
* **Location on Cyberdeck SSD:**
  `/mnt/250GB-SSD/backup/2026-10-14/sdcard-mmcblk0.img.zst`
* **Size:** 59.5 GB raw block stream compressed to 2.59 GiB with `zstd -T1 -1`.
* **Checksum Verification Command:**
  ```bash
  ssh neko@10.0.0.212 "cd /mnt/250GB-SSD/backup/2026-10-14 && sha256sum -c SHA256SUMS"
  ```
  *Expected Output:*
  ```text
  boot-firmware.tar.gz: OK
  mmcblk0-partition-table.sfdisk: OK
  sdcard-mmcblk0.img.zst: OK
  ```
* **Developer Host Offloaded Backup Location:**
  Sync from cyberdeck to workstation before packing:
  ```bash
  rsync -avz --bwlimit=5000 neko@10.0.0.212:/mnt/250GB-SSD/backup/2026-10-14/ ~/cyberdeck-golden-backup/
  ```

---

### Diagnostic Rule: How to Tell a Halted Pi from a Dead One

When the cyberdeck appears dark or unresponsive, use this physical diagnostic decision tree:

```text
+-------------------------------------------------------------+
|               CYBERDECK DIAGNOSTIC DECISION TREE             |
+-------------------------------------------------------------+
                           |
            Check Green ACT LED through vent
                           |
         +-----------------+-----------------+
         |                                   |
    ACT LED is OFF                     ACT LED is ON
         |                                   |
Check CYD Display Backlight          Check ACT LED Behavior
         |                                   |
    +----+----+                         +----+----+
    |         |                         |         |
Backlight Backlight                Solid ON   Blinking
   OFF       ON                    (Locked)   Pattern
    |         |                         |         |
 [HALTED]  [CRASHED]                [FROZEN]   [BOOT FAULT]
Clean shutdown Serial bridge        Kernel     Read blink
Opcode 0x06    died before          deadlock   code below
executed       sleep hook           Hard reset
```

#### Detailed Diagnostic Indicators
1. **Case 1: Cleanly Halted Pi (Normal Shutdown)**
   * **ACT LED:** Solid **OFF** (after a 10-flash halt signal).
   * **CYD Display:** Completely dark. The `goodbye_hook` executed opcode `0x06` (`SLEEP`), pulling backlight GPIO 21 LOW and issuing ILI9341 sleep commands.
   * **Power State:** Pi is halted; unswitched 5V rail remains energized drawing ~100 mA idle.
   * **Action:** Safe to toggle the physical power switch OFF.

2. **Case 2: Frozen / Locked Pi (System Hang)**
   * **ACT LED:** Solid **ON** without flickering (no kernel disk/CPU activity).
   * **CYD Display:** Backlight actively lit (displaying frozen frame or white raster).
   * **Power State:** SoC is locked up or core watchdog stalled.
   * **Action:** Toggle physical power switch OFF, wait 3 seconds, toggle ON.

3. **Case 3: Bootloader / Firmware Fault**
   * **ACT LED:** Repeating blinking flash sequence:
     * *4 flashes:* `start.elf` not found on MicroSD partition 1.
     * *7 flashes:* `kernel.img` not found.
     * *8 flashes:* SDRAM not recognized or corrupted.
   * **Action:** Swap to spare pre-imaged MicroSD card.

4. **Case 4: Completely Dead / Depleted Battery**
   * **ACT LED:** Completely **OFF**.
   * **CYD Display:** Backlight **OFF**.
   * **Power Switch:** Toggling switch produces zero LED activity.
   * **Action:** Battery has hit 10.2V hardware BMS cutoff. Attach 12.6V DC charger or USB-C power bank.

---

## 5. Software Sanity Checks & Verification Summary

### `pi/bin/demo`
* **File Location:** `pi/bin/demo` (mode 0755) and deployed to `/usr/local/bin/demo`.
* **Column Formatting:** All borders, headers, and telemetry output strictly adhere to `<= 53 columns` to prevent line-wrapping on CYD Font 1 and Font 2.
* **Character Set:** Pure ASCII text; no multibyte emojis that break custom CYD fonts.
* **Telemetry Queries:** Reads `/sys/class/thermal/thermal_zone0/temp` directly (no elevated privileges needed) and `/run/battery_monitor/status.json`.

### `pi/terminal/login_view.py`
* **Demo Mode Logic:** Lines 170-174 evaluate `if demo_mode and rows > 4:`:
  * For displays with `>= 19 columns`: renders `demo: guest / guest`.
  * For narrow displays `< 19 columns`: renders `guest / guest`.
* **Automatic Activation:** `daemon.py` line 175 automatically sets `demo_mode = True` whenever `"guest"` is present in the configured user list.
* **Security:** Password field uses `state.masked()`, rendering strictly asterisks; credentials can never be leaked onto the character grid.
* **Test Verification:** Unit test `test/unit_login.py` passes 100% of assertion checks.
