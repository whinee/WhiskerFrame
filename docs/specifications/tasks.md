## 4. Immediate Development Backlog

Tasks are ordered strictly by hardware safety and operational priority.

```text
[Wave 1: Verification] -> [Wave 2: Storage Core] -> [Wave 3: SD Protection] -> [Wave 4: Container Stack]
```

### Task Matrix

A glossary mapping every `TSK-XX` ticket to its description, current status, and the exact related files. This is the single lookup table for ticket provenance.

| Ticket | Description | Status | Related files |
| --- | --- | --- | --- |
| **TSK-01** | CYD terminal live login — a real `bash -l` shell rendered on the CYD, typed on the CardKB, gated by splash + PAM login. | `VERIFIED` / DONE — on-device bash login (`neko`/`root`) confirmed working. | `pi/terminal/bridge.py`, `pi/terminal/daemon.py`, `pi/terminal/login.py`, `pi/terminal/login_view.py`, `pi/terminal/splash.py`, `pi/terminal/grid.py`, `pi/terminal/vt.py`, `pi/terminal/theme.py`, `pi/terminal/terminal.service`, `pi/terminal/install.sh`, `scripts/convert_splash.py` |
| **TSK-02** | Safe persistent SSD mount via a systemd `.mount` unit (`nofail`, device-timeout, UUID-bound). | `VERIFIED` / DONE — unit generated + applied + enabled on the Pi; reconciled to **btrfs** 2026-10-07 (DEC-W12), `findmnt` confirms `/mnt/250GB-SSD` ← btrfs `compress=zstd:3 subvol=/@data`, UUID `98bb87d2-…`. | `pi/storage/storage.mount.example` (now with `@STORAGE_OPTIONS@`), `pi/storage/install_mount.py`, `.whiskerframe.example.yaml` (`storage:` block, `fstype: btrfs`), `.whiskerframe.yaml` (live `storage:` with btrfs UUID/subvol/compress) |
| **TSK-02a** | SSD reformat NTFS → ext4 → **btrfs** (POSIX semantics; then subvolumes + zstd compression per operator directive). | `VERIFIED` / DONE — NTFS→ext4 2026-10-06, then **reconciled ext4→btrfs 2026-10-07 (DEC-W12, supersedes the ext4 reformat for the FS choice)**; device unambiguous via `/dev/disk/by-id/ata-...`, DEC-W9 pre-wipe guard re-used, whole-disk `mkfs.btrfs` with subvols `@data`/`@swap`; new UUID `98bb87d2-…` feeds TSK-02. | (manual, human-gated; executed on the Pi), DEC-W9, DEC-W12 |
| **TSK-03** | SD card wear reduction (log2ram/tmpfs buffers; divert persistent journald to the SSD). | `VERIFIED` / DONE via Ansible `roles/journald_ssd`. | `ansible/roles/journald_ssd/` (tasks, handlers, defaults), `/etc/systemd/journald.conf` + `/etc/log2ram.conf` on the Pi |
| **TSK-04** | Komodo 2.0 + FerretDB clean deploy via Docker Compose. | `SHELVED` — hardware-infeasible on the 416MB Pi (full stack OOM-thrashed; Docker purged). The Ansible role is kept for deploying Komodo on a bigger box later. Superseded by TSK-07. | `ansible/roles/komodo/` (retained but not run on the Pi), DEC-W10 |
| **TSK-07** | Native self-hosted services (git bare/SSH, Netbird, Syncthing, File Browser as binaries) + memory-safety layer (SSD swapfile low-prio, zram high-prio, swappiness ~10-20, earlyoom, per-unit MemoryMax). | `DEPLOYED` (PARTIAL) — both roles **deployed + verified live on the Pi 2026-10-07**; `memory_safety` btrfs-aware (DEC-W12: `mkswapfile` on `@swap` nodatacow, adopts native zram); `native_services` syncthing@neko + filebrowser (as `neko`) verified, netbird `NeedsLogin` + git `authorized_keys` empty → BLOCKED-ON-OPERATOR. Rationale DEC-W11 + DEC-W12. | `ansible/roles/memory_safety/`, `ansible/roles/native_services/`, `ansible/site.yml`, `ansible/requirements.yml` |
| **TSK-05** | Offline network automation — Wi-Fi client at reserved `${PI_HOST}` when a known network is present, self-hosted AP fallback (hostapd/dnsmasq) when none is; all services offline-tolerant. | `BUILT` (STAGED, not applied) — role implemented + syntax-checks clean (DEC-W13): iwd owns wlan0, hostapd/dnsmasq AP fallback via single-owner arbiter, lockout rollback guard, `network_automation_apply=false` default. Deployment deferred by design (lockout risk on the headless box); wifi creds BLOCKED-ON-OPERATOR. | `ansible/roles/network_automation/` (tasks, handlers, defaults, templates), `ansible/site.yml`, DEC-W13 |
| **TSK-06** | Named theme-file switching — load a named JSON theme via a `terminal.theme_file` key, falling back to the inline `terminal.theme` block. | `VERIFIED` / DONE — loader added, path-confined to `assets/themes/`, all 3 themes + fallbacks tested; example snippet added. | `pi/terminal/theme.py`, `assets/themes/`, `.whiskerframe.example.yaml` |
