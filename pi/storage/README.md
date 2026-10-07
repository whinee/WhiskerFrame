# External storage mount

Parameterized systemd `.mount` unit for an external SSD, bound by UUID so a
missing drive never blocks boot (`nofail` + `x-systemd.device-timeout=5s`).

No real UUIDs or paths live in the repo. The committed files are a template and
a generator; the real values come from the gitignored `.whiskerframe.yaml`
`storage` block and are only ever materialized on the Pi.

## Files

- `storage.mount.example` — template unit with `@...@` placeholders.
- `install_mount.py` — generator: reads the `storage` block, computes the
  systemd-escaped unit filename from `mount_point`, renders the template, and
  (with `--apply`) writes `/etc/systemd/system/<escaped>.mount` + daemon-reload.

## Configure

Set the `storage` block in `.whiskerframe.yaml` (not the committed example):

```yaml
storage:
  enabled: true
  mount_point: "/mnt/storage"
  device_uuid: "<blkid UUID of the filesystem>"
  fstype: "btrfs"
  subvol: "@data"
  compress: "zstd"
```

Leave `enabled: false` or `device_uuid: ""` and the generator is a safe no-op.

## Install (on the Pi)

```sh
source .env
# push repo to the Pi (uv/rsync deploy)
rsync -e "ssh -i ${DEFAULT_KEY_PATH}" -a pi/storage/ \
  "${PI_USER}@${PI_HOST}:~/cyberdeck/pi/storage/"

# 1. preview the generated unit (default; writes nothing)
ssh -i "${DEFAULT_KEY_PATH}" "${PI_USER}@${PI_HOST}" \
  'python3 ~/cyberdeck/pi/storage/install_mount.py --dry-run'

# 2. write it + daemon-reload (root)
ssh -i "${DEFAULT_KEY_PATH}" "${PI_USER}@${PI_HOST}" \
  'sudo python3 ~/cyberdeck/pi/storage/install_mount.py --apply'

# 3. enable the unit (deliberate separate step; name is printed by step 2)
ssh -i "${DEFAULT_KEY_PATH}" "${PI_USER}@${PI_HOST}" \
  'sudo systemctl enable --now "mnt-storage.mount"'
```

The generator never runs mkfs/mount and never enables the unit. Formatting the
SSD (destructive) and enabling the mount stay manual.

> ext4 is the project target. For an NTFS drive, set `fstype: ntfs` and install
> `ntfs-3g` on the Pi (`sudo apt install ntfs-3g`).

## Verify

```sh
ssh -i "${DEFAULT_KEY_PATH}" "${PI_USER}@${PI_HOST}" 'findmnt ${STORAGE_MOUNT_POINT:-/mnt/storage}'
```

## Rollback

```sh
ssh -i "${DEFAULT_KEY_PATH}" "${PI_USER}@${PI_HOST}" \
  'sudo systemctl disable --now "mnt-storage.mount" \
   && sudo rm /etc/systemd/system/"mnt-storage.mount" \
   && sudo systemctl daemon-reload'
```

(Substitute the escaped unit name from the generator output for a different
mount point.)
