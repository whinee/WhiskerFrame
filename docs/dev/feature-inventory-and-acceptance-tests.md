# WhiskerFrame Cyberdeck Feature Inventory & Acceptance Test Plans

**Document Version:** 1.0.0  
**Target Milestone:** `v0` (Demo Prototype) / `v1` (Field Hardened)  
**Date:** 2026-10-16  
**Reference Invariants:** `.agents/rules/document-architecture-sync.md`, `docs/specifications/product-requirements.md`, `docs/dev/ai-decisions.md`

---

## 1. Comprehensive Feature Inventory

This inventory enumerates every implemented subsystem, capability, CLI tool, daemon, and driver in the WhiskerFrame cyberdeck codebase, mapped to its source artifacts, architectural tickets, and design decisions.

| Subsystem | Feature / Capability | Description & Wire Contract | Primary Source Artifacts | Tickets & Decisions | Status |
|---|---|---|---|---|---|
| **Terminal Core** | VT100 Grid Emulator | Pure Python ANSI/VT100 grid emulator managing cursor, wrap, scroll, and 16-color ANSI SGR attributes (`Theme.sgr_to_rgb565`). Standardized on `TERM=xterm`. Full dirty-cell blank wash on `\x1b[2J`. | `pi/terminal/vt.py`, `pi/terminal/grid.py`, `pi/terminal/theme.py` | TSK-01, TSK-17, DEC-W31 | `VERIFIED` |
| **Terminal Core** | Differential UART Repaint | Cell-run coalescing (`grid.diff`) emitting incremental `DRAW_CELLS` (`0x03`) and `SCROLL` (`0x04`) frames over 115,200 baud UART. Bounded periodic keyframe refresh. | `pi/terminal/bridge.py`, `whiskerframe/protocol.py`, `firmware/cyd_display_link/render.h` | TSK-01, DEC-W5, DEC-W14 | `VERIFIED` |
| **Terminal Core** | PAM Login Gate | User selection picker (`LoginState`), masked password entry emitting `*`, authentication via `simplepam`, and child shell spawning via `su - <user>` on PTY. | `pi/terminal/login.py`, `pi/terminal/login_view.py`, `pi/terminal/daemon.py` | TSK-01, TSK-11, DEC-W29 | `VERIFIED` |
| **Terminal Core** | Multi-PTY Workspaces | Embedded session multiplexer supporting up to 4 concurrent workspaces (`WS1`..`WS4`), background async select pump, CardKB switching chords, and differential screen swapping. | `pi/terminal/bridge.py`, `pi/terminal/grid.py` | TSK-22, DEC-W36 | `VERIFIED` |
| **Terminal Core** | Low-Flicker Status Bar | 1-line telemetry bar on row 0/29 updated at 2.0s throttled cadence via cell diffing (<10 bytes per tick), reading cached telemetry without I2C stalls. | `pi/terminal/bridge.py`, `docs/specifications/architecture.md` | TSK-23, DEC-W37 | `VERIFIED` |
| **Input Subsystem** | CardKB I2C Driver | Non-blocking poll adapter over `/dev/i2c-0` (`0x5F`) using Pins 27/28. Whitelist + 30 ms identical-byte ripple debounce filter. | `pi/cardkb/reader.py`, `test/test_cardkb_filter.py` | TSK-01, DEC-W6 | `VERIFIED` |
| **Input Subsystem** | Sticky Ctrl Latch | Sequential sticky modifier state machine on `Fn+Tab` (`0x8C`). Bitmasks next alphanumeric key with `& 0x1F` (emitting C0 codes like `Ctrl+C` = `0x03`). 3.0s timeout and toggle cancel. | `pi/terminal/bridge.py`, `test/test_ctrl_latch.py`, `scripts/reliability/test_ctrl_latch_edge_cases.py` | TSK-12, DEC-W29 | `VERIFIED` |
| **Input Subsystem** | SK6812 NeoPixel Feedback | Hardware LED control over I2C: opcode `0x13 [r, g, b]` (set color) and `0x11` (clear). Drives NeoPixel bright yellow (`255, 200, 0`) on Ctrl latch; default-off on boot. | `pi/cardkb/reader.py`, `pi/terminal/bridge.py` | TSK-16, TSK-19, DEC-W30, DEC-W33 | `VERIFIED` |
| **Input Subsystem** | 53-Col Key Cheatsheet | Standalone 53-column CLI reference tool (`keys`) documenting CardKB keybindings, sticky Ctrl latch, and `Fn+Backspace` geometry cycling. | `pi/bin/keys`, `docs/dev/keyboard-cheatsheet.md` | TSK-12, DEC-W29 | `VERIFIED` |
| **Typography** | Multi-Geometry Font Engine | 4 distinct character geometries: 53x30 (Font 1, 6x8), 40x20 (Font 5, 8x12), 26x15 (Font 2, 12x16), 17x10 (Font 3, 18x24). Dynamic cycling via `Fn+Backspace` (`0x8B`). | `whiskerframe/metrics.py`, `pi/terminal/bridge.py`, `test/prop_terminal_geometry.py` | TSK-18, DEC-W30, DEC-W32 | `VERIFIED` |
| **Typography** | Font Compilation Pipeline | Python utility compiling 95 printable ASCII glyphs (32..126) from monospaced sources into compact C++ PROGMEM bitmask arrays (`kFont8x12Glyphs[95][12]`). | `scripts/generate_font_8x12.py`, `firmware/cyd_display_link/font_8x12.h` | TSK-18, DEC-W32 | `VERIFIED` |
| **Display Link** | Binary Wire Protocol | Framing envelope (`SOF 0xA5`, `LEN u16`, `OPCODE u8`, `PAYLOAD`, `CRC8`). Opcodes `0x01`–`0x06` (`DRAW_TEXT`, `DRAW_RECT`, `DRAW_CELLS`, `SCROLL`, `DRAW_IMAGE`, `SLEEP`). | `whiskerframe/protocol.py`, `whiskerframe/terminal.py`, `firmware/cyd_display_link/` | TSK-01, TSK-13, DEC-W5, DEC-W29 | `VERIFIED` |
| **Display Link** | Big-Endian RGB565 Blitting | Coprocessor binary image streaming (`0x05 DRAW_IMAGE`) using big-endian byte order (high byte first) matching TFT_eSPI `pushImage`. 2-row bounded chunks (1,280 bytes). | `whiskerframe/protocol.py`, `scripts/convert_splash.py`, `pi/terminal/splash.py` | TSK-01, TSK-21, DEC-W5, DEC-W35 | `VERIFIED` |
| **Display Link** | Low-Power Display Sleep | Additive opcode `0x06` (`SLEEP`) commanding ESP32 to cut backlight, enter `DISPOFF`/`SLPIN`, and lower CPU to 80MHz. Wakes immediately on next valid frame. | `whiskerframe/protocol.py`, `whiskerframe/terminal.py`, `firmware/cyd_display_link/main.cpp` | TSK-13, DEC-W29 | `VERIFIED` |
| **Lifecycle** | Boot Splash Hold | Letterboxed 320x240 RGB565 boot splash streamed at initialization, held for 3.0 seconds before presenting the interactive login gate. | `pi/terminal/splash.py`, `pi/terminal/bridge.py` | TSK-01, TSK-16, DEC-W30 | `VERIFIED` |
| **Lifecycle** | Split Systemd Goodbye Units | Dedicated systemd units: `cyberdeck-goodbye-reboot.service` (`reboot.target`, `"brb :3"`) and `cyberdeck-goodbye-shutdown.service` (`poweroff.target`, `"bai baiii!"`). 8.0s timeout. | `pi/terminal/cyberdeck-goodbye-reboot.service`, `pi/terminal/cyberdeck-goodbye-shutdown.service`, `pi/bin/goodbye_hook` | TSK-13, TSK-16, DEC-W30, DEC-W31 | `VERIFIED` |
| **Guest Sandbox** | Unprivileged Guest Account | Dedicated demo account (`guest:guest`) with credentials hint rendered on login screen (`demo_mode: true`). Sourced from `ansible/roles/guest_demo/`. | `/etc/whiskerframe.yaml`, `pi/terminal/login_view.py`, `ansible/roles/guest_demo/` | TSK-10, TSK-11, DEC-W27, DEC-W29 | `VERIFIED` |
| **Guest Sandbox** | Ephemeral RAM Home Directory | `/home/guest` mounted on 8MB tmpfs (`nodev,nosuid,mode=0700`). Automatically purged and restored from `/etc/skel` on session close via PAM hook. | `/usr/local/bin/guest-session-cleanup.sh`, `/etc/pam.d/common-session` | TSK-10, DEC-W27, DEC-W34 | `VERIFIED` |
| **Guest Sandbox** | Kernel nftables Egress Drop | Dedicated `nftables` table `guest_isolation` blocking all outbound packets from `skuid "guest"` (LAN, WAN, loopback). Persistent across boots. | `/etc/nftables.d/guest_isolation.nft`, `/etc/nftables.conf` | TSK-10, DEC-W27, DEC-W29 | `VERIFIED` |
| **Guest Sandbox** | Process Execution Reaper | Systemd daemon (`cyberdeck-guest-reaper.service`) executing every 5s. Terminates guest child processes running >5s with SIGKILL while preserving the login shell. | `/usr/local/bin/cyberdeck-guest-reaper.sh` | TSK-10, DEC-W27, DEC-W34 | `VERIFIED` |
| **Guest Sandbox** | Interactive Demo Telemetry | 53-column interactive sandbox dashboard (`pi/bin/demo`) auto-launched on guest login, displaying live uptime, battery voltage/percentage, thermals, and memory. | `pi/bin/demo`, `/home/guest/.bashrc` | TSK-10, TSK-20, DEC-W27, DEC-W34 | `VERIFIED` |
| **Guest Sandbox** | Containment Abuse Test Suite | Automated security test harness validating 11 attack vectors (network egress, tmpfs write limits, cgroups CPU/memory, persistence, privacy boundaries). | `/usr/local/bin/test-guest-containment.sh` | TSK-10, DEC-W27 | `VERIFIED` |
| **Network UX** | 53-Col Wi-Fi Helper | Command-line utility (`wifi`) wrapping NetworkManager into <=53 columns: `status`, `scan`, `join`, `forget`. Captive portal detection and 802.1X Enterprise warnings. | `pi/bin/wifi`, `docs/dev/network-access.md`, `test/test_wifi_helper.py` | TSK-14, DEC-W29, DEC-W30 | `VERIFIED` |
| **Network UX** | Wi-Fi Cold Boot Persistence | Headless persistence layer: kernel `rfkill default_state=1`, regdom `PH`, persistent SSD journal, NM `wifi.powersave=2` disabled, autoconnect priority 100. | `ansible/roles/wifi_persistence/`, `docs/dev/network-access.md` | TSK-08, DEC-W25 | `VERIFIED` |
| **Network UX** | Self-Healing Watchdog | Autonomous network recovery timer (`cyberdeck-net-heal.timer`) running ~30s checks with 3-tier escalation (unblock wlan0 -> restart NM -> reload driver). Dual heartbeat logs. | `ansible/roles/self_heal_watchdog/` | TSK-09, DEC-W26 | `VERIFIED` |
| **Network UX** | Hardware BCM2835 Watchdog | Hardware watchdog supervision via `/etc/systemd/system.conf.d/00-watchdog.conf` (`RuntimeWatchdogSec=60s`). `fake-hwclock` hourly saves. | `ansible/roles/self_heal_watchdog/` | TSK-09, DEC-W26 | `VERIFIED` |
| **Hardware Telemetry** | INA219 Battery Daemon | Background monitor on I2C-1 (`0x41`) polling 3S Li-ion pack voltage, current, and state of charge; writes `/run/battery_monitor/status.json` with auto-shutdown at 5%. | `pi/battery_monitor/` | TSK-01, DEC-W17, DEC-W21 | `VERIFIED` |
| **Storage Subsystem** | BTRFS Mount Generator | Idempotent systemd mount generator (`install_mount.py`) rendering `storage.mount` from `.whiskerframe.yaml` (`uuid: 98bb87d2-...`, `compress=zstd:3`, `subvol=@data`). | `pi/storage/install_mount.py`, `pi/storage/storage.mount.example` | TSK-02, TSK-02a, DEC-W7, DEC-W12 | `VERIFIED` |
| **Storage Subsystem** | SD Wear Reduction | Flash wear mitigation via `log2ram` (32MB RAM ring buffer) and diversion of persistent `journald` storage to `/mnt/250GB-SSD/log/journal`. | `ansible/roles/journald_ssd/` | TSK-03, DEC-W10 | `VERIFIED` |
| **Storage Subsystem** | Memory Safety Hierarchy | Two-tier swap architecture: zram compressed RAM (priority 100, 208MB) + BTRFS SSD swapfile (priority 10, 512MB, `nodatacow`). `vm.swappiness=15`, `earlyoom` daemon. | `ansible/roles/memory_safety/` | TSK-07, DEC-W11, DEC-W12 | `VERIFIED` |
| **Documentation & CLI**| 53-Col Offline Wiki CLI | Command-line documentation tool (`wiki`) wrapping `man`, `bash-doc`, and `python3-doc` into 53-column readable text with offline fallbacks. | `pi/bin/wiki`, `docs/dev/offline-library-plan.md`, `test/test_wiki_helper.py` | TSK-15, DEC-W29 | `VERIFIED` |
| **Documentation & CLI**| Compact Shell Prompts | Ergonomic prompts: `n~ ` (neko), `g~ ` (guest), and `r# ` (root) deployed via `/etc/profile.d/cyd_prompt.sh`, preventing line-wrap truncation on small screens. | `/etc/profile.d/cyd_prompt.sh` | TSK-16, DEC-W30 | `VERIFIED` |

