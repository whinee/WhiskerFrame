# Disaster Recovery & System Restore Procedure

## 1. Overview & Safety Net Architecture

This document specifies the exact, step-by-step procedure for restoring the Whiskerframe Cyberdeck (Raspberry Pi Zero 2W) from local or offloaded backup images.

During unattended maintenance (Phase 4, 2026-10-14), a golden safety net backup was produced directly to the onboard Samsung 860 EVO 250GB SSD (`/mnt/250GB-SSD/backup/2026-10-14/`).

### Backup Artifacts

Location on SSD: `/mnt/250GB-SSD/backup/2026-10-14/`

| Artifact | Format | Description |
| --- | --- | --- |
| `mmcblk0-partition-table.sfdisk` | Text (`sfdisk`) | Full dump of GPT / MBR partition layout for the 64GB MicroSD card. |
| `boot-firmware.tar.gz` | `tar.gz` | Complete file-level archive of `/boot/firmware` (FAT32 partition `mmcblk0p1`), including kernel images, device-tree overlays, `cmdline.txt`, and `config.txt`. |
| `sdcard-mmcblk0.img.zst` | `zstd -T1 -1` compressed raw image | Full block-level streaming image of `/dev/mmcblk0` (partitions 1 and 2). Crash-consistent. |
| `SHA256SUMS` | Text | Cryptographic SHA-256 hashes for all backup artifacts. |

### Crash Consistency Note
The block image was created live while the root filesystem was mounted read-write (`dd if=/dev/mmcblk0 conv=sync,noerror`). While write activity was minimized during the backup, ext4 journal replay will occur on first boot following a restoration. This is standard crash-consistent behavior (identical to an unexpected power outage) and safely recovers filesystem consistency via `fsck.ext4`.

---

## 2. Recovery Scenarios

### Scenario A: Corrupted `/boot/firmware` (Kernel, Overlays, or cmdline.txt)
*Symptoms:* Pi does not boot, ACT LED blinks error patterns, or kernel hangs before mounting root.

1. Remove the MicroSD card from the Cyberdeck and insert it into a host machine (or boot the Pi into an alternate live environment).
2. Mount the first partition (`mmcblk0p1` or `/dev/sdX1`):
   ```bash
   sudo mount /dev/sdX1 /mnt/sd-boot
   ```
3. Extract the backup archive directly onto the partition:
   ```bash
   tar -xzf /path/to/boot-firmware.tar.gz -C /mnt/sd-boot
   sync
   sudo umount /mnt/sd-boot
   ```
4. Re-insert the card into the Cyberdeck and boot.

---

### Scenario B: Complete MicroSD Card Failure or Replacement
*Symptoms:* Read-only filesystem errors, I/O errors from `mmcblk0`, bad blocks, or total boot failure.

#### Required Tools
- New MicroSD card (>= 64GB recommended).
- Workstation with a card reader and `zstd`, `dd`, `sfdisk` installed.
- The backup directory copied from the SSD to the workstation:
  ```bash
  # Offload from Cyberdeck SSD (when online):
  rsync -avz --bwlimit=5000 root@10.0.0.212:/mnt/250GB-SSD/backup/2026-10-14/ ./backup-2026-10-14/
  ```

#### Step 1: Verify Checksums
```bash
cd ./backup-2026-10-14/
sha256sum -c SHA256SUMS
```
Do NOT proceed if checksum verification fails.

#### Step 2: Identify Target Card
Insert the replacement MicroSD card into the dev workstation. Determine its block device name (e.g. `/dev/sdb` or `/dev/mmcblk0`). **DO NOT target the system disk.**
```bash
lsblk
```

#### Step 3: Flash the Image
Decompress and stream the raw image directly to the target device:
```bash
# Decompress on the fly directly to the card:
zstd -d -c sdcard-mmcblk0.img.zst | sudo dd of=/dev/sdX bs=4M status=progress conv=fsync
```

#### Step 4 (Alternative): Restore Partition Table and Filesystems Manually
If flashing a different-sized card:
1. Restore partition boundaries:
   ```bash
   sudo sfdisk /dev/sdX < mmcblk0-partition-table.sfdisk
   ```
2. Format partitions if restoring selectively:
   ```bash
   sudo mkfs.vfat -F 32 -n "bootfs" /dev/sdX1
   sudo mkfs.ext4 -L "rootfs" -U <ORIGINAL_UUID> /dev/sdX2
   ```
3. Unpack boot firmware:
   ```bash
   sudo mount /dev/sdX1 /mnt/target-boot
   sudo tar -xzf boot-firmware.tar.gz -C /mnt/target-boot
   sudo umount /mnt/target-boot
   ```

---

### Scenario C: Emergency On-Device Rollback (Dual-Media Recovery)
If the Cyberdeck is booted into a minimal recovery environment (or via USB mass storage):
1. Mount the SSD:
   ```bash
   mount /dev/sda1 /mnt/250GB-SSD
   ```
2. Restore to the internal card directly on-device:
   ```bash
   zstd -d -c /mnt/250GB-SSD/backup/2026-10-14/sdcard-mmcblk0.img.zst | dd of=/dev/mmcblk0 bs=4M status=progress conv=fsync
   ```

---

## 3. Post-Restore Verification Checklist

After restoring and booting the restored system:
- [ ] Connect via serial console or SSH (`root@10.0.0.212`).
- [ ] Run `dmesg | grep -E "EXT4|error|mmc"` to confirm clean journal replay without uncorrected errors.
- [ ] Run `btrfs filesystem show` to ensure the SSD `/mnt/250GB-SSD` mounted cleanly.
- [ ] Run `systemctl --failed` to verify all services (`terminal.service`, `battery-monitor.service`, `cyberdeck-net-heal.timer`) started successfully.
- [ ] Run `/usr/local/bin/cyberdeck-net-heal.sh` to confirm network self-healing and heartbeat updates.
