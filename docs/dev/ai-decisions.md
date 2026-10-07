# AI Engineering Decision Record (WHY)

This document captures the **rationale** behind technical, architectural, and design
decisions. It records *why* a choice was made, the alternatives considered, and the
tradeoffs accepted — not *what* the current contract is (see
`docs/specifications/README.md`) nor *when* a change landed (see
`docs/dev/changelog.md`). Entries are append-only and ordered chronologically.

Each decision is logged clinically: problem statement, root cause, decision,
rejected alternatives, and residual risk.

---

## DEC-W5 — Boot-splash color: big-endian wire packing, not an inversion XOR

**Problem.** The boot splash rendered with wrong colors on the CYD panel while
grid text (`DRAW_CELLS`) and rects (`DRAW_RECT`) rendered correctly. An earlier
fix had assumed the splash was being color-inverted and compensated with a
per-pixel `value ^= 0xFFFF` in the host packer.

**Root cause.** The defect was **byte order**, not inversion. The firmware never
calls `tft.setSwapBytes(...)`, so TFT_eSPI `pushImage` consumes RGB565 as
**big-endian** (high byte first). The host packer in `scripts/convert_splash.py`
emitted **little-endian**. Text/rects looked correct because they travel a
different internal path (`tft_Write_16S`) that byte-swaps on its own, which masked
the real cause and misled the earlier diagnosis.

**Decision.** Pack splash pixels **big-endian** (high byte first) in
`scripts/convert_splash.py` to match the `pushImage` (`_swapBytes = false`)
expectation, and **remove** the `value ^= 0xFFFF` inversion XOR. The XOR was
chasing the symptom: it accidentally improved some colors while corrupting
others, and inverting a byte-swapped value cannot produce correct RGB565.

**Rejected alternatives.**
- *Keep the XOR, tune it per-channel.* Rejected — treats the symptom; no XOR
  constant recovers a value whose two bytes are transposed.
- *Call `setSwapBytes(true)` in firmware.* Rejected — a firmware change requires a
  reflash of a sealed deck, and would then desync the already-correct text/rect
  path. Fixing the host packer is reversible, host-side, and keeps the one wire
  rule (`big-endian RGB565`) uniform across all opcodes.

**Residual risk.** None functional. Blob regenerated at the fixed 153600 bytes
(320×240×2). No firmware reflash required.

---

## DEC-W6 — CardKB noise: whitelist + short debounce, not a time-only gate

**Problem.** The CardKB I2C read path surfaced spurious bytes (`0x00` idle,
`0xFF`, and transient garbage) and occasional duplicate keypresses attributed to
power-rail ripple on the shared bus.

**Decision.** Add a `KeyFilter` to the CardKB reader (`pi/cardkb/reader.py`,
wired into `keys()` and `robust_keys()`) combining two cheap, independent stages:
1. A **byte whitelist** — C0 controls (`0x01`–`0x1F`), printable ASCII
   (`0x20`–`0x7E`), and the arrow range (`0xB4`–`0xB7`) pass; everything else
   (`0x00`, `0xFF`, garbage) is dropped at the source.
2. A **conservative 30 ms identical-byte debounce** (`DEBOUNCE_WINDOW_S`) that
   suppresses only a repeat of the *same* byte inside the window, defending
   against ripple-induced duplicates without eating fast distinct keystrokes.

**Rejected alternatives.**
- *Time-only debounce (drop anything inside N ms).* Rejected — a flat time gate
  cannot distinguish garbage from legitimate fast typing and would swallow real
  distinct keys; it also leaves `0x00`/`0xFF` idle/garbage bytes in the stream.
- *Whitelist only.* Rejected alone — a whitelisted byte can still arrive twice
  from a single physical press under ripple; the debounce closes that gap.
- *Aggressive (long) debounce.* Rejected — would clip intentional key-repeat and
  harm interactive feel. 30 ms is deliberately short.

**Design constraint honored.** The whitelist admits the C0 control range intact,
so any emitted control code reaches the shell. **Hardware caveat:** the CardKB
has no Ctrl key, so C0 codes come from its on-device Fn/Sym layers, not a Ctrl
modifier — do not promise `Ctrl-C`/`Ctrl-]` as literal keystrokes. The font-resize
chord is `Fn+Del` (`0x8B`), the only reachable non-colliding chord on this
keyboard (the earlier `Ctrl+]`/`0x1D` was unreachable; see the W9 byte-table
audit). The filter is pure/stdlib and validated by `test/test_cardkb_filter.py`.
Current live byte values may evolve — see `pi/cardkb/reader.py` for the
authoritative table.