---

## 2. Acceptance Test Plans (ATPs)

Each test plan defines the preconditions, step-by-step commands, expected outputs, pass/fail criteria, and rollback instructions for a concrete system capability.

---

### ATP-01: Terminal Live Login & PAM su Authentication

* **Identifier:** `ATP-01-TERM-LOGIN`
* **Requirements Addressed:** `REQ-TERM-01`, `REQ-TERM-02`, `REQ-TERM-04`
* **Preconditions:**
  1. CYD display connected via USB-Serial (`/dev/ttyUSB0`) and CardKB on I2C-0 (`/dev/i2c-0`).
  2. `terminal.service` is active and running.
* **Execution Steps:**
  1. Observe CYD display upon boot: verify boot splash displays for 3.0 seconds, followed by blurple login screen.
  2. Verify credentials hint on bottom row: `"demo: guest / guest"`.
  3. Use CardKB arrow keys (`Down`/`Up`) to navigate between `neko`, `guest`, and `root`.
  4. Select `guest`, press `Enter`, enter password `guest`, and press `Enter`.
  5. Verify successful shell spawn: observe prompt `g~ `.
  6. Execute `exit` or `logout`.
* **Pass / Fail Criteria:**
  * **PASS:** Login screen accepts keystrokes, masks password with `*`, spawns unprivileged shell as `guest`, renders `g~ `, and clean logout returns to user picker.
  * **FAIL:** Display freezes, password echoes in plaintext, authentication fails with valid credentials, or logout fails to restore the login view.
