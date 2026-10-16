# Domain 08: Compute, OS, Memory Safety & Containment (REQ-OPS)

**Specification Prefix:** `REQ-OPS`  
**System Layer:** Operating System, Memory Isolation, Cgroups & Multi-Tenant Sandbox  
**Primary Implementations:** `pi/terminal/login.py`, `ansible/roles/guest_demo/`, `/usr/local/bin/cyberdeck-net-heal.sh`  
**Acceptance Test Plans:** `ATP-04-SEC-GUEST-CONTAINMENT`, `ATP-01-TERM-LOGIN`, `ATP-08-NET-SELF-HEAL`  
**Target Milestone:** `v0` (Demo Prototype) / `v1` (Field Hardened)  

---

## 1. Scope & Domain Objectives

The Compute, OS, Memory Safety & Containment domain establishes the host operating system configuration, memory bounds protecting the 416 MB RAM ceiling, automated systemd service management, network self-healing watchdogs, clock monotonicity, and the hardened guest demo sandbox. It guarantees that the cyberdeck remains stable, responsive, and secure against both accidental memory exhaustion and intentional public adversarial exploitation.

---

## 2. Formal Requirements & Normative Specifications

### REQ-OPS-01 [v0]: Strict Lightweight Native Services
- **Requirement:** The host OS MUST NOT run container runtimes (Docker, Podman, LXC) or heavy database engines (Postgres, FerretDB) to remain within the 416 MB RAM envelope; all services run as native systemd units.
- **Rationale:** Container engines consume 150+ MB of RAM just for daemons; running them on a 416 MB Pi Zero 2W triggers constant swap thrashing and kernel freezing.
- **Traceability:** Section 6.03, `DEC-W10`, `TSK-07`.

### REQ-OPS-02 [v0]: Memory Safety Floor & Cgroup Bounds
- **Requirement:** The system MUST enforce a 50 MB minimum free-RAM safety floor. Background daemons MUST be bounded by systemd `MemoryMax=` directives, with `earlyoom` configured to terminate non-critical processes before swap thrashing triggers kernel panic.
- **Rationale:** Preserves system interactivity under sudden memory pressure.
- **Traceability:** Section 6.05, `DEC-W11`, `TSK-07`.

### REQ-OPS-03 [v1]: Hardware Watchdog Supervision
- **Requirement:** The BCM2835 hardware watchdog (`/dev/watchdog0`) MUST be pet continuously by systemd (`RuntimeWatchdogSec=60s`), forcing an automatic board reset if the Linux kernel deadlocks.
- **Rationale:** Ensures unattended self-recovery if the kernel encounters a hard hang.
- **Traceability:** Section 6.10, `DEC-W26`, `TSK-09`.

### REQ-OPS-04 [v0]: Multi-Tenant Hardened Guest Demo Sandbox
- **Requirement:** The system MUST provide an unprivileged `guest` account (password: `guest`) engineered for public hands-on demonstration under the assumption of arbitrary adversarial code execution:
  1. **Authentication Gate:** `guest` MUST NOT possess `sudo` rights or auxiliary groups; MUST be blocked in `sshd` (`DenyUsers guest`), `su`, and console ttys; and MUST authenticate strictly via the CYD `terminal` PAM service.
  2. **Kernel Network Isolation:** Outbound network traffic from UID `guest` MUST be dropped at the kernel netfilter layer via `/etc/nftables.d/guest_isolation.nft` (`skuid "guest" counter drop`), severing loopback (`127.0.0.1`), LAN, and WAN egress.
  3. **Resource & Cgroup Ceilings:** Resource consumption MUST be bounded via systemd slice limits (`MemoryMax=64M`, `TasksMax=30`, `CPUQuota=50%`), disabling core dumps and limiting open file descriptors.
  4. **5-Second Process Reaper:** A background supervisor (`cyberdeck-guest-reaper.service`) MUST poll every second and issue `SIGKILL` to any process owned by `guest` (excluding the interactive login shell `bash -l`) exceeding 5.0 seconds of elapsed execution time.
  5. **Ephemeral In-Memory Home Directory:** The `guest` home directory MUST reside on an 8MB `tmpfs` volume, automatically wiped and re-populated from `/etc/skel` upon session logout via PAM `pam_exec.so`. `guest` MUST NOT have read access to `/home/neko`, `/root`, `/mnt/250GB-SSD`, or network credentials.
  6. **Restricted Shell Environment:** `guest` MUST NOT be permitted to execute system poweroff/reboot via polkit or logind, and shell prompt MUST render as `g~ `.