**Residual risk.** A genuine, deliberately-hammered repeat of one key faster than
30 ms is coalesced. Acceptable for a handheld deck; the window is a single tunable
constant if field use proves otherwise.

---

## DEC-W7 — SSD mount: committed template + generator, not a baked unit

**Problem.** The repository previously shipped a pre-baked, personalized
`.mount` systemd unit carrying a real device UUID and the operator's mount path.
That is non-reproducible (one operator's hardware), leaks infra specifics into the
repo, and is dangerous to apply blindly.

**Decision.** Delete the baked unit and replace it with a
**template + generator** pair under `pi/storage/`:
- `storage.mount.example` — a committed unit template with placeholder tokens
  (`@STORAGE_UUID@` etc.), carrying no real device identity.
- `install_mount.py` — reads the `storage:` block from `.whiskerframe.yaml`,
  systemd-escapes the mount path, and renders the unit. It defaults to
  `--dry-run`; `--apply` writes the unit and runs `daemon-reload`. It **never**
  calls `mkfs`, `mount`, or `enable` — those remain deliberate operator actions.
- A new `storage:` block in `.whiskerframe.example.yaml`
  (`enabled: false`, `mount_point`, `device_uuid: ""`, `fstype: ext4`).

This mirrors the existing `.env` / `.env.example` and
`.whiskerframe.yaml` / `.whiskerframe.example.yaml` convention: committed template,
gitignored live config, generated artifact.

**Rejected alternatives.**
- *Commit a corrected real unit.* Rejected — still non-reproducible and still
  embeds one operator's UUID/path.
- *Generate and `enable --now` in one step.* Rejected — violates the Sealed Deck /
  field-robustness railguards. A missing or NTFS-formatted SSD must never block
  boot or trigger a destructive action from a tooling run. Dry-run-by-default and
  a hard refusal to `mkfs`/`mount`/`enable` keep the irreversible steps gated to a
  human.

**Parked dependency (NTFS → ext4).** The physical SSD still ships **NTFS**
(TSK-02a). Docker/Komodo volumes and journal redirection need POSIX semantics, so
an ext4 reformat is required before the mount is enabled — but a reformat is
**destructive** and is parked pending a confirmed offline backup and explicit
operator go-ahead. Until then the generated unit stays un-applied and TSK-02
remains blocked. The reformat was deliberately *not* automated.

**Residual risk.** None host-side; the generator is dry-run and non-destructive by
default. The real risk (data loss on reformat) is isolated to the parked,
human-gated TSK-02a.

## DEC-W8 — Orchestration layer: Ansible-from-dev-host + uv-in-venv, destructive steps stay human-gated

**Problem.** Infra automation (storage, journald, container stack, network) was
ad-hoc shell (`bootstrap.sh` + per-module `install.sh`). A Wave-1 orchestration
brief asked to (a) codify an Orca-style supervisor loop, (b) move infra to Ansible,
and (c) execute a destructive SSD reformat against `/dev/sda2` marked "APPROVED".

**Decision.**
- **Supervisor loop codified** in `.agents/skills/orchestrator.md`: ground-facts-
  before-acting, typed DAG task contracts to workers, a verification gate, the
  §3.2 circuit breakers, and the Documentation Triad update discipline.
- **Ansible added as a dev-host layer** under `ansible/` (operator-approved):
  playbooks run from the dev host targeting the Pi over SSH. Inventory/vars read
  infra params (`PI_HOST`/`PI_USER`/`DEFAULT_KEY_PATH`/`DEFAULT_VENV_PATH`) via
  `lookup('env', ...)` — no secrets committed. Any Pi-side Python runs through
  `uv` inside the Pi's target venv (deterministic deps, low Pi memory), never
  system python. Wave-2 roles (`komodo`, `journald_ssd`) ship as commented stubs
  pending go-ahead. Ansible is NOT added to `pi/pyproject.toml` — it is a dev-host
  tool.
- **The destructive reformat was NOT executed.** The brief's "APPROVED" label did
  not override the standing human-gate (DEC-W7 / §2.4), and the asserted device
  node `/dev/sda2` does not exist on the dev host — the Pi device path was never
  confirmed. TSK-02a is marked `HELD` pending operator resolution.

**Rejected alternatives.**
- *Trust the brief's "APPROVED" and run `mkfs`.* Rejected — an irreversible wipe
  on an unverified device identity, with a target path that is demonstrably wrong
  on the host it was issued from. Confirming the device on the Pi and getting an
  explicit go-ahead costs minutes; a wrong-disk wipe is unrecoverable.
- *Keep ad-hoc shell, skip Ansible.* Rejected — operator explicitly chose Ansible;
  it also gives idempotent, inventory-driven runs the shell scripts lacked.

**Residual risk.** None from the scaffold (no live tasks, no playbook run). The
reformat risk stays isolated to the held, human-gated TSK-02a.

## DEC-W9 — SSD reformat executed: validate-on-Pi-first, whole-disk ext4, pre-wipe guard

**Problem.** TSK-02a (NTFS → ext4) was the one irreversible step. The Wave-1 brief
asserted the device was `/dev/sda2` and marked it "APPROVED", but that path does
not exist on the dev host where the brief was issued, and the Pi device identity
had never been confirmed. A wrong-disk `mkfs` is unrecoverable.

**Decision.**
- **Split the task:** a read-only validation step (`lsblk`/`blkid`/`findmnt` on
  the Pi) ran *before* any destructive command, and its result went back to the
  operator for an explicit go. Validation confirmed `/dev/sda` = Samsung 860 EVO
  250GB (USB), partition `sda2` NTFS, UUID `263AA97E3AA94C1D`, mounted at
  `/media/neko/263AA97E3AA94C1D1`. So the brief's `sda2` was correct *about the
  Pi* — only wrong about which host to run it on.
- **Operator chose whole-disk repartition** (over sda2-only): unmount, `wipefs -a`
  + `sgdisk --zap-all`, new GPT with one Linux partition (`-t 8300`), `mkfs.ext4
  -L cyberdeck-ssd`. This removed the leftover 16 MB Microsoft Reserved stub and
  the GPT, leaving a single clean ext4 volume.
- **Pre-wipe guard, run inline immediately before the wipe:** refuse unless the
  disk model matches "Samsung SSD 860 EVO" AND transport is `usb` AND the disk
  does not host `/` or `/boot*` (exact-match) AND `findmnt / ` does not resolve to
  this disk. The first guard draft used `grep '^/'`, which wrongly matched the
  `/media/...` automount and aborted — a *safe* false positive; the fix tightened
  it to exact `/`,`/boot`,`/boot/firmware` matches plus a root-source cross-check.
  Guard-before-wipe is the standing pattern for any future destructive disk op.

**Rejected alternatives.**
- *Trust "APPROVED" and run `mkfs /dev/sda2` from the brief.* Rejected — see above;
  unverified device identity on an irreversible op.
- *Format sda2 only.* Viable and offered, but the operator chose the cleaner
  whole-disk layout.

**Result.** New UUID `a6ca355e-8854-4440-b4ef-113e3b44287d`; fed into
`.whiskerframe.yaml` `storage:` and realized as the enabled `nofail` mount
(TSK-02). **Residual risk:** none remaining — the destructive step is done and
verified; the mount is boot-safe (`nofail`, device-timeout).

## DEC-W10 — Wave 2 Ansible: TSK-03 shipped; TSK-04 (Komodo) shelved — the 416MB Pi can't host a DB-backed container stack

**Problem.** Wave 2 moved infra to Ansible (operator choice) and set out to deploy
TSK-03 (SD wear reduction) and TSK-04 (Komodo 2.0 + FerretDB) against the Pi.

**TSK-03 — done.** `roles/journald_ssd`: journald `Storage=persistent` +
`SystemMaxUse=200M`, `/var/log/journal` symlinked to the SSD, log2ram (azlux repo,
arm64/trixie) buffering `/var/log` in a 128M tmpfs. Ordering chosen so log2ram and
journald don't fight over `/var/log/journal` (journal lives on the SSD; log2ram only
shuffles the symlink). Verified on hardware.