* **Rollback:** `ssh root@10.0.0.212 "systemctl restart terminal.service"`

---

### ATP-02: Sticky Ctrl Latch (`Fn+Tab`) & SK6812 NeoPixel Yellow Feedback

* **Identifier:** `ATP-02-INP-CTRL-LATCH`
* **Requirements Addressed:** `REQ-INP-03`, `REQ-INP-04`, `REQ-INP-05`
* **Preconditions:**
  1. Interactive terminal shell active on Cyberdeck.
  2. CardKB NeoPixel initially off (or green/sym).
* **Execution Steps:**
  1. Start an uninterruptible command: `cat` (blocking on stdin) or `sleep 60`.
  2. On CardKB, press `Fn + Tab` (`0x8C`).
  3. **Observe:** Verify the CardKB NeoPixel illuminates bright yellow (`RGB 255, 200, 0`) AND the terminal cursor cell recolors to bright yellow (`#ffe08a`).
  4. Press `c`.
  5. **Observe:** Verify the foreground process receives `SIGINT` (`Ctrl+C` = `0x03`) and terminates immediately.
  6. **Observe:** Verify the NeoPixel extinguishes and cursor color restores to default.
  7. Press `Fn + Tab` again, wait 3.5 seconds without typing. Verify latch disarms automatically (NeoPixel turns off, cursor restores).
