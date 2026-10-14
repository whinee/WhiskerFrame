# Offline Library & Knowledge Base Architecture (WS-5)

## 1. Executive Summary & Hardware Envelope

The Whiskerframe Cyberdeck operates as an off-grid, field-deployable companion capable of comprehensive technical reference, system administration, and public demonstration without relying on active internet access or cloud services.

### Hardware Envelope & System Constraints

| Subsystem | Specification / Limit | Architectural Impact |
| --- | --- | --- |
| **Compute / SoC** | Broadcom BCM2710A1 quad-core Cortex-A53 @ 1GHz | Passive heatsink dissipation; high thermal sensitivity under sustained network or CPU loads. |
| **System RAM** | **~416 MB usable RAM** ceiling (Debian 13 trixie, arm64) | Absolute prohibition of heavy DB stacks or container runtimes (Komodo/FerretDB/Postgres OOM-thrash the host per `pi-zero-2w-ram-ceiling.md`). Services must be native lightweight static binaries with strict cgroup `MemoryMax` bounds. |
| **Storage Subsystem** | Samsung 860 EVO 250 GB SATA SSD over internal USB-SATA bridge | Mounted persistently at `/mnt/250GB-SSD` formatted with **BTRFS**. Ample storage (>240 GB available) for offline corpora, but write caching and compression must be tuned for RAM conservation. |
| **Display Subsystem** | 320x240 ESP32 Cheap Yellow Display (CYD) | Terminal character grid operates at **53 columns x 30 rows** (Font Size 1, 6x8 cell metrics). All reader and query outputs must conform to <=53 columns without line-wrapping artifacts. |
| **Power & Battery** | Waveshare 3S 18650 UPS module (9-12.6V pack) | Sustained Wi-Fi or CPU loads shorten field battery runtime and raise internal chassis thermals. |

---

## 2. Core Offline System Documentation (v0 Baseline)

The baseline offline documentation provides immediate, zero-daemon references via standard POSIX and GNU toolchains installed directly to the OS filesystem:

### 2.1 Essential Debian Packages

```bash
sudo apt-get update && sudo apt-get install -y \
  man-db \
  manpages \
  manpages-dev \
  bash-doc \
  python3-doc \
  w3m \
  lynx
```

### 2.2 Text Browsers & Display Geometry

The Cyberdeck uses text-based browsers for reading local HTML documentation and querying HTTP daemon endpoints:
- **`w3m`**: Primary text browser and dump renderer. Invoked in dump mode with explicit width targeting the CYD panel:
  ```bash
  w3m -dump -cols 53 /usr/share/doc/python3/html/index.html
  ```
- **`lynx`**: Secondary lightweight text browser for interactive browsing:
  ```bash
  lynx -width=53 /usr/share/doc/bash/bashref.html
  ```

### 2.3 Terminal Man-Page Formatting

To prevent horizontal clipping on the 53-column CYD display, man-db pagination is constrained via environment variables in `/etc/profile.d/cyberdeck-pager.sh`:

```bash
export MANWIDTH=53
export PAGER="less -r -w -E"
```

---

## 3. Kiwix ZIM Knowledge Base Architecture (v1)

### 3.1 Overview of ZIM & Kiwix

The open **ZIM** (Zeno IMproved) format stores compressed, indexed wiki and documentation trees (HTML, CSS, metadata, and compressed webp/jpeg assets) using internal LZMA or Zstandard compression. The `kiwix-serve` daemon reads ZIM files directly without decompressing the entire archive into memory, allowing multi-gigabyte corpora to be served within minimal RAM footprints.

### 3.2 Planned Datasets & Scope