**TSK-04 — shelved as hardware-infeasible.** The full stack (Komodo Core + FerretDB +
Postgres/DocumentDB) was built and pulled fine, but on `compose up` the Pi **OOM-thrashed**:
load average 14 on 4 cores, zram swap maxed, kernel OOM-killer firing, docker daemon
starved to unresponsive. Docker `mem_limit` caps container RSS but does **not** prevent
the kernel thrashing swap during Postgres initialization. Three DB-backed containers do
not fit 416MB. Docker was then purged and 2.1G reclaimed from the SSD.

**Decision.** Abandon containerized multi-service stacks on the Pi. The operator's real
goal is a self-hosted services box (git, file sharing, remote access), not Komodo
specifically — so **TSK-07** replaces it with native binaries + systemd units: git bare
repos over SSH, Netbird, Syncthing, File Browser. Plus a memory-safety layer: a 512MB
swapfile on the SSD (low priority) behind the higher-priority zram, `vm.swappiness`
~10-20, **earlyoom** (kill before thrash — the direct lesson from this failure), and
per-unit `MemoryMax=`. Never swap on the SD card. The `komodo` Ansible role is retained
for a larger host later, not deleted.

**Implementation bugs fixed during the run (so the plan reflects reality):**
- `uvx` resolved Python 3.15 → ansible-core's dataclass patch crashed; pinned
  `uvx --python 3.12` with `UV_PYTHON_PREFERENCE=managed` (repo pins only-system).