* **Pass / Fail Criteria:**
  * **PASS:** `Fn+Tab` latches Ctrl, lights yellow NeoPixel and yellow cursor, `c` sends `\x03` killing process, latch auto-disarms, timeout works.
  * **FAIL:** NeoPixel does not light, `Ctrl+C` is not delivered, or latch remains stuck permanently.
* **Rollback:** Press `Fn + Tab` again to toggle off, or restart terminal service.

---

### ATP-03: Multi-Geometry Font Cycling (`Fn+Backspace`) & 8x12 Typography

* **Identifier:** `ATP-03-TYPO-GEOMETRY`
* **Requirements Addressed:** `REQ-TERM-02`, `REQ-TERM-03`, `REQ-UX-08`
* **Preconditions:**
  1. Active shell session on Cyberdeck.
  2. Initial geometry is 53x30 (Font 1, 6x8).
* **Execution Steps:**
  1. Run `stty size` in shell; verify output is `30 53`.
  2. Press `Fn + Backspace (labeled 'del')` (`0x8B`).
  3. **Observe:** Screen clears and repaints into Font 5 (8x12 intermediate Comic Mono/monospace layout). Run `stty size`; verify `20 40`.
  4. Press `Fn + Backspace` again: verify Font 2 (12x16, `15 26`).
  5. Press `Fn + Backspace` again: verify Font 3 (18x24, `10 17`).
  6. Press `Fn + Backspace` again: verify return to Font 1 (6x8, `30 53`).