| Dataset | Archive Filename Pattern | Size | Scope & Rationale |
| --- | --- | --- | --- |
| **Simple English Wikipedia** | `wikipedia_en_simple_all_maxi_*.zim` | ~1.0 – 1.2 GB | Comprehensive general knowledge written in accessible English; includes thumbnail graphics; ideal demonstration corpus. |
| **ArchWiki** | `archlinux_en_all_*.zim` | ~200 MB | Gold-standard Linux systems, networking, hardware, and security reference. |
| **Stack Exchange: InfoSec** | `security.stackexchange.com_en_all_*.zim` | ~400 MB | Penetration testing, cryptography, defensive operations, protocol analysis. |
| **Stack Exchange: Unix & Linux** | `unix.stackexchange.com_en_all_*.zim` | ~1.1 GB | Shell scripting, system administration, kernel tuning, troubleshooting. |
| **Total Corpus Footprint** | — | **~2.8 GB** | Consumes <1.2% of the 250 GB SSD; leaves over 240 GB available. |

### 3.3 Strict Download Prohibition for Tonight

> **PROHIBITION:** Do **NOT** attempt to download full English Wikipedia (`wikipedia_en_all_nopic_*.zim` ~40 GB, or `wikipedia_en_all_maxi_*.zim` ~100 GB) tonight directly over the Raspberry Pi Wi-Fi.

#### Rationale:
1. **Thermal & Radio Saturation:** Continuous Wi-Fi reception of 40–100 GB on the Pi Zero 2W single-band 2.4GHz radio takes 12–28 hours, causing continuous SoC temperature spikes (>70°C) without active cooling, risking thermal throttling.
2. **Memory Buffer Exhaustion:** Large direct downloads on 416 MB RAM lead to socket buffer memory pressure and I/O thrashing.
3. **Power Drain:** Continuous download depletes the 3S UPS pack during field prep.

### 3.4 Staged Download & Rsync Deployment Procedure

All ZIM archives must be acquired on the developer workstation and transferred to the Cyberdeck via bandwidth-limited rsync.

#### Step 1: Workstation Download & Checksum Verification
```bash
# On Developer Workstation (fast connection):
mkdir -p ~/cyberdeck-zim && cd ~/cyberdeck-zim

# Example: Download Simple Wikipedia and ArchWiki
wget https://download.kiwix.org/zim/wikipedia/wikipedia_en_simple_all_maxi_2024-05.zim
wget https://download.kiwix.org/zim/wikipedia/wikipedia_en_simple_all_maxi_2024-05.zim.sha256
wget https://download.kiwix.org/zim/other/archlinux_en_all_maxi_2024-05.zim
wget https://download.kiwix.org/zim/other/archlinux_en_all_maxi_2024-05.zim.sha256

# Verify cryptographic integrity:
sha256sum -c *.sha256
```

#### Step 2: Bandwidth-Limited Transfer to Cyberdeck
To prevent Pi Wi-Fi saturation and thermal elevation, throttle transfer to 5 MB/s (`--bwlimit=5M`):

```bash
# On Developer Workstation:
rsync -avP --bwlimit=5M \
  -e "ssh -i ~/.ssh/id_ed25519" \
  ~/cyberdeck-zim/*.zim \
  neko@10.0.0.212:/mnt/250GB-SSD/kiwix/
```

### 3.5 Storage Location & BTRFS Optimization

All ZIM archives reside on the dedicated SSD path:
```bash
/mnt/250GB-SSD/kiwix/
```

#### Filesystem Compression Optimization (NOCOW / No Compression)
Because ZIM archives are already internally compressed with high-ratio Zstandard or LZMA algorithms, enabling filesystem-level compression (e.g. BTRFS `compress=zstd`) on this directory offers **0% space reduction** while introducing severe performance penalties:
- Every read causes redundant CPU decompression overhead on Cortex-A53 cores.
- Decompression buffers consume critical RAM within the 416 MB envelope.

Disable BTRFS compression on the Kiwix directory:

```bash
# Ensure directory exists:
sudo mkdir -p /mnt/250GB-SSD/kiwix

# Option A: Disable compression via BTRFS property
sudo btrfs property set /mnt/250GB-SSD/kiwix compression none

# Option B: Set NOCOW / No-compression attribute
sudo chattr +C /mnt/250GB-SSD/kiwix

# Verify property
btrfs property get /mnt/250GB-SSD/kiwix
```