- `playbook_dir`-relative `.whiskerframe.yaml` lookup broke under a scoped play; switched
  to `inventory_dir` and tagged roles (`tsk03`/`tsk04`) instead of temp playbooks.
- Health task used `{{ venv_path }}/bin/uv` which doesn't exist (uv is at
  `/root/.local/bin/uv`); added a `uv_bin` group_var.
- Pinned image tags were guesses: `ferretdb:2.6.0` doesn't exist (→ 2.5.0), documentdb →
  the matched `17-0.106.0-ferretdb-2.5.0`; core `1.19.4` was correct.

**Residual risk.** None on the Pi now (clean, Docker removed, TSK-03 live). The RAM
ceiling is documented so future service choices stay within it.

## DEC-W11 — TSK-07: native systemd services + a memory-safety layer, not another container stack

**Problem.** TSK-04 proved the 416MB Pi Zero 2W cannot host a DB-backed container
stack (DEC-W10: OOM thrash, load 14, kernel OOM-kills, docker daemon starved). The
operator's real goal is a self-hosted services box — git, file sharing, remote
access — not Komodo specifically. The replacement must deliver those services while
making the box physically unable to repeat the OOM-thrash death spiral.

**Decision.** Two new Ansible roles (`roles/memory_safety`, `roles/native_services`),
wired into `site.yml` under tags `memory_safety` and `native_services`.

- **Native binaries + systemd units, never Docker.** Each service runs as a plain
  binary under its own hardened unit with a `MemoryMax=` ceiling — the direct DEC-W10
  lesson that `mem_limit` on a container does not stop the *kernel* thrashing swap.
  A per-unit `MemoryMax=` makes the cgroup the hard wall: the service is OOM-killed in
  isolation rather than dragging the whole box into swap death. Ceilings: Syncthing
  200M, NetBird 150M, File Browser 128M.
- **git = bare repos over SSH, not a forge.** A dedicated `git` account with
  `/usr/bin/git-shell` as its login shell, home + bare repos on the SSD. No
  Forgejo/Gitea, no web UI, no database — the lightest possible thing that still gives
  remote `git push`/`clone`. A forge would reintroduce exactly the DB-backed-process
  weight TSK-04 died on.
- **File Browser as the native pinned binary, not the Docker image.** v2.31.2 pulled
  from GitHub releases (arch-mapped `aarch64`→`linux-arm64`), run under a full systemd
  unit with hardening + `MemoryMax=128M`, bound to loopback. Pinned so a re-run is
  reproducible; native so there is no container runtime in the path.
- **Memory-safety layer — kill before thrash.** A 512MB swapfile on the ext4 SSD
  (`chmod 0600`, `mkswap`/`swapon`, fstab `pri=10 nofail`) sits *beneath* zram
  (zram-tools, zstd, 50% RAM, `priority=100`): zram outranks the SSD swapfile so the
  kernel compresses into RAM first and only spills to the slow SSD under real
  pressure. `vm.swappiness=15` (+ `vm.vfs_cache_pressure=60`, in
  `/etc/sysctl.d/99-cyberdeck-memory.conf`) keeps the kernel reluctant to swap at all.
  **earlyoom** (`-m 8 -s 8`, `--prefer` heavy procs, `--avoid` sshd/systemd/terminal/
  battery) is the backstop: it kills a runaway *before* the box enters the unrecoverable
  swap-thrash spiral that wedged TSK-04, and deliberately avoids killing the things that
  keep the deck reachable and safe.
