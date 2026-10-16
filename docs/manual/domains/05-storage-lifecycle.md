# Domain 05: Storage Lifecycle, Mounts & Media (REQ-STORAGE)

**Specification Prefix:** `REQ-STORAGE`  
**System Layer:** Physical Storage Media, Filesystem Layout & Wear Reduction  
**Primary Implementations:** `pi/storage/install_mount.py`, `scripts/backup-sync.sh`, `ansible/roles/journald_ssd/`  
**Acceptance Test Plan:** `ATP-07-STOR-BTRFS-SWAP`  
**Target Milestone:** `v0` (Demo Prototype) / `v1` (Field Hardened)  

---

## 1. Scope & Domain Objectives

The Storage Lifecycle domain defines the media hierarchy, partition structure, BTRFS subvolume architecture, systemd mount generation, SD-card wear mitigation, and backup policies for the WhiskerFrame Cyberdeck. The storage architecture ensures that the Raspberry Pi OS MicroSD card is protected against write exhaustion while user repositories, swap, and system journals reside on a durable, high-speed 250GB Samsung 860 EVO SSD.

---

## 2. Formal Requirements & Normative Specifications

### REQ-STORAGE-01 [v0]: Non-Destructive Mount Generator
- **Requirement:** The persistent SSD mount MUST be managed via a systemd `.mount` generator (`pi/storage/install_mount.py`) rendering from `.whiskerframe.yaml`. The generator MUST default to `--dry-run` and MUST NOT execute destructive partition or filesystem operations.
- **Rationale:** Prevents accidental data loss or clobbering of partitions when testing or re-configuring storage mounts.
- **Traceability:** `DEC-W7`, `TSK-02`.

### REQ-STORAGE-02 [v0]: BTRFS Whole-Disk Topology
- **Requirement:** The 250GB Samsung 860 EVO SSD MUST be formatted with BTRFS (label `cyberdeck-ssd`, UUID `98bb87d2-7128-470e-91d5-9e117df2ab1a`) hosting two distinct subvolumes: `@data` mounted at `/mnt/250GB-SSD` (`noatime,compress=zstd:3,nofail,x-systemd.device-timeout=5s`) and `@swap` hosting an uncompressed `nodatacow` swapfile.
- **Rationale:** Transparent zstd:3 compression extends storage capacity and write endurance; subvolumes isolate user data from swap paging.
- **Traceability:** `DEC-W12`, `TSK-02a`.

### REQ-STORAGE-03 [v0]: SD Card Wear Mitigation
- **Requirement:** The OS root filesystem on the MicroSD card MUST be protected against write wear via `log2ram` (allocating a 32MB RAM ring buffer) and diverting persistent `systemd-journald` log storage to `/mnt/250GB-SSD/log/journal`.
- **Rationale:** MicroSD cards experience premature flash wear and controller death when subjected to continuous small journal writes.
- **Traceability:** `DEC-W14`, `DEC-W25`, `TSK-03`.

### REQ-STORAGE-04 [v0]: Zero Uncurated Data Deletion
- **Requirement:** Project and user repositories on the persistent SSD MUST NOT be automatically purged; local cleanups remain manual, with primary copies retained on external git remotes or the operator's home server.
- **Rationale:** Sovereign data integrity; an agent or script must never delete operator projects without explicit confirmation.
- **Traceability:** Section 7.13, `DEC-W20`.

### REQ-STORAGE-05 [v1]: Network-Gated Automated Snapshots
- **Requirement:** Automated backup mechanisms (e.g. Backrest / restic) for project repositories MUST synchronize only when connected to trusted, non-LTE networks to preserve battery and cellular data budgets.
- **Rationale:** Cellular connections (LTE modem) have metered data and high power drain; backups must wait for home/campus Wi-Fi.
- **Traceability:** Section 7.07, `scripts/backup-sync.sh`.

### REQ-STORAGE-06 [v1]: Encrypted Authenticated File Sharing
- **Requirement:** File sharing over SMB or File Browser MUST require mandatory user authentication and wire encryption (`smb encrypt = required`) bounded by firewall isolation.
- **Rationale:** Protects personal and client files from LAN eavesdropping in shared university or cafe networks.
- **Traceability:** Section F-07.01, `DEC-W20`.

---

## 3. Actual Implementation Architecture

### 3.1 Declarative Mount Generator (`pi/storage/install_mount.py`)
- Reads mount parameters from `.whiskerframe.yaml` under `storage:`.
- Renders systemd mount unit: `/etc/systemd/system/mnt-250GB\x2dSSD.mount`.
- Generates mount options: `subvol=@data,noatime,compress=zstd:3,nofail,x-systemd.device-timeout=5s`.
- Safety rules: Requires explicit `--apply` flag; defaults to `--dry-run`; verifies UUID with `blkid` before installation.

### 3.2 BTRFS Swapfile Implementation
BTRFS Copy-on-Write (CoW) causes filesystem corruption if enabled on swapfiles. The `@swap` subvolume is created with `nodatacow`:
```bash
# Subvolume creation
btrfs subvolume create /mnt/250GB-SSD/@swap

# Swapfile initialization with CoW disabled
chattr +C /mnt/250GB-SSD/@swap/swapfile
dd if=/dev/zero of=/mnt/250GB-SSD/@swap/swapfile bs=1M count=2048
chmod 600 /mnt/250GB-SSD/@swap/swapfile
mkswap /mnt/250GB-SSD/@swap/swapfile
swapon --priority 100 /mnt/250GB-SSD/@swap/swapfile
```

### 3.3 Log Diversion & Log2Ram
1. **`log2ram`:** Buffers `/var/log` writes in a 32MB tmpfs RAM ring, flushing to disk only on shutdown or daily sync.
2. **Persistent Journald:** Diverted to the SSD via `/etc/systemd/journald.conf.d/ssd-storage.conf`:
   ```ini
   [Journal]
   Storage=persistent
   SystemMaxUse=1G
   Directory=/mnt/250GB-SSD/log/journal
   ```

### 3.4 Backup Synchronization (`scripts/backup-sync.sh`)
- Probes default gateway and active SSID via `nmcli`.
- Compares against trusted SSID list (`HomeNet`, `LabNet`).
- If network is unmetered, executes rsync/restic snapshots to remote homelab target (`10.0.0.2 / 100.86.0.15`).
- If network is cellular (e.g. ZTE LTE modem interface `wwan0`), synchronization is gracefully deferred.

---

## 4. Verification & Acceptance Criteria

Compliance is validated by **`ATP-07-STOR-BTRFS-SWAP`**:
1. Mount unit renders correctly with valid escaped path `mnt-250GB\x2dSSD.mount`.
2. BTRFS subvolumes `@data` and `@swap` are isolated.
3. Swapfile operates with priority 100 and CoW disabled.
4. `log2ram` service active, and journal logs persist under `/mnt/250GB-SSD/log/journal`.
