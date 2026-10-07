# MASTER SPECIFICATION & ARCHITECTURE RFC: CYBERDECK (WHISKERFRAME)

**Target System:** Raspberry Pi Zero 2W Host (`${PI_USER}@${PI_HOST}`) + ESP32 CYD (ILI9341 Display Coprocessor)

**System Role:** Single-user ultraportable cyberdeck, hardware-integrated terminal, and autonomous agent orchestration node.

**Specification Status:** Living Base Spec (v0.2.0-seed) — Machine-readable contract for Orchestrator & Worker Agents.

---

## 1. System Architecture & Hardware Topology

The cyberdeck functions as an asymmetric dual-core system: a Linux host (Pi Zero 2W) handling storage, networking, PAM, and high-level agent logic, while an ESP32 coprocessor acts as a dedicated graphic/terminal rendering unit over serial.

```
                    +------------------------------------+
                    |        Raspberry Pi Zero 2W        |
                    |         (Raspberry Pi OS)          |
                    +---+--------------+--------------+--+
                        |              |              |
           USB-Serial   |        I2C-0 |        I2C-1 |
           (CH340)      |        (Pin 27/28)    (Pin 3/5)
                        |              |              |
                        v              v              v
               +----------------+ +----------+ +---------------+
               | ESP32-2432S028 | | M5Stack  | | UPS Module 3S |
               | (CYD Coproc)   | |  CardKB  | | (INA219 Sens) |
               | ILI9341 Display| | Addr 0x5F| | Addr 0x41    |
               +----------------+ +----------+ +---------------+

```

### 1.1 Hardware Node Matrix

| Component | Interface / Port | Address / Node | Operational Parameters | Critical Constraints |
| --- | --- | --- | --- | --- |
| **CYD (ESP32)** | USB-Serial (CH340) | `/dev/ttyUSB0` (`usb-1a86_USB_Serial...`) | 115200 baud (runtime), 460800 baud (flash) | Hardware is sealed inside deck. Panel requires `tft.invertDisplay(true)`. Exclusive lock by `terminal.service`. |
| **M5Stack CardKB** | I2C-0 (Pins 27/28) | `/dev/i2c-0` @ `0x5F` | Polled ASCII byte stream (`0x00` = idle) | Requires `dtparam=i2c_vc=on` & `dtoverlay=i2c0,pins_0_1`. Self-healing via `robust_keys()`. |
| **UPS Module 3S** | I2C-1 (Pins 3/5) | `/dev/i2c-1` @ `0x41` | 3S Li-ion pack (9.0V–12.6V) | Managed by `battery-monitor.service`. Calibrates per poll; auto-shutdown trigger at 5%. |
| **Storage (SSD)** | USB 2.0 (SATA-to-USB) | `/dev/disk/by-uuid/98bb87d2-7128-470e-91d5-9e117df2ab1a` | **btrfs** (whole-disk, label `cyberdeck-ssd`); `@data` subvol → `/mnt/250GB-SSD` (`noatime,compress=zstd`); `@swap` subvol holds the swapfile (`nodatacow`) | Must use `nofail` + device timeout to prevent boot hangs. Reconciled ext4→btrfs 2026-10-07 (DEC-W12); old ext4 UUID `a6ca355e-…` is dead. Swap is `nodatacow`/uncompressed (CoW incompatible with swap). |

---

## 2. Invariant Subsystem Contracts

Any worker agent altering code in these domains must maintain wire and runtime compatibility against these exact contracts.

### 2.1 The Wire Protocol Contract (`whiskerframe.protocol`)

The link between the host Python library (`whiskerframe/`) and the ESP32 C++ firmware (`firmware/cyd_display_link/`) is a fixed binary framing envelope. No high-level abstractions or bitmapped framebuffers may cross this bus.

#### Frame Layout

```text
+-------+--------+--------+---------------------+--------+
|  SOF  |  LEN   | OPCODE |  PAYLOAD (LEN-1 B)  |  CRC8  |
| 0xA5  | uint16 | uint8  |  Opcode-specific    | uint8  |
+-------+--------+--------+---------------------+--------+

```