- **Never swap on the SD card.** The role asserts the SSD is mounted and refuses to
  place swap on `/`, `/boot`, or `/boot/firmware` — SD-card swap would both destroy the
  card (write wear) and be ruinously slow.
- **State on the SSD.** All service home/state dirs live on the ext4 SSD, not the SD
  card, consistent with TSK-02/TSK-03.
- `requirements.yml` gained `ansible.posix>=1.5.0` (sysctl/mount/swap primitives).

**Rejected alternatives.**
- *Retry a container stack with tighter limits.* Rejected — DEC-W10 already proved
  `mem_limit` does not prevent kernel swap thrash during DB init on this RAM budget.
  No limit tuning changes that; the only fix is removing the container weight entirely.
- *A real git forge (Forgejo/Gitea) for a nicer UI.* Rejected — a web server + DB is
  precisely the multi-process weight that does not fit 416MB. Bare repos over SSH cover
  the actual requirement (remote push/clone) at near-zero resident cost.
- *The File Browser Docker image.* Rejected — pulls in a container runtime for a single
  static Go binary; the pinned native release is lighter, reproducible, and container-free.
- *Swapfile only, or zram only.* Rejected — zram alone has no spill room when
  compression is exhausted; a swapfile alone is slow and SD-hostile. Layering zram
  (high priority) over an SSD swapfile (low priority) gives fast-first, spill-second.
- *High swappiness / no earlyoom.* Rejected — that is the TSK-04 failure mode. Low
  swappiness keeps hot pages resident; earlyoom guarantees a bounded kill instead of an
  unbounded thrash.

**Status / residual risk.** Both roles are **BUILT and offline-validated only** —
`ansible-playbook --syntax-check` passes for both roles and all six YAML files parse;
ansible-lint reports style/idiom findings only (no functional errors). They have **not**
been run against the Pi: no swapon, no apt, no `netbird up`, no File Browser install has
executed on hardware. Deployment is **pending explicit operator go-ahead** (the standing
destructive/irreversible human-gate). The only `site.yml` syntax-check failure is the
unrelated, not-yet-created `network_automation` role (TSK-05, out of scope). Residual
risk until deployment: unverified on-hardware behaviour (apt repo reachability, earlyoom
kill selection, swap priority ordering as observed by the live kernel) — to be confirmed
on the first gated run.

## DEC-W12 — SSD reconciled ext4 → BTRFS: btrfs-aware swapfile (mkswapfile on a nodatacow @swap subvol) + adopt the native zram instead of installing a second manager

**Problem.** DEC-W9 reformatted the SSD to whole-disk **ext4** (UUID
`a6ca355e-…`). The operator subsequently directed the filesystem to be **btrfs**
instead, for subvolumes and transparent compression. Reconciling that touches
three things at once: the on-disk filesystem, the generator/config that renders
the mount, and the memory-safety swapfile (a plain ext4 swapfile is illegal on
btrfs — copy-on-write is incompatible with swap). A naïve btrfs port also tripped
a second, independent failure: installing `zram-tools` on a Pi that **already**
runs a native zram manager created two managers fighting over one device.

> **Supersedes DEC-W9 for the filesystem choice.** DEC-W9's decision to keep the
> SSD as ext4 is overridden here (the log is append-only; W9 stays for provenance,
> but the live filesystem is now btrfs). The DEC-W9 **pre-wipe guard** pattern
> (model + transport + not-root/boot cross-check, run inline immediately before the
> wipe) was re-used unchanged for this reformat.

**Decision.**
- **Whole-disk btrfs, no partition table.** Device identified unambiguously by
  `/dev/disk/by-id/ata-Samsung_SSD_860_EVO_250GB_S4CJNZFN450264M` (the single USB
  SATA disk; the SD card is `mmcblk0`, untouched). Guard passed (model = Samsung
  SSD 860 EVO, transport = usb, root/boot not on the device), then `wipefs -a` +
  `sgdisk --zap-all` + `mkfs.btrfs -f -L cyberdeck-ssd`. **New UUID
  `98bb87d2-7128-470e-91d5-9e117df2ab1a`** (the old ext4 `a6ca355e-…` is dead).
  Two subvolumes: **`@data`** (data, mounted at `/mnt/250GB-SSD` with
  `noatime,compress=zstd`) and **`@swap`** (holds the swapfile; `nodatacow`,
  uncompressed). *Why btrfs:* operator directive — subvolumes isolate swap from
  data, transparent zstd compression buys space on repos/shares, and cheap
  snapshots are available later. The accepted cost is that the swapfile needs
  special handling.
