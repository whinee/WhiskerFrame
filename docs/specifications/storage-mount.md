### §2.4 Storage Mount Contract (Template + Generator)

The persistent SSD mount is **never a committed, baked unit**. The repo ships a parameterized template and a generator; the live unit is produced from config, and the destructive and irreversible steps stay gated to a human.

* **Template:** `pi/storage/storage.mount.example` — a systemd `.mount` template carrying placeholder tokens (`@STORAGE_UUID@`, `@STORAGE_OPTIONS@`, etc.), no real device identity. The `@STORAGE_OPTIONS@` token is where the generator injects the fstype-specific mount options (for btrfs: `subvol=@data,compress=zstd,noatime,nofail`).
* **Generator:** `pi/storage/install_mount.py` — reads the `storage:` block from `.whiskerframe.yaml`, systemd-escapes the mount path, and renders the unit, expanding `@STORAGE_OPTIONS@` from the btrfs `subvol`/`compress`/`noatime`/`nofail` keys. Defaults to `--dry-run`; `--apply` writes the unit and runs `daemon-reload`. It **never** runs `mkfs`, `mount`, or `enable` — a missing/foreign SSD must not block boot or trigger a destructive action from a tooling run.
* **Config:** `.whiskerframe.example.yaml` carries a `storage:` block (`enabled: false`, `mount_point`, `device_uuid: ""`, `fstype: btrfs`, `subvol: "@data"`, `compress: zstd`). Live values live in the gitignored `.whiskerframe.yaml` (UUID `98bb87d2-7128-470e-91d5-9e117df2ab1a`).
* **Filesystem (reconciled 2026-10-07, DEC-W12).** The SSD is **whole-disk btrfs** (label `cyberdeck-ssd`), superseding the earlier ext4 reformat (DEC-W9). Two subvolumes: **`@data`** (the data mount at `/mnt/250GB-SSD`, `compress=zstd`) and **`@swap`** (holds the memory-safety swapfile, `nodatacow`, uncompressed — CoW is incompatible with swap). Verified live: `findmnt /mnt/250GB-SSD` → btrfs, `compress=zstd:3`, `subvol=/@data`.
* **Gating:** the destructive reformat is **done** (DEC-W9 ext4, then DEC-W12 btrfs) behind the standing model/transport/root pre-wipe guard and explicit operator go-ahead; the generator itself stays dry-run / non-destructive by default. Rationale in `docs/dev/ai-decisions.md` DEC-W7 (template+generator), DEC-W9 (ext4 reformat), and DEC-W12 (btrfs reconciliation).

---