* **SOF (Start of Frame):** Fixed byte `0xA5`.
* **LEN:** Little-endian `uint16` representing byte length of `OPCODE + PAYLOAD`.
* **CRC8:** CRC-8/SMBUS polynomial (`0x07`, init `0x00`, check `crc8(b"123456789") == 0xF4`). Calculated over `OPCODE + PAYLOAD`.
* **Byte Order:** Little-endian for framing/header integer fields (`LEN`, and the `u16` coordinate/color fields inside each payload). **Exception:** the raw pixel block carried by `DRAW_IMAGE` is **big-endian RGB565** (high byte first) on the wire — see §2.3.

#### Opcode Registry

| Opcode | Identifier | Payload Format | Semantics |
| --- | --- | --- | --- |
| `0x01` | `DRAW_TEXT` | `x:u16, y:u16, fg:u16, bg:u16, font:u8, anchor:u8, text_len:u16, text:str` | Direct text rendering with anchor alignment. |
| `0x02` | `DRAW_RECT` | `x:u16, y:u16, w:u16, h:u16, color:u16, filled:u8` | Background clears and structural panels. |
| `0x03` | `DRAW_CELLS` | `start_col:u8, row:u8, fg:u16, bg:u16, glyph_run:bytes` | VT100 character grid cell updates (terminal core). |
| `0x04` | `SCROLL` | `top_row:u8, bot_row:u8, count:i8, fill_color:u16` | Hardware region scroll (cell height tracked internally). |
| `0x05` | `DRAW_IMAGE` | `x:u16, y:u16, w:u16, h:u16, rgb565_data:bytes` | Splash screens and compressed iconography. Pixel block is **big-endian RGB565** (high byte first), see §2.3. |

### 2.2 Terminal & Cockpit Contract (`cyd-terminal`)

* **Line Discipline & Input:** The bridge takes ASCII bytes from CardKB (`0x5F`) and injects them into a pseudo-terminal (PTY) running a `bash` login shell.
* **Rendering Loop:** Terminal state is maintained via a VT100 character-grid emulator. The bridge computes screen diffs (`grid.diff`) and translates updates to `DRAW_CELLS` commands.
* **A11y Theme:** RGB565 theme derived from WCAG contrast auditing (`assets/themes/piiiiink-a11y.json`).
* **Session Life Cycle:** PAM authentication gate on boot (`simplepam` against `root` or `neko`). Invoking `logout` or `exit` must trap SIGCHLD, clear the display via full `DRAW_RECT` blurple wash, and drop back to the account picker.
* **CardKB Input Filter Contract:** CardKB bytes pass through a `KeyFilter` (`pi/cardkb/reader.py`, applied inside both `keys()` and `robust_keys()`) before reaching the bridge. The filter is a **whitelist + short debounce** aligned to the real M5Stack CardKB v1.1 byte table: C0 controls (`0x01`–`0x1F`), printable ASCII (`0x20`–`0x7E`), `0x7F` (Shift+Del), the Fn layer (`0x80`–`0xAF`), and arrows (`0xB4`–`0xB7`) pass; `0x00`/`0xFF`/out-of-range garbage are dropped, and an identical byte repeated within a conservative 30 ms window (`DEBOUNCE_WINDOW_S`, ripple guard) is suppressed. **Hardware reality:** the CardKB has no Ctrl key — the C0 range stays whitelisted so any emitted control byte reaches the shell, but control codes are produced only by on-device Fn/Sym layers, not a Ctrl modifier. The runtime **font-resize chord is `Fn+Del` (`0x8B`)** — the only reachable, non-colliding chord on this keyboard (the former `Ctrl+]`/`0x1D` was physically unreachable). The authoritative byte table lives in `pi/cardkb/reader.py`; rationale in `docs/dev/ai-decisions.md` DEC-W6.

### 2.3 RGB565 Color Packing, Wire Byte Order & Display Inversion

RGB565 values are a 16-bit packing of an 8-bit `(r, g, b)` triple, keeping the top bits of each channel: `value = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)` (5 bits red, 6 bits green, 5 bits blue). Example: pink `#ffb3e6` -> `0xFD9C`. That `uint16` *value* is identical everywhere; only its **byte order on the wire** differs by opcode.