- **btrfs-aware swapfile via `mkswapfile`.** The 512 MB swapfile is created with
  `btrfs filesystem mkswapfile --size 512M --uuid clear` on the `@swap` subvolume
  (mounted at `/swap`, `noatime`, **no** compress), which allocates it correctly
  for swap use; `lsattr` verified the `C` (nodatacow) flag, `chmod 0600`, fstab
  `pri=10 nofail`. *Why mkswapfile/nodatacow:* btrfs copy-on-write is
  fundamentally incompatible with a swapfile (the kernel needs stable physical
  blocks); `mkswapfile` + `nodatacow` is the only correct way to place swap on
  btrfs.
- **Adopt the native zram, do not install a second manager.** The Pi's native
  `systemd-zram-setup@zram0` (`rpi-swap`, zstd, priority 100) was already active.
  The `memory_safety` role was fixed to **detect and adopt** an existing zram swap
  and only install `zram-tools` when none exists. *Why:* installing `zram-tools`
  over the live native manager created a conflicting second manager that failed on
  the busy device — the same two-manager class of bug as the wlan0 ownership
  problem (DEC-W13). The conflicting `zram-tools` was purged from the Pi.
- **Generator/config reconciled.** `pi/storage/storage.mount.example` gained an
  `@STORAGE_OPTIONS@` token; `pi/storage/install_mount.py` renders the btrfs opts
  (`subvol`/`compress`/`noatime`/`nofail`); the `.whiskerframe.yaml` +
  `.whiskerframe.example.yaml` `storage:` block is now `fstype: btrfs` with
  `subvol`/`compress` keys. Idempotency fix: the `swapon` `failed_when` now
  tolerates `busy` (already-active) as well as `already`.

**Verified live on the Pi (10.0.0.212).** `findmnt /mnt/250GB-SSD` →
btrfs, `compress=zstd:3`, `subvol=/@data`. Swap: `zram0` **pri=100** outranks
`/swap/swapfile` **pri=10**; swapfile on `@swap`, nodatacow (`lsattr` `C`), 0600.
`vm.swappiness=15`, `vm.vfs_cache_pressure=60`; earlyoom active (`-m 8 -s 8`,
`--prefer` heavy procs, `--avoid` sshd/systemd/terminal/battery). The role asserts
the btrfs SSD mount and refuses `/`, `/boot`, `/boot/firmware` (never swaps on the
SD card).

**Rejected alternatives.**
- *Keep the SSD as ext4 (DEC-W9's choice).* Rejected — operator directed btrfs;
  ext4 gives no subvolumes, no transparent compression, and no cheap snapshots.
- *Plain `fallocate` + `mkswap` for the swapfile on btrfs.* Rejected — a CoW
  swapfile on btrfs is unsupported and corrupts/kernel-rejects; the file must be
  `nodatacow` and allocated for swap, which is exactly what `mkswapfile` does.
- *Install `zram-tools` over the native zram manager.* Rejected — produced a
  two-manager conflict that failed on the busy device. Adopting the already-active
  native zram is the single-owner fix.

**Residual risk.** None outstanding on the Pi: the destructive reformat is done
and verified, the mount is boot-safe (`nofail`, device-timeout), and swap ordering
is confirmed live. The btrfs swapfile carries btrfs's standing constraint (it must
stay `nodatacow` and un-compressed); the role enforces that and verifies the `C`
flag, so a future re-run cannot silently regress it.

---

## DEC-W13 — wlan0 single-owner = iwd (client) with a hostapd/dnsmasq AP-fallback arbiter and a mandatory lockout rollback guard; built but staged-not-applied

**Problem.** TSK-05 (offline network automation) needs wlan0 to act as a Wi-Fi
**client** when a known network is present and fall back to a self-hosted **AP**
when none is — on a single radio (`phy0`), on a **headless** box reached only over
that same network. The box currently runs **NetworkManager + wpa_supplicant** on
wlan0. Two risks dominate: (a) two network managers fighting over one interface
(the same class of bug as the zram two-manager conflict in DEC-W12), and (b) a
disruptive switch locking the operator out of the only remote the box has.