* **Pass / Fail Criteria:**
  * **PASS:** Geometry cycles smoothly across all 4 layouts: 53x30 -> 40x20 -> 26x15 -> 17x10 -> 53x30; PTY window size updates via `TIOCSWINSZ`; zero dirty cell artifacts.
  * **FAIL:** Coprocessor hangs, text wraps incorrectly, or font cycling chord fails to trigger.
* **Rollback:** Cycle back to Font 1 via chord, or restart `terminal.service`.

---

### ATP-04: Guest Demo Sandbox Containment & Abuse Rejection

* **Identifier:** `ATP-04-SEC-GUEST-CONTAINMENT`
* **Requirements Addressed:** `REQ-OPS-04`, `REQ-SEC-01`, `REQ-CAP-03`
* **Preconditions:**
  1. Pi online; `nftables.service` and `cyberdeck-guest-reaper.service` active.
  2. Automated test suite present at `/usr/local/bin/test-guest-containment.sh`.
* **Execution Steps:**
  1. Log into Cyberdeck as `guest` (password `guest`).
  2. Execute `/usr/local/bin/test-guest-containment.sh`.
  3. Verify all 11 security containment tests execute and pass:
     - Test 1: Network egress drop (WAN ping denied).
     - Test 2: Local LAN scanning blocked (gateway ping denied).
     - Test 3: Loopback isolation enforced.
     - Test 4: Ephemeral home tmpfs mounted (`8M` max, `nodev,nosuid`).
     - Test 5: Writing >8MB to home fails with `No space left on device`.
     - Test 6: Operator home `/home/neko` is unreadable (Permission denied, `0700`).
     - Test 7: Root directory `/root` is unreadable (`0700`).
     - Test 8: Wi-Fi credentials in `/etc/NetworkManager` unreadable (`0700`).
     - Test 9: Cgroup memory limit enforced (`MemoryMax=64M`).
     - Test 10: Process execution reaper kills long-running processes after 5s.
     - Test 11: Ephemeral tmpfs completely wiped and reset on logout.
* **Pass / Fail Criteria:**
  * **PASS:** Output prints `11/11 tests PASSED. Guest containment fully enforced.`
  * **FAIL:** Any test fails or network packets escape the guest sandbox.
* **Rollback:** `ansible-playbook -i ansible/inventory.ini ansible/site.yml --tags guest_demo`

---

### ATP-05: Goodbye & Reboot Splash Hooks

* **Identifier:** `ATP-05-LIFE-GOODBYE`
* **Requirements Addressed:** `REQ-UX-05`, `REQ-UX-09`, `REQ-TERM-01`
* **Preconditions:**
  1. Pi running with `cyberdeck-goodbye-reboot.service` and `cyberdeck-goodbye-shutdown.service` enabled.
  2. Operator watching physical display.