**Image pixels are big-endian, not pre-inverted.** The `DRAW_IMAGE` (`0x05`) pixel block is packed **big-endian** (high byte first). The firmware blits it with TFT_eSPI `pushImage` while `_swapBytes = false`, so `pushImage` reads the two bytes in that big-endian order directly. The host splash packer (`scripts/convert_splash.py`) therefore emits high-byte-first. Pixels are shipped as their **true** RGB565 values — they are **NOT pre-inverted and NOT XOR-compensated**. (An earlier revision wrongly described a `value ^= 0xFFFF` pre-inversion to compensate a presumed per-image inversion; that was a misdiagnosis of a byte-order bug and has been removed — see `docs/dev/ai-decisions.md` DEC-W5.)

**Inversion is panel-level and uniform.** `tft.invertDisplay(true)` is a *panel* setting that affects **every** pixel the controller emits — text, rects, and images equally. It is not a per-opcode transform and must never be compensated per-opcode in software.

**Theme cell colors.** Theme values (`bg`/`fg`/`cursor`/`accents`/`ansi` consumed by `DRAW_CELLS`/`DRAW_TEXT`/`DRAW_RECT`) are shipped as their true RGB565 values. These opcodes travel the firmware's internally byte-swapped text/graphics path (`tft_Write_16S`), which is why they rendered correctly even while the splash byte order was wrong. Never pre-invert or XOR theme colors.

### 2.4 Storage Mount Contract (Template + Generator)

The persistent SSD mount is **never a committed, baked unit**. The repo ships a parameterized template and a generator; the live unit is produced from config, and the destructive and irreversible steps stay gated to a human.

* **Template:** `pi/storage/storage.mount.example` — a systemd `.mount` template carrying placeholder tokens (`@STORAGE_UUID@`, `@STORAGE_OPTIONS@`, etc.), no real device identity. The `@STORAGE_OPTIONS@` token is where the generator injects the fstype-specific mount options (for btrfs: `subvol=@data,compress=zstd,noatime,nofail`).
* **Generator:** `pi/storage/install_mount.py` — reads the `storage:` block from `.whiskerframe.yaml`, systemd-escapes the mount path, and renders the unit, expanding `@STORAGE_OPTIONS@` from the btrfs `subvol`/`compress`/`noatime`/`nofail` keys. Defaults to `--dry-run`; `--apply` writes the unit and runs `daemon-reload`. It **never** runs `mkfs`, `mount`, or `enable` — a missing/foreign SSD must not block boot or trigger a destructive action from a tooling run.
* **Config:** `.whiskerframe.example.yaml` carries a `storage:` block (`enabled: false`, `mount_point`, `device_uuid: ""`, `fstype: btrfs`, `subvol: "@data"`, `compress: zstd`). Live values live in the gitignored `.whiskerframe.yaml` (UUID `98bb87d2-7128-470e-91d5-9e117df2ab1a`).
* **Filesystem (reconciled 2026-10-07, DEC-W12).** The SSD is **whole-disk btrfs** (label `cyberdeck-ssd`), superseding the earlier ext4 reformat (DEC-W9). Two subvolumes: **`@data`** (the data mount at `/mnt/250GB-SSD`, `compress=zstd`) and **`@swap`** (holds the memory-safety swapfile, `nodatacow`, uncompressed — CoW is incompatible with swap). Verified live: `findmnt /mnt/250GB-SSD` → btrfs, `compress=zstd:3`, `subvol=/@data`.
* **Gating:** the destructive reformat is **done** (DEC-W9 ext4, then DEC-W12 btrfs) behind the standing model/transport/root pre-wipe guard and explicit operator go-ahead; the generator itself stays dry-run / non-destructive by default. Rationale in `docs/dev/ai-decisions.md` DEC-W7 (template+generator), DEC-W9 (ext4 reformat), and DEC-W12 (btrfs reconciliation).

---

## 3. Orchestration & Multi-Agent Architecture

The goal of this cyberdeck is to serve as an intelligent field tool. To prevent token waste, runaway subshells, or system corruption, agents operate under a **Strict Supervisor / DAG Execution Model**.

