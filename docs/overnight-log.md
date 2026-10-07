# Overnight Autonomous Session Log — 2026-10-07

Operator asleep. Full autonomy on Pi (Zero 2W, 416MB) + external SSD. Contents
disposable. Dev host / remote git / secrets / keys are OFF LIMITS.

Running log of every action, decision, and failure. Newest at bottom.

---

## Ground facts (07:33, read-only on Pi 10.0.0.212)

- **SSD identity (unambiguous):** `/dev/disk/by-id/ata-Samsung_SSD_860_EVO_250GB_S4CJNZFN450264M` → `/dev/sda`, 232.9G, USB, Samsung SSD 860 EVO 250GB. Also `usb-...` and `wwn-0x5002538ec04d5358` aliases. Exactly one SATA disk → not ambiguous.
- **Current SSD fs:** `sda1` ext4, LABEL `cyberdeck-ssd`, UUID `a6ca355e-8854-4440-b4ef-113e3b44287d`, mounted `/mnt/250GB-SSD`.
- **SD card (OFF LIMITS):** `mmcblk0` 59.5G — `p1` /boot/firmware vfat, `p2` / ext4. Never touch.
- **Swap:** zram0 416M pri=100 live (148M used); no SSD swapfile yet.
- **Mem:** 416MB total, ~105 free + 164 buff/cache.
- **btrfs-progs:** NOT installed on the Pi.
- **Radio:** single phy0, `wlan0` managed, connected. Country=PH. BT soft-blocked.
- **Network owner (current):** NetworkManager active + wpa_supplicant active; iwd inactive; systemd-networkd/dhcpcd/hostapd/dnsmasq inactive.

### Decision: SSD reformat ext4 → BTRFS is authorized
Operator ordered it; SSD contents disposable. Device identity confirmed by-id +
single-disk + model/size match. SD card is a different device (mmcblk0). Proceed.

## 07:38 — SSD reformatted to BTRFS (DONE)
- Installed `btrfs-progs` on the Pi.
- Guard passed (model=Samsung SSD 860 EVO, tran=usb, root not on \$DEV, boot not on \$DEV).
- `wipefs -a` + `sgdisk --zap-all` + `mkfs.btrfs -f -L cyberdeck-ssd` whole-disk (no partition table).
- **New BTRFS UUID: `98bb87d2-7128-470e-91d5-9e117df2ab1a`** (was ext4 `a6ca355e-...`).
- Subvolumes created: `@data` (id 256), `@swap` (id 257).

## 07:40 — Fan-out plan (parallel subagents)
- **wlan0 owner DECISION (orchestrator, now):** `iwd` owns wlan0 for client mode.
  NetworkManager + wpa_supplicant currently own it and MUST be disabled by the role
  (no two managers fighting). `hostapd`+`dnsmasq` bind wlan0 ONLY as AP fallback when
  iwd finds no known network — mutually exclusive, single radio. → DEC-W13.
- Spawned subagents (disjoint file ownership; Pi apt/format/deploy stays with orchestrator):
  - **B** memory_safety BTRFS rewrite — owns `ansible/roles/memory_safety/*`
  - **C** network_automation build (TSK-05) — owns `ansible/roles/network_automation/*`
  - **D** docs triad + DEC-W12/W13 + spec + changelog — owns `docs/*` (waits on A/B/C facts)
- Orchestrator does inline: generator+config (A), all Pi-side apt/deploy, verification.



## 07:46 — Subagent results (orchestrator-verified)
- **A (inline):** `pi/storage/install_mount.py` + template now emit btrfs opts
  (`subvol=@data,compress=zstd,noatime,nofail`). `.whiskerframe.yaml` storage →
  btrfs, UUID `98bb87d2-...`, subvol `@data`. Example updated.
- **B memory_safety (PASS, verified):** btrfs-correct. `btrfs filesystem mkswapfile
  --size 512M --uuid clear` on `@swap` subvol mounted at `/swap`
  (`noatime,subvol=@swap,nofail`), chattr +C belt-and-suspenders, 0600, fstab
  pri=10 nofail, swapon pri=10 (under zram pri=100). Asserts SSD is btrfs; SD-card
  guard kept. btrfs-progs added to apt. zram/sysctl/earlyoom preserved.