* **Execution Steps:**
  1. Execute `sudo reboot` from terminal or via SSH.
  2. **Observe:** Display washes to blurple, blits centered 128x128 doodle with text `"brb :3"`, holds for ~3.5 seconds, then cleanly wipes to black before hardware reset.
  3. Total execution completes within the 8.0s systemd window.
  4. Following boot, execute `sudo poweroff`.
  5. **Observe:** Display washes to blurple, blits centered 128x128 doodle with text `"bai baiii!"`, holds for ~3.5 seconds, wipes to black, and halts cleanly.
* **Pass / Fail Criteria:**
  * **PASS:** Reboot shows `"brb :3"`; shutdown shows `"bai baiii!"`; display wipes to black; zero hang or timeout during systemd halt.
  * **FAIL:** Display freezes with terminal text visible, shows wrong splash message, or systemd kills hook due to timeout.
* **Rollback:** Re-enable services via `systemctl enable cyberdeck-goodbye-reboot.service cyberdeck-goodbye-shutdown.service`.

---

### ATP-06: 53-Column Wi-Fi CLI (`pi/bin/wifi`) & Captive Portal Detection

* **Identifier:** `ATP-06-NET-WIFI-HELPER`
* **Requirements Addressed:** `REQ-NET-01`, `REQ-NET-02`
* **Preconditions:**
  1. Deck operating with wlan0 radio unblocked (`rfkill list wifi` shows unblocked).
  2. `pi/bin/wifi` deployed and executable.
* **Execution Steps:**
  1. Run `wifi status`: verify output fits within 53 columns. Verify connection state, active SSID, signal strength, IP address, and gateway.
  2. Run `wifi scan`: verify top 10 available 2.4 GHz SSIDs are displayed with signal bars (`####`), security status (`WPA2`/`OPEN`), and no lines exceed 53 characters.
  3. Connect to an AP: `wifi join <SSID>` (or profile index). Verify secure, hidden password entry prompt.
  4. If connected to a captive network (HTTP 204 check fails): verify prominent warning: `"CAPTIVE PORTAL DETECTED!"`.
* **Pass / Fail Criteria:**
  * **PASS:** Output strictly <=53 columns; scan lists 2.4 GHz networks; join connects cleanly; captive portals flagged immediately.
  * **FAIL:** Text overflows 53 columns wrapping awkwardly; password echoes on screen; join crashes on secured network.
* **Rollback:** `nmcli connection reload`

---

### ATP-07: Persistent BTRFS Mount & Swap Priority Hierarchy

* **Identifier:** `ATP-07-STOR-BTRFS-SWAP`
* **Requirements Addressed:** `REQ-STORAGE-01`, `REQ-STORAGE-02`, `REQ-STORAGE-03`
* **Preconditions:**
  1. Samsung 860 EVO 250GB SSD connected via USB SATA bridge.
  2. Unit `mnt-250GB\x2dSSD.mount` enabled and active.
* **Execution Steps:**
  1. Run `findmnt /mnt/250GB-SSD`:
     Verify filesystem is `btrfs`, subvolume is `/@data`, and options include `compress=zstd:3`.
  2. Run `swapon --show`:
     Verify two swap devices active:
     - `/dev/zram0` (priority 100, ~208MB).
     - `/swap/swapfile` (priority 10, 512MB, on `@swap` subvolume with `nodatacow`).
  3. Verify `cat /proc/sys/vm/swappiness` returns `15`.
  4. Verify `systemctl is-active earlyoom` returns `active`.
* **Pass / Fail Criteria:**
  * **PASS:** BTRFS mount active with zstd compression; zram priority (100) strictly outranks SSD swapfile (10); earlyoom running.
  * **FAIL:** SSD fails to mount; swapfile located on root SD card; zram missing or lower priority than SSD.
* **Rollback:** `ansible-playbook -i ansible/inventory.ini ansible/site.yml --tags memory_safety`

---

### ATP-08: Wi-Fi Cold Boot Persistence & 3-Tier Self-Healing Watchdog

* **Identifier:** `ATP-08-NET-SELF-HEAL`
* **Requirements Addressed:** `REQ-NET-03`, `REQ-NET-04`, `REQ-OPS-03`
* **Preconditions:**
  1. Pi online on Wi-Fi network.
  2. Safety rule active: Rescue timer armed before disruptive network actions.