```
                   +----------------------------------+
                   |     USER PROMPT / TUI COMMAND    |
                   +-----------------+----------------+
                                     |
                                     v
                   +----------------------------------+
                   |         ORCHESTRATOR AGENT       |
                   |   - Intent Decomposition (DAG)   |
                   |   - Spec Compliance Gatekeeper   |
                   |   - Token & Cost Circuit Breaker |
                   +-----------------+----------------+
                                     |
               +---------------------+---------------------+
               | Sub-Task Spec                             | Sub-Task Spec
               v                                           v
    +----------------------+                    +----------------------+
    |    SYSTEM WORKER     |                    |    NETWORK WORKER    |
    | (Storage/Systemd/OS) |                    |   (Wi-Fi/iwd/SDR)    |
    +----------+-----------+                    +----------+-----------+
               |                                           |
               +---------------------+---------------------+
                                     v
                   +----------------------------------+
                   |     OUTPUT VERIFICATION GATE     |
                   |  - Schema match? Exit code 0?    |
                   |  - System invariants checked?    |
                   +-----------------+----------------+
                                     |
                                     v
                   +----------------------------------+
                   |      SYNTHESIZED USER UPDATE     |
                   +----------------------------------+

```

### 3.1 Task Contract Schema

The Orchestrator must never issue conversational prompts to Worker Agents. Every task fan-out must conform to a typed contract:

```json
{
  "task_id": "SYS-001",
  "target_subsystem": "storage | display | network | telemetry",
  "intent": "Mount the Samsung 250GB SSD cleanly without boot risk.",
  "inputs": {
    "device_node": "/dev/sda1",
    "mount_point": "/mnt/250GB-SSD",
    "fs_type": "ext4"
  },
  "invariants": [
    "Must bind the unit's What= to /dev/disk/by-uuid/<UUID> (via blkid), never a bare /dev/sdX.",
    "Unit must carry Options=nofail and x-systemd.device-timeout=5s so a missing SSD never blocks boot.",
    "Must run 'systemctl daemon-reload' then start the unit and confirm the mount before terminating."
  ],
  "verification_command": "systemctl daemon-reload && systemctl start mnt-250GB\\x2dSSD.mount && findmnt /mnt/250GB-SSD",
  "rollback_procedure": "systemctl disable --now mnt-250GB\\x2dSSD.mount && rm -f /etc/systemd/system/mnt-250GB\\x2dSSD.mount && systemctl daemon-reload"
}

```

### 3.2 Agent Execution Rules & Circuit Breakers

1. **The Sealed Deck Invariant:** Never emit commands assuming physical access. The ESP32 is flashed strictly via the Pi's internal venv esptool. Factory flash backup (`cyd_factory_backup.bin`) is immutable.
2. **Serial Exclusivity Lock:** Any agent interacting with the CYD via esptool or testing direct serial MUST first verify `terminal.service` is stopped (`systemctl stop terminal`).
3. **Terminal Circuit Breaker:** If an agent encounters two consecutive hanging commands or TTY desyncs, it must abort execution and yield to the user rather than spamming carriage returns or spawning zombie subshells.
4. **Secret Sanitization:** When deploying services (Komodo 2.0, API tokens), agents generate random entropy via `openssl rand -hex 32` directly into `.env` files. Agents are strictly forbidden from echoing secrets into stdout, logs, or chat context.
5. **No Ticket IDs in Ansible:** `TSK-XX` ticket identifiers must **never** appear in Ansible task names, tags, role names, or filenames — ticket provenance lives **only** in these markdown tables (Task Matrix + Task & Roadmap Registry). Ansible tags are descriptive (`memory_safety`, `native_services`, `network_automation`), not ticket-numbered.

---

## 4. Immediate Development Backlog

Tasks are ordered strictly by hardware safety and operational priority.

```
[Wave 1: Verification] -> [Wave 2: Storage Core] -> [Wave 3: SD Protection] -> [Wave 4: Container Stack]

```

### Task Matrix