---

## 4. Kiwix-Serve Daemon Architecture & Systemd Unit

### 4.1 Native Binary & Network Binding

`kiwix-serve` is installed as a native ARM64 static binary from `kiwix-tools` into `/usr/local/bin/kiwix-serve`.

- **Network Binding:** Bound **strictly to loopback** (`127.0.0.1:8088`).
- **Exposure:** Never bound to `0.0.0.0` or external network adapters. It is strictly a local host IPC service.

### 4.2 Systemd Service Unit (`kiwix-serve.service`)

Deploy the service file to `/etc/systemd/system/kiwix-serve.service`:

```ini
[Unit]
Description=Kiwix ZIM Knowledge Base Daemon (Offline Library)
Documentation=https://github.com/kiwix/kiwix-tools
After=network.target mnt-250GB\x2dSSD.mount
Wants=mnt-250GB\x2dSSD.mount

[Service]
Type=simple
User=neko
Group=neko

# Run kiwix-serve on 127.0.0.1:8088 serving all ZIM files in /mnt/250GB-SSD/kiwix/
ExecStart=/usr/local/bin/kiwix-serve \
  --port=8088 \
  --address=127.0.0.1 \
  /mnt/250GB-SSD/kiwix/wikipedia_en_simple_all_maxi_2024-05.zim

Restart=on-failure
RestartSec=5

# Priority: Lowest CPU scheduling priority to preserve CYD terminal interactivity
Nice=19

# Strict CGroup Resource Constraints (REQ-OPS-02, DEC-W10)
MemoryMax=96M
MemoryHigh=80M
CPUQuota=30%
TasksMax=16

# Security Hardening & Sandboxing
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=read-only
ReadOnlyPaths=/mnt/250GB-SSD/kiwix
PrivateTmp=true
ProtectKernelTunables=true
ProtectControlGroups=true
RestrictAddressFamilies=AF_INET AF_INET6 AF_UNIX

[Install]
WantedBy=multi-user.target
```

### 4.3 Cgroup Constraint Rationale

1. **`MemoryMax=96M`**: Kiwix-serve memory usage scales with concurrent search requests and index size. Capping at 96 MB guarantees that Kiwix can never trigger an out-of-memory crash of the Pi Zero 2W or starve the `terminal` daemon.
2. **`CPUQuota=30%`**: Limits search queries from running 100% CPU on all cores, preventing thermal runup on the passive chassis.
3. **`Nice=19`**: Sets lowest CPU scheduling priority so the interactive CardKB keyboard and CYD serial display bridge maintain crisp <50ms response times.

---

## 5. Multi-Tenant Security & Guest Demo Isolation

### 5.1 The Security Boundary (REQ-OPS-04, DEC-W27)

The Whiskerframe Cyberdeck features an unprivileged `guest` account designed for untrusted hands-on demonstration.

Under **REQ-OPS-04** and **DEC-W27**, the kernel enforces packet drops via `nftables` for all processes running under UID `guest`:

```text
table inet guest_isolation {
    chain output {
        type filter hook output priority 0; policy accept;
        skuid "guest" drop
    }
}
```

### 5.2 Architectural Consequence on Kiwix-Serve

1. **Loopback Traffic Severed:** The `skuid "guest" drop` rule drops **all** egress packets generated by the `guest` user, including packets directed to `127.0.0.1` (loopback).
2. **Loopback Denial:** Because `kiwix-serve` listens on `127.0.0.1:8088`, any connection attempt from a `guest` shell to `127.0.0.1:8088` is blocked immediately at the netfilter kernel hook (`EPERM` / connection timeout).
3. **Intentional Containment:** This behavior is an explicit, deliberate design choice:
   - Prevents untrusted guests from executing high-concurrency search denial-of-service queries against `kiwix-serve`.
   - Prevents port scanning against local daemon ports (`127.0.0.1:8080` File Browser, `127.0.0.1:8384` Syncthing, `127.0.0.1:8088` Kiwix).
   - Preserves complete isolation between guest demonstration mode and privileged host services.