* **Execution Steps:**
  1. Check cold boot persistence files:
     - `cat /etc/modprobe.d/rfkill_default.conf` -> `options rfkill default_state=1`.
     - `iw reg get` -> country `PH`.
     - `cat /etc/NetworkManager/conf.d/default-wifi-powersave.conf` -> `wifi.powersave=2`.
  2. Arm a 90-second rescue timer:
     `systemd-run --on-active=90s rfkill unblock wifi`
  3. Intentionally sever network link:
     `rfkill block wifi`
  4. **Observe:** Wait 30-45 seconds for `cyberdeck-net-heal.timer` to trigger Tier 1 recovery (`rfkill unblock wifi` + `nmcli radio wifi on`).
  5. Check connection restoration: ping gateway or check SSH reconnect.
* **Pass / Fail Criteria:**
  * **PASS:** Radio self-heals within 36 seconds without rebooting the Pi; persistent heartbeat recorded in `/run/cyberdeck/heartbeat.json`.
  * **FAIL:** Link remains dead until manual intervention; system requires hard reboot.
* **Rollback:** Automated rescue timer unblocks radio if self-heal fails.

---

### ATP-09: Battery Monitor & Thermal Telemetry Service

* **Identifier:** `ATP-09-HW-BATTERY-THERMAL`
* **Requirements Addressed:** `REQ-HW-04`, `REQ-PWR-01`, `REQ-PWR-02`
* **Preconditions:**
  1. Waveshare UPS 3S module attached to I2C-1 (`0x41`).
  2. `battery-monitor.service` active.
* **Execution Steps:**
  1. Inspect `/run/battery_monitor/status.json`:
     Verify valid JSON containing:
     - `bus_voltage_v` (between 9.0V and 12.6V).
     - `current_ma` (positive charging, negative discharging).
     - `battery_percent` (0..100%).
     - `fresh: true` and current ISO-8601 `updated_at` timestamp.
  2. Inspect `/sys/class/thermal/thermal_zone0/temp`:
     Verify temperature reading is realistic (e.g. 50000..70000 millidegrees C, 50.0..70.0°C).
  3. Run `demo` utility and verify Power and Thermal readings match raw sysfs values.
* **Pass / Fail Criteria:**
  * **PASS:** Telemetry JSON is fresh (<5s old), voltage and percentage are within physical 3S cell bounds, thermals report accurately.
  * **FAIL:** Values stuck/frozen, I2C bus error causes daemon crash, or JSON file missing.
* **Rollback:** `ssh root@10.0.0.212 "systemctl restart battery-monitor.service"`

---

### ATP-10: Coprocessor Binary Image Blitting (`0x05 DRAW_IMAGE`) & Grid Repaint

* **Identifier:** `ATP-10-DISP-DRAW-IMAGE`
* **Requirements Addressed:** `REQ-TERM-07`, `REQ-UX-05`
* **Preconditions:**
  1. Serial link active between Pi and CYD coprocessor.
  2. Terminal session active on display.
* **Execution Steps:**
  1. Stream a test image to the display using `whiskerframe/terminal.py`:
     Create and serialize a `DrawImage` frame with 2-row chunking (1,280 bytes per chunk).
  2. **Observe:** Image blits onto the ILI9341 LCD without color distortion or horizontal pixel shearing.
  3. Emit terminal text or trigger a bridge `full_repaint()`.
  4. **Observe:** Character grid text cleanly overwrites the image region without VRAM corruption or stale pixel debris.
* **Pass / Fail Criteria:**
  * **PASS:** Image renders with correct big-endian colors; zero UART FIFO overflows; text cleanly repaints over the image area.
  * **FAIL:** Image inverted/corrupted; coprocessor resets or panics; terminal grid corrupted after render.
* **Rollback:** `whiskerframe` script issuing `Clear()` frame (`0xA5 0x01 0x00 0x02 ...`).

---

### ATP-11: Multi-PTY Terminal Workspaces & CardKB Switching Chords

* **Identifier:** `ATP-11-TERM-WORKSPACES`
* **Requirements Addressed:** `REQ-TERM-05`
* **Preconditions:**
  1. Interactive terminal session running on Cyberdeck.
  2. CardKB connected.