| ID | Title | Target Component | Status | Next Milestone |
| --- | --- | --- | --- | --- |
| **TSK-01** | CYD Terminal Live Login | `pi/terminal/` | `VERIFIED` (DONE) | On-device `bash` login shell verified: CardKB keyboard login (`neko`/`root`) into the blurple shell works on hardware. |
| **TSK-02** | Safe Persistent SSD Mount | `pi/storage/` (template + generator) | `VERIFIED` (DONE) | Mount LIVE on hardware. Reconciled to **btrfs** 2026-10-07 (DEC-W12): `/mnt/250GB-SSD` ← btrfs `@data` subvol, unit UUID-bound to `98bb87d2-7128-470e-91d5-9e117df2ab1a` with `subvol=@data,compress=zstd,noatime,nofail` (`@STORAGE_OPTIONS@` token in the generator) + `device-timeout`. `findmnt` confirms btrfs `compress=zstd:3 subvol=/@data`. UUID/fstype updated in `.whiskerframe.yaml` `storage:` block (old ext4 UUID `a6ca355e-…` dead). **This verification is the Wave 2 trigger.** |
| **TSK-02a** | SSD Reformat NTFS → ext4 → **BTRFS** | `/dev/sda` (Samsung 860 EVO 250GB, USB) | `VERIFIED` (DONE) | Done 2026-10-06 (NTFS→ext4) then **reconciled ext4→btrfs 2026-10-07 (DEC-W12, supersedes the ext4 reformat for the filesystem choice)** per operator directive. Device identified unambiguously by `/dev/disk/by-id/ata-Samsung_SSD_860_EVO_250GB_S4CJNZFN450264M` (single USB SATA disk; SD card `mmcblk0` untouched). Re-used the DEC-W9 pre-wipe guard (model/transport/not-root-or-boot), then `wipefs`+`sgdisk --zap-all`+`mkfs.btrfs -f -L cyberdeck-ssd` whole-disk (no partition table). Subvols `@data` (data) + `@swap` (swapfile, nodatacow). **New UUID `98bb87d2-7128-470e-91d5-9e117df2ab1a`** (old ext4 `a6ca355e-…` dead) fed to TSK-02. |
| **TSK-03** | SD Card Wear Reduction | Host OS / FS | `VERIFIED` (DONE) | Done 2026-10-07 via Ansible (`roles/journald_ssd`): journald `Storage=persistent` + `SystemMaxUse=200M`, `/var/log/journal` symlinked to `/mnt/250GB-SSD/log/journal` (journal on SSD), log2ram installed (azlux repo, arm64/trixie), `/var/log` a 128M tmpfs. Verified: `readlink`, `findmnt`, `systemctl is-active log2ram`. |
| **TSK-04** | Komodo 2.0 Stack Clean Deploy | Docker / Compose | `SHELVED` (hardware-infeasible) | Attempted via Ansible (`roles/komodo`): Docker installed (data-root on SSD) and the stack rendered + pulled, but the full Core+FerretDB+Postgres stack **OOM-thrashed the Pi** (load 14, swap maxed, kernel OOM-kills, docker daemon starved) — `mem_limit` does not prevent swap thrash during Postgres init. 416MB Pi Zero 2W cannot host a DB-backed container stack. Docker purged + 2.1G reclaimed. Superseded by **TSK-07** (native lightweight services). Rationale in DEC-W10. |
| **TSK-05** | Offline Network Automation | `iwd` / Host Network (`ansible/roles/network_automation/`) | `BUILT` (STAGED, not applied) | Role implemented + syntax-checks clean (DEC-W13): **iwd owns wlan0** for client (NetworkManager + wpa_supplicant masked — no two-manager fight), **hostapd/dnsmasq AP fallback** via a single-owner arbiter (never concurrent AP+client on the single radio), PSK/802.1X/open profiles, country PH. **Mandatory lockout rollback guard**: captures known-good state + arms a systemd-timer rollback restoring NetworkManager unless a connectivity sentinel confirms. Defaults `network_automation_apply=false` so a plain run does NOT cut the network on the headless box. **NOT applied this session (lockout risk); wifi creds BLOCKED-ON-OPERATOR.** |
| **TSK-07** | Native Self-Hosted Services + Memory Safety | Host OS / systemd (`ansible/roles/memory_safety/`, `ansible/roles/native_services/`) | `DEPLOYED` (PARTIAL) | Supersedes TSK-04 on the Pi. **Deployed + verified live 2026-10-07.** `memory_safety` (btrfs-aware, DEC-W12): 512MB swapfile via `btrfs filesystem mkswapfile` on the `@swap` subvol (`nodatacow`, 0600, fstab `pri=10 nofail`), **adopts** the Pi's native zram (`zram0` pri=100 > swapfile pri=10) instead of installing a conflicting second manager, `vm.swappiness=15`/`vfs_cache_pressure=60`, earlyoom (`-m 8 -s 8`); never swaps on the SD card. `native_services`: **syncthing@neko** (as `neko`, MemoryMax=200M, GUI 127.0.0.1:8384), **filebrowser** (native pinned v2.31.2, as `neko`, MemoryMax=128M, HTTP 200 on 127.0.0.1:8080), **netbird** (active, MemoryMax=150M, `NeedsLogin` → **BLOCKED-ON-OPERATOR**, no setup key invented), **git** (dedicated acct + `/usr/bin/git-shell`, bare repos on SSD, `authorized_keys` empty → **BLOCKED-ON-OPERATOR**, no pubkey invented). Rationale in DEC-W11 (design) + DEC-W12 (btrfs/zram). |
| **TSK-06** | Named Theme-File Switching | `pi/terminal/theme.py` | `VERIFIED` (DONE) | `terminal.theme_file` loader added (2026-10-06): a named JSON theme under `assets/themes/` overrides the inline `theme` block; missing/invalid/escape-attempt falls back to inline then baked-in palette. Verified loading all three themes (piiiiink-a11y, amber-crt, ice-cyan) + 3 fallback cases. Path confined to `assets/themes/` (no arbitrary reads). Example snippet added to `.whiskerframe.example.yaml`. |