4. **Guest Knowledge Access:** When `guest` runs the CLI helper (`wiki <term>`), the helper gracefully detects that `127.0.0.1:8088` is unreachable and falls back to local man-pages (`man`), Python docs (`pydoc`), and GNU manual pages installed on the local filesystem.

---

## 6. Ethical Hacking & Security Reference Library

For off-grid operations and demonstration of the deck's utility, the offline library incorporates complete documentation and man-pages for security auditing and network tools:

### 6.1 Tool Manual Coverage

| Tool | Core Capability | Offline Reference Source |
| --- | --- | --- |
| `nmap` | Network discovery, port scanning, OS fingerprinting | `man nmap` (comprehensive man-db documentation) |
| `tcpdump` | Network packet capture, BPF filtering | `man tcpdump`, `man pcap-filter` |
| `tshark` | CLI packet dissection and protocol decoding | `man tshark` |
| `curl` | HTTP/HTTPS inspection, header manipulation | `man curl` |
| `openssl` | Cryptographic certificate inspection, cipher analysis | `man openssl`, `man x509`, `man ciphers` |
| `ssh` | Secure shell administration, tunneling, proxying | `man ssh`, `man ssh_config`, `man sshd` |
| `wireguard` | High-performance VPN configuration | `man wg`, `man wg-quick` |
| `nftables` | Packet filtering and network address translation | `man nft` |

### 6.2 Curated Quick References & Cheat Sheets

Stored at `/mnt/250GB-SSD/docs/cheatsheets/` (formatted <= 53 columns):
- `nmap-switches.txt`: Quick reference for stealth SYN, UDP, service versioning, and timing templates.
- `bpf-filters.txt`: Berkeley Packet Filter syntax examples for `tcpdump`.
- `openssl-certs.txt`: One-liners for checking expiry, SANs, and certificate chains.
- `subnets-cidr.txt`: IPv4 CIDR to netmask and usable host tables.

---

## 7. Client Tooling: Terminal `wiki` Helper

### 7.1 Architecture & Geometry Constraints

The Cyberdeck provides a dedicated query CLI:
```bash
/usr/local/bin/wiki  # Symlink to /opt/cyd-display-link/pi/bin/wiki
```

- **Output Formatting:** Tailored strictly for the 53-column CYD display. Every output line is clipped or wrapped to <= 53 characters.
- **Dual-Mode Operation:**
  - **Online Daemon Mode:** If `kiwix-serve` is running on `127.0.0.1:8088`, `wiki` queries the Kiwix search API (`/search?content=...&pattern=...`) or fetches articles via `w3m -dump -cols 53` / `curl`. Supports `-r` for a random article.
  - **Offline Fallback Mode:** If `kiwix-serve` is inactive or blocked, `wiki` queries local system documentation in priority order (`man`, `bash help`, `python3 pydoc`), formatting results <= 53 columns.

### 7.2 Usage Syntax

```bash
wiki <search-term>    # Search offline Wikipedia or fallback man page
wiki -r               # Fetch random article from Kiwix
wiki /path/to/article # Render specific Kiwix article
```

---

## 8. Verification & Operational Runbook

### 8.1 Verification Commands

```bash
# 1. Verify BTRFS directory attribute (no-compression)
btrfs property get /mnt/250GB-SSD/kiwix

# 2. Check kiwix-serve service status and cgroup constraints
systemctl status kiwix-serve.service
systemd-cgls /system.slice/kiwix-serve.service

# 3. Test loopback search API from operator account (neko)
curl -s "http://127.0.0.1:8088/search?pattern=raspberry" | head -n 20

# 4. Test wiki helper on CYD display
wiki "Raspberry Pi"
wiki -r
wiki nmap
wiki cd

# 5. Verify guest isolation drops loopback
sudo -u guest curl -s --connect-timeout 2 http://127.0.0.1:8088/
# Expected: Fails with timeout / EPERM per REQ-OPS-04 and DEC-W27
```