- **C network_automation (PASS, verified):** iwd owns wlan0 (NM+wpa_supplicant
  masked), hostapd/dnsmasq AP fallback via single-owner arbiter (never concurrent),
  PSK/802.1X/open profiles (empty by default → BLOCKED-ON-OPERATOR for creds),
  mandatory lockout rollback (systemd timer restores NM unless sentinel confirmed
  in 10min). **STAGED: `network_automation_apply=false`** in site.yml — plain run
  does NOT cut network. site.yml re-enabled safely.
- **Verification:** orchestrator ran `ansible-playbook --syntax-check site.yml` →
  RC=0, zero errors. Both roles read + confirmed correct.

## 07:49–08:05 — Deploy to Pi (DONE, verified)
### BTRFS mount
- Synced storage files + `.whiskerframe.yaml`; `install_mount.py --apply` rendered
  btrfs unit (`subvol=@data,compress=zstd,noatime,nofail`), enabled + mounted.
- Verified: `findmnt /mnt/250GB-SSD` → btrfs, compress=zstd:3, subvol=/@data, writable.

### memory_safety (RC=0, idempotent)
- Fixed 3 issues found on live apply (diagnosed root causes, not patched blindly):
  1. **zram two-manager conflict** — RPi OS already runs native
     `systemd-zram-setup@zram0` (zstd, pri=100). Installing zram-tools created a
     2nd manager that failed on the busy device. FIX: role now DETECTS an active
     zram swap and ADOPTS it, only installing zram-tools when none exists. Purged
     the conflicting zram-tools from the Pi.
  2. **swapon not idempotent** — rc 255 "Device or resource busy" on 2nd run.
     FIX: `failed_when` now also tolerates "busy".
  3. (check-mode chmod artifact — expected, not a real bug.)
- Verified live: swap = zram0 **pri=100** > /swap/swapfile **pri=10**; swapfile on
  btrfs **@swap** subvol, **nodatacow** (lsattr `C`), 0600; vm.swappiness=15,
  vfs_cache_pressure=60; earlyoom active with -m8 -s8 prefer/avoid.

### native_services (RC=0)
- Fixed: service user defaulted to `ansible_user`=root (wrong). syncthing refuses
  root; filebrowser ran as root then crash-looped on a root-owned db after the fix.
  FIX: default syncthing_user/filebrowser_user = `neko`; added `recurse: true` to
  the filebrowser dir so a stale root-owned db gets re-owned. Removed the stale db.
- Verified live:
  - **syncthing@neko** active as neko, MemoryMax=200M, GUI 127.0.0.1:8384 (loopback).
  - **filebrowser** active as neko, MemoryMax=128M, HTTP 200 on 127.0.0.1:8080, db neko-owned.
  - **netbird** active, MemoryMax=150M, status `NeedsLogin` → **BLOCKED-ON-OPERATOR** (no setup key).
  - **git** account (uid 997, /usr/bin/git-shell), repos dir on SSD, authorized_keys
    empty → **BLOCKED-ON-OPERATOR** (no operator SSH pubkey).
- Final idempotency re-run: ok=46 changed=1 failed=0.

### network_automation
- NOT applied (STAGED, apply=false) — lockout risk on headless box. Role present,
  packages NOT installed (staged tasks are gated). Will apply only with operator
  present + rollback understood. BLOCKED-ON-OPERATOR for wifi creds.

## 08:10 — Session complete
Docs triad synced (DEC-W12, DEC-W13, spec TSK-02/02a/05/07, changelog) +
docs/morning-report.md created. All orchestrator-verified.

LOOP EXHAUSTED. Remaining work is all BLOCKED-ON-OPERATOR (needs human secrets/
decisions, nothing autonomous left):
- git `authorized_keys` — operator SSH pubkey.
- netbird — setup key or interactive `netbird up` (SSO).
- network_automation apply — operator present + wifi creds (PSK/802.1X); lockout risk.
No critical autonomous tasks remain. Stopping per budget/stop-rules.