### Task & Roadmap Registry

A glossary mapping every `TSK-XX` ticket to its description, current status, and the exact related files. This is the single lookup table for ticket provenance; the Task Matrix above is the prioritized backlog view.

| Ticket | Description | Status | Related files |
| --- | --- | --- | --- |
| **TSK-01** | CYD terminal live login — a real `bash -l` shell rendered on the CYD, typed on the CardKB, gated by splash + PAM login. | `VERIFIED` / DONE — on-device bash login (`neko`/`root`) confirmed working. | `pi/terminal/bridge.py`, `pi/terminal/daemon.py`, `pi/terminal/login.py`, `pi/terminal/login_view.py`, `pi/terminal/splash.py`, `pi/terminal/grid.py`, `pi/terminal/vt.py`, `pi/terminal/theme.py`, `pi/terminal/terminal.service`, `pi/terminal/install.sh`, `scripts/convert_splash.py` |
| **TSK-02** | Safe persistent SSD mount via a systemd `.mount` unit (`nofail`, device-timeout, UUID-bound). | `VERIFIED` / DONE — unit generated + applied + enabled on the Pi; reconciled to **btrfs** 2026-10-07 (DEC-W12), `findmnt` confirms `/mnt/250GB-SSD` ← btrfs `compress=zstd:3 subvol=/@data`, UUID `98bb87d2-…`. | `pi/storage/storage.mount.example` (now with `@STORAGE_OPTIONS@`), `pi/storage/install_mount.py`, `.whiskerframe.example.yaml` (`storage:` block, `fstype: btrfs`), `.whiskerframe.yaml` (live `storage:` with btrfs UUID/subvol/compress) |
| **TSK-02a** | SSD reformat NTFS → ext4 → **btrfs** (POSIX semantics; then subvolumes + zstd compression per operator directive). | `VERIFIED` / DONE — NTFS→ext4 2026-10-06, then **reconciled ext4→btrfs 2026-10-07 (DEC-W12, supersedes the ext4 reformat for the FS choice)**; device unambiguous via `/dev/disk/by-id/ata-Samsung_SSD_860_EVO_250GB_S4CJNZFN450264M`, DEC-W9 pre-wipe guard re-used, whole-disk `mkfs.btrfs` with subvols `@data`/`@swap`; new UUID `98bb87d2-…` feeds TSK-02. | (manual, human-gated; executed on the Pi), DEC-W9, DEC-W12 |
| **TSK-03** | SD card wear reduction (log2ram/tmpfs buffers; divert persistent journald to the ext4 SSD). | `VERIFIED` / DONE via Ansible `roles/journald_ssd`. | `ansible/roles/journald_ssd/` (tasks, handlers, defaults), `/etc/systemd/journald.conf` + `/etc/log2ram.conf` on the Pi |
| **TSK-04** | Komodo 2.0 + FerretDB clean deploy via Docker Compose. | `SHELVED` — hardware-infeasible on the 416MB Pi (full stack OOM-thrashed; Docker purged). The Ansible role is kept for deploying Komodo on a bigger box later. Superseded by TSK-07. | `ansible/roles/komodo/` (retained but not run on the Pi), DEC-W10 |
| **TSK-07** | Native self-hosted services (git bare/SSH, Netbird, Syncthing, File Browser as binaries) + memory-safety layer (SSD swapfile low-prio, zram high-prio, swappiness ~10-20, earlyoom, per-unit MemoryMax). | `DEPLOYED` (PARTIAL) — both roles **deployed + verified live on the Pi 2026-10-07**; `memory_safety` btrfs-aware (DEC-W12: `mkswapfile` on `@swap` nodatacow, adopts native zram); `native_services` syncthing@neko + filebrowser (as `neko`) verified, netbird `NeedsLogin` + git `authorized_keys` empty → BLOCKED-ON-OPERATOR. Rationale DEC-W11 + DEC-W12. | `ansible/roles/memory_safety/` (tasks, handlers, defaults), `ansible/roles/native_services/` (tasks, handlers, defaults), `ansible/site.yml` (tags `memory_safety`, `native_services`), `ansible/requirements.yml` (`ansible.posix>=1.5.0`) |
| **TSK-05** | Offline network automation — Wi-Fi client at reserved `${PI_HOST}` when a known network is present, self-hosted AP fallback (hostapd/dnsmasq) when none is; all services offline-tolerant. | `BUILT` (STAGED, not applied) — role implemented + syntax-checks clean (DEC-W13): iwd owns wlan0 (NetworkManager + wpa_supplicant masked), hostapd/dnsmasq AP fallback via single-owner arbiter, lockout rollback guard, `network_automation_apply=false` default. Deployment deferred by design (lockout risk on the headless box); wifi creds BLOCKED-ON-OPERATOR. | `ansible/roles/network_automation/` (tasks, handlers, defaults, templates), `ansible/site.yml`, DEC-W13 |
| **TSK-06** | Named theme-file switching — load a named JSON theme via a `terminal.theme_file` key, falling back to the inline `terminal.theme` block. | `VERIFIED` / DONE — loader added, path-confined to `assets/themes/`, all 3 themes + fallbacks tested; example snippet added. | `pi/terminal/theme.py`, `assets/themes/` (`piiiiink-a11y.json`, `amber-crt.json`, `ice-cyan.json`), `.whiskerframe.example.yaml` |