* **Execution Steps:**
  1. Log into workspace 1 (`WS1`). Launch a continuous task: `top` or a counter script `while true; do date; sleep 1; done`.
  2. Press `Fn + 2` on CardKB.
  3. **Observe:** Screen switches to workspace 2 (`WS2`) with a clean login/shell prompt.
  4. In workspace 2, edit a file or run `wifi status`.
  5. Press `Fn + 1` on CardKB.
  6. **Observe:** Screen immediately switches back to workspace 1; verify the background task has continued executing without interruption.
  7. In workspace 2, type `exit`. Verify workspace 2 closes while workspace 1 remains running.
* **Pass / Fail Criteria:**
  * **PASS:** Workspaces switch cleanly via CardKB chords; background tasks continue running; memory usage remains <100 KB RAM; exiting one workspace preserves siblings.
  * **FAIL:** Switching drops child processes; display tearing on switch; closing one workspace halts the entire terminal bridge.
* **Rollback:** Restart `terminal.service`.

---

### ATP-12: Offline Documentation Helper (`pi/bin/wiki`)

* **Identifier:** `ATP-12-CAP-OFFLINE-WIKI`
* **Requirements Addressed:** `REQ-CAP-01`, `REQ-CAP-02`
* **Preconditions:**
  1. Packages `bash-doc`, `python3-doc`, `man-db` installed on host.
  2. `pi/bin/wiki` deployed and executable.
* **Execution Steps:**
  1. Run `wiki ls`: verify available documentation topics are listed within 53 columns.
  2. Run `wiki echo`: verify `man echo` output is rendered cleanly wrapped to <=53 columns.
  3. Run `wiki math`: verify Python math module documentation renders readable text without line-wrapping truncation.
  4. Disconnect all network interfaces (`nmcli radio wifi off`) and repeat query. Verify documentation functions 100% offline.
* **Pass / Fail Criteria:**
  * **PASS:** All output formatted to <=53 columns; no text clipping; queries resolve completely offline without network access.
  * **FAIL:** Output assumes 80 columns and wraps awkwardly; tool attempts external network requests; query crashes.
* **Rollback:** `nmcli radio wifi on`

---

## 3. Acceptance Verification Summary Matrix

| Test Plan ID | Subsystem | Target Milestone | Automation Level | Test Command / Script | Status |
|---|---|---|---|---|---|
| **ATP-01** | Terminal Core | `v0` | Semi-Automated / Hardware | `test/unit_login.py` & manual login on CardKB | `VERIFIED` |
| **ATP-02** | Input Subsystem | `v0` | Fully Automated & Hardware | `test/test_ctrl_latch.py`, `scripts/reliability/test_ctrl_latch_edge_cases.py` | `VERIFIED` |
| **ATP-03** | Typography | `v0/v1` | Fully Automated & Hardware | `test/prop_terminal_geometry.py`, `scripts/generate_font_8x12.py` | `VERIFIED` |
| **ATP-04** | Guest Sandbox | `v0` | Fully Automated | `/usr/local/bin/test-guest-containment.sh` (11/11 pass) | `VERIFIED` |
| **ATP-05** | System Lifecycle | `v0` | Fully Automated & Hardware | `test/test_goodbye_hook.py`, manual reboot eyeball test | `VERIFIED` |
| **ATP-06** | Network UX | `v0` | Automated & Manual | `test/test_wifi_helper.py`, `pi/bin/wifi status` | `VERIFIED` |
| **ATP-07** | Storage & Memory | `v0` | Fully Automated | `findmnt`, `swapon --show`, `earlyoom` status | `VERIFIED` |
| **ATP-08** | Self-Healing | `v0` | Fully Automated | `scripts/reliability/net_heal_drill.sh`, `test_reliability.py` | `VERIFIED` |
| **ATP-09** | Hardware Telemetry | `v0` | Fully Automated | `pi/bin/demo`, `/run/battery_monitor/status.json` check | `VERIFIED` |
| **ATP-10** | Coprocessor Blitting| `v0` | Fully Automated | `test/prop_terminal_protocol.py`, `pi/terminal/splash.py` | `VERIFIED` |
| **ATP-11** | Workspaces | `v0` | Fully Automated & Hardware | `scripts/reliability/test_terminal_pty_soak.py` | `VERIFIED` |
| **ATP-12** | Offline Docs | `v0` | Fully Automated | `test/test_wiki_helper.py`, `pi/bin/wiki echo` | `VERIFIED` |