- **Rationale:** Allows complete strangers to test the cyberdeck at public conferences and demo days with zero risk of malware persistence, network attacks, or filesystem tampering.
- **Traceability:** `DEC-W27`, `TSK-10`, `ATP-04-SEC-GUEST-CONTAINMENT`.

### REQ-OPS-05 [v0]: System Configuration & Locales
- **Requirement:** System configuration defaults MUST standardize on UTC+0 and American English (`en_US.UTF-8`), configurable via `.whiskerframe.yaml`.
- **Rationale:** Eliminates character encoding mismatches and timestamp ambiguities across time zones.
- **Traceability:** Section 6.11.

### REQ-OPS-06 [v1]: Declarative Dotfile Synchronization
- **Requirement:** The environment MUST support automated configuration management (via Ansible or chezmoi) to maintain parity with the operator's primary workstation dotfiles.
- **Rationale:** Operator workflows, aliases, and tools stay synchronized without manual file copying.
- **Traceability:** Section 6.12, `DEC-W14`.

### REQ-OPS-07 [v0]: PAM Login & PTY Bridge
- **Requirement:** Terminal authentication MUST use standard Linux PAM services (`simplepam`) to spawn isolated PTY sessions for `root`, `neko`, or `guest`, rendering a demo banner when `terminal.login.demo_mode` is enabled.
- **Rationale:** Enforces robust Linux user isolation and credential checking for all terminal access.
- **Traceability:** `DEC-W29`, `TSK-11`.

### REQ-OPS-08 [v0]: Clock Monotonicity via `fake-hwclock`
- **Requirement:** In the absence of a hardware RTC in `v0`, the OS MUST utilize `fake-hwclock` to save and restore timestamps on boot and shutdown, preventing the system clock from regressing to the 1970 UNIX epoch.
- **Rationale:** Protects file modification times and log sequences from epoch collapse.
- **Traceability:** `DEC-W26`, `TSK-09`.

### REQ-OPS-09 [v0]: 3-Tier Self-Healing Network Watchdog
- **Requirement:** The system MUST run `/usr/local/bin/cyberdeck-net-heal.sh` every 30 seconds via systemd timer to detect gateway ping failure. Escalation MUST proceed through Tier 1 (`rfkill unblock wifi` + reconnect), Tier 2 (restart NetworkManager after 5m), and Tier 3 (reload kernel module `brcmfmac` after 15m), and MUST NEVER issue a system reboot.
- **Rationale:** Automatically recovers from Wi-Fi driver lockups without disrupting the active operator session.
- **Traceability:** `DEC-W26`, `TSK-09`, `ATP-08-NET-SELF-HEAL`.

---

## 3. Actual Implementation Architecture

### 3.1 Hardened Guest Sandbox (`ansible/roles/guest_demo/`)
- **Tmpfs Setup:** `/home/guest` is mounted via `/etc/fstab` as `tmpfs size=8M,mode=0700,uid=guest,gid=guest`.
- **Logout Wipe:** `/etc/pam.d/terminal` includes:
  ```text
  session post-login /usr/local/bin/cyberdeck-guest-session.sh
  session post-logout /usr/local/bin/cyberdeck-guest-session.sh
  ```
  On logout, the script issues `rm -rf /home/guest/* /home/guest/.*` and copies clean files from `/etc/skel`.
- **Process Reaper:** `cyberdeck-guest-reaper.service` runs `pi/bin/guest_reaper.py` polling `/proc` every 1.0 second.

### 3.2 Systemd Resource Slices
Configured in `/etc/systemd/system/user-guest.slice`:
```ini
[Unit]
Description=Guest Sandbox User Slice
Before=slices.target

[Slice]
MemoryMax=64M
TasksMax=30
CPUQuota=50%
```

### 3.3 3-Tier Network Self-Heal (`/usr/local/bin/cyberdeck-net-heal.sh`)
```bash
# Tier 1 (0-5 min of failure):
rfkill unblock wifi
nmcli device wifi connect "$LAST_SSID"

# Tier 2 (5-15 min of failure):
systemctl restart NetworkManager

# Tier 3 (>15 min of failure):
modprobe -r brcmfmac
sleep 2
modprobe brcmfmac
```

---

## 4. Verification & Acceptance Criteria

- **`ATP-04-SEC-GUEST-CONTAINMENT`:** Validates tmpfs wipe, process reaper SIGKILL after 5.0s, nftables drop of outbound packets, and rejection of SSH/console access.
- **`ATP-01-TERM-LOGIN`:** Validates PAM authentication for `neko` and `guest`.
- **`ATP-08-NET-SELF-HEAL`:** Validates 3-tier escalation progression without triggering system reboot.