---

## 5. Standard Operating Procedures (SOPs)

### 5.1 Remote Deployment & Wheel Sync

```bash
# Infra params (PI_HOST / PI_USER / DEFAULT_KEY_PATH) are sourced from .env.
# 1. Sync workspace to Pi (excluding build artifacts and local caches)
rsync -a --exclude-from=pi/deploy-exclude.txt -e "ssh -i ${DEFAULT_KEY_PATH}" ./ ${PI_USER}@${PI_HOST}:/opt/cyd-display-link/

# 2. Reinstall whiskerframe wheel into Pi runtime environment
ssh -i ${DEFAULT_KEY_PATH} ${PI_USER}@${PI_HOST} "cd /opt/cyd-display-link/pi && uv pip install --reinstall-package whiskerframe ."

```

### 5.2 Safe CYD Reflashing (Via Pi Bridge)

```bash
# 1. Build binary locally
uvx --from platformio pio run -d firmware/cyd_display_link

# 2. Stop terminal service to free /dev/ttyUSB0
ssh -i ${DEFAULT_KEY_PATH} ${PI_USER}@${PI_HOST} "systemctl stop terminal && fuser -k /dev/ttyUSB0 || true"

# 3. Execute flash write from Pi venv
ssh -i ${DEFAULT_KEY_PATH} ${PI_USER}@${PI_HOST} "/opt/cyd-display-link/pi/.venv/bin/python -m esptool --chip esp32 --port /dev/serial/by-id/usb-1a86_USB_Serial-if00-port0 --baud 460800 --before default-reset --after hard-reset write-flash -z 0x10000 /opt/cyd-flash/firmware.bin"

# 4. Resume terminal service
ssh -i ${DEFAULT_KEY_PATH} ${PI_USER}@${PI_HOST} "systemctl start terminal"

```