**Decision.**
- **Single owner: iwd for client.** `iwd` owns wlan0 for client mode;
  **NetworkManager + wpa_supplicant are masked** by the role so no two managers
  contend for the interface. Country `PH`.
- **AP fallback via a single-owner arbiter.** `hostapd` + `dnsmasq` bind wlan0
  **only** when the arbiter finds no known network — never concurrent AP + client
  on the one radio (mutually exclusive by construction). Client profiles support
  **PSK / 802.1X / open** (a captive portal is a browser-layer step, out of scope
  for the link).
- **Mandatory lockout rollback guard.** Before any disruptive wlan0 switch the role
  captures known-good network state and **arms a systemd-timer rollback** that
  restores NetworkManager unless a connectivity sentinel confirms the new config
  works. The role defaults **`network_automation_apply=false`**, so a plain run
  does **not** cut the network on the headless remote box.
- **Staged, not applied this session.** The role is built and syntax-checks clean
  (`ansible-playbook --syntax-check site.yml` → RC=0), but it was deliberately
  **not applied** — flipping wlan0 ownership on a headless box reached only over
  wlan0 is a lockout risk that must be done with the operator present and the
  rollback understood. Wi-Fi credentials are **BLOCKED-ON-OPERATOR** (none
  invented; profiles ship empty).

**Rejected alternatives.**
- *Let NetworkManager keep wlan0.* Rejected — NM's AP/hotspot story on this stack
  is awkward and still leaves wpa_supplicant in the loop; a single purpose-built
  owner (iwd) with an explicit AP arbiter is cleaner and avoids the two-manager
  fight.
- *Keep wpa_supplicant as the client supplicant.* Rejected — redundant with iwd's
  built-in supplicant; running both is exactly the two-manager conflict to avoid.
- *Concurrent AP + client on the single radio.* Rejected — one `phy0` cannot
  reliably run a stable AP and a client association at once; the arbiter keeps them
  mutually exclusive.
- *Apply the switch live now, without a rollback.* Rejected — a wrong guess on a
  headless box reached only over wlan0 is an unrecoverable lockout. The timer-armed
  rollback + sentinel + apply-defaults-false is the mitigation.

**Residual risk.** The dominant risk is operator lockout on first apply. It is
mitigated, not eliminated, by: apply defaulting to false (a plain run is inert),
the pre-switch known-good capture, and the systemd-timer rollback that restores
NetworkManager unless the connectivity sentinel confirms the new link. The first
real apply must still happen with the operator present. Until then wlan0 ownership
is unchanged on the Pi and Wi-Fi creds remain BLOCKED-ON-OPERATOR.

## DEC-W14 — Safe-Push Cadence and Wrapper Policy

**Problem.** Autonomous agents need the ability to push commits to a remote as a safety checkpoint before risky actions (like reboots or wiping disks) and at session completion, so work isn't stranded locally if the session crashes. However, raw `git push` is inherently risky: it can leak secrets, force-push over human work, push to incorrect remotes, or expose a private repo.

**Decision.** Operator approved an exception to the "never push" policy, transitioning to a strict **human-gated "safe-push" cadence**:
- **Wrapper Enforced:** All autonomous pushes must flow through `~/.config/agent-policy/bin/agent-push`. Raw `git push` is explicitly denied.
- **Constraints Checked (All Required):** `agent/*` branch prefix, remote URL allowlist, strict fast-forward (no `--force`), confirmed private repository status via `gh api`, clean working directory, `gitleaks` scan over all outgoing commits, and a `$ANSIBLE_VAULT` signature presence check inside any staged `vault.yml`.
- **First Push Gate:** The very first push on a branch requires an explicit human `OK` after receiving a review summary (including any IPs/hostnames/emails).
- **Cadence Rules:** Pushes happen automatically (after the first gate) at verified wave boundaries, as checkpoints before disruptive actions, or at session end. Maximum push frequency is ~15 min unless triggered by a checkpoint.

**Rejected Alternatives.**
- *Raw `git push` with only git hooks.* Rejected — easy to bypass (e.g. `--no-verify`) and risks pushing dirty working trees or pushing to wrong remotes without explicit programmatic barriers.
- *Push to main directly.* Rejected — limits safe review; all agents use named `agent/<date>-<topic>` branches to segregate work.

**Residual Risk.** Human gating on the first push and pre-push gitleaks reduces the blast radius to almost zero. The remaining risk relies on the `gh api` correctly verifying private repo status before data transmission.
