# Morning Report — 2026-10-07

Overnight autonomous session on the Pi (`10.0.0.212`) + external SSD. Here is what
you woke up to, what needs you, and what was decided without you. Full blow-by-blow
in `docs/overnight-log.md`; the *why* behind each call in `docs/dev/ai-decisions.md`
(DEC-W12, DEC-W13).

---

## 1. Done (verified live on the Pi)

- **SSD is now BTRFS.** Reformatted whole-disk btrfs (label `cyberdeck-ssd`, new
  UUID `98bb87d2-7128-470e-91d5-9e117df2ab1a`), with two subvolumes: `@data`
  (your data, mounted at `/mnt/250GB-SSD` with zstd compression) and `@swap` (holds
  the swapfile). Verified: `findmnt` shows btrfs, `compress=zstd:3`, `subvol=/@data`.
- **Swap/memory safety deployed.** 512MB btrfs swapfile on `@swap` (nodatacow,
  correct for btrfs), sitting *under* the Pi's native zram (zram pri=100 >
  swapfile pri=10). `vm.swappiness=15`, earlyoom running (`-m 8 -s 8`, avoids
  killing sshd/systemd/terminal/battery). Never swaps on the SD card.
- **Syncthing** running as user `neko`, capped at 200M RAM, GUI on
  `127.0.0.1:8384`.
- **File Browser** running as `neko` (native binary v2.31.2, not Docker), capped at
  128M, returns HTTP 200 on `127.0.0.1:8080`.
- **NetBird** installed and running, capped at 150M (not yet logged in — see below).
- **Git server** account created (`git-shell`, bare-repo root on the SSD) — ready,
  but no keys authorized yet (see below).
- **Network automation role built** (iwd client + AP fallback + lockout guard) and
  syntax-checks clean — but deliberately **not switched on** (see below).

## 2. Blocked — needs you (a decision or a secret)

Each of these needs a human choice or a credential I will not invent:

- **Git access — add your SSH public key.** The `git` account's `authorized_keys`
  is empty, so no one can push/clone yet. Drop your pubkey in and git-over-SSH is
  live. *(Needs your key — a secret.)*
- **NetBird — enroll it.** Status is `NeedsLogin`. Either run `netbird up` for
  interactive SSO, or provide a setup key for a headless `netbird up --setup-key …`.
  *(Needs your account / a setup key.)*
- **Wi-Fi automation — apply it + supply creds.** The `network_automation` role is
  built and staged but **not applied** (applying it on a headless box reached only
  over Wi-Fi is a lockout risk). To go live you need to (a) be present / okay with
  the armed rollback, and (b) provide the Wi-Fi network credentials (empty by
  design). *(Needs your decision + Wi-Fi secrets.)*

## 3. Decisions made autonomously

- **btrfs over ext4** for the SSD (your directive) — gives subvolumes (isolate swap
  from data), transparent zstd compression, cheap snapshots later. Cost: the
  swapfile needs btrfs-specific handling (handled).
- **Adopt the Pi's existing zram** rather than install `zram-tools` — installing a
  second zram manager fought the native one and failed on the busy device. The role
  now detects + adopts the live zram.
- **iwd owns wlan0** (client), with NetworkManager + wpa_supplicant masked, and an
  AP fallback arbiter — one owner per radio, never two managers fighting.
- **Services run as `neko`, not root** — syncthing refuses root and filebrowser had
  crash-looped on a root-owned db; both now default to `neko`.
- **Network change staged, not applied** — the apply flag defaults off so a plain
  run can't cut your remote link.

## 4. Anything risky that was done

- **The SSD was wiped and reformatted** (NTFS→ext4 earlier, then ext4→btrfs
  overnight). This was **authorized** and its contents were **disposable**. The disk
  was identified unambiguously by its by-id path (single USB SATA disk) behind a
  model/transport/not-root-or-boot guard; the SD card (`mmcblk0`) was never touched.
- **No network change was applied.** wlan0 ownership is unchanged; your remote
  access is intact.
- **No secrets were invented.** Git `authorized_keys`, the NetBird setup key, and
  the Wi-Fi credentials were all left empty / blocked on you rather than guessed.
