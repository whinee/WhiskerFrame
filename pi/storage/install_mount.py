#!/usr/bin/env python3
r"""
Render and install the external-storage systemd ``.mount`` unit on the Pi.

Keep hardware-specific values (device UUID, mount point, filesystem type) out of
the committed repo: ``storage.mount.example`` holds ``@...@`` placeholders and
the live ``.whiskerframe.yaml`` ``storage`` block holds the real values. This
generator substitutes the two together, computes the systemd-escaped unit
filename from the mount point, and writes the result to
``/etc/systemd/system/`` plus a ``systemctl daemon-reload``.

Run on the Pi, as root, when ``storage.enabled`` is true. Defaults to
``--dry-run`` (print only); pass ``--apply`` to actually write and reload.
Enabling the unit (``systemctl enable --now``) is a deliberate separate manual
step and is never performed here; nor is any mkfs/mount.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
TEMPLATE = HERE / "storage.mount.example"
SYSTEMD_DIR = Path("/etc/systemd/system")


def load_storage_config() -> dict[str, Any]:
    r"""
    Load the ``storage`` block from ``.whiskerframe.yaml``.

    Reuse the project's ``load_yaml_config`` (``scripts/`` sits beside ``pi/``
    under the deploy root) when importable; otherwise read the yaml directly.

    Returns:
    `dict[str, Any]`: The ``storage`` mapping (empty when absent).

    """
    scripts_dir = HERE.parent.parent / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    try:
        from config import load_yaml_config  # type: ignore[import-not-found]

        loaded = load_yaml_config()
    except ImportError:
        import yaml

        root = HERE.parent.parent
        live = root / ".whiskerframe.yaml"
        example = root / ".whiskerframe.example.yaml"
        path = live if live.is_file() else example
        loaded = yaml.safe_load(path.read_text()) if path.is_file() else {}
    cfg = loaded if isinstance(loaded, dict) else {}
    storage = cfg.get("storage", {})
    return storage if isinstance(storage, dict) else {}


def systemd_escape(mount_point: str) -> str:
    r"""
    Return the systemd-escaped ``.mount`` unit filename for ``mount_point``.

    Prefer ``systemd-escape --path --suffix=mount`` for correctness; fall back to
    a local implementation when the binary is unavailable (e.g. off the Pi).

    Args:
    - mount_point (`str`): Absolute mount path, e.g. ``/mnt/ext-ssd``.

    Returns:
    `str`: Escaped unit filename, e.g. ``mnt-ext\x2dssd.mount``.

    """
    try:
        out = subprocess.run(
            ["systemd-escape", "--path", "--suffix=mount", mount_point],
            capture_output=True,
            text=True,
            check=True,
        )
        return out.stdout.strip()
    except (FileNotFoundError, subprocess.CalledProcessError):
        return _escape_path(mount_point) + ".mount"


def _escape_path(path: str) -> str:
    r"""
    Local reimplementation of ``systemd-escape --path``.

    Strip the leading slash, collapse ``/`` to ``-``, escape ``-`` to ``\x2d``,
    escape any other non-``[A-Za-z0-9_.]`` byte to ``\xNN``, and escape a leading
    digit or dot. An empty/root path escapes to ``-``.

    Args:
    - path (`str`): Absolute path to escape.

    Returns:
    `str`: Escaped name without the unit suffix.

    """
    stripped = path.strip("/")
    if not stripped:
        return "-"

    def esc_byte(b: int) -> str:
        return f"\\x{b:02x}"

    out: list[str] = []
    for ch in stripped:
        if ch == "/":
            out.append("-")
        elif ch == "-":
            out.append(esc_byte(ord("-")))
        elif re.match(r"[A-Za-z0-9_.]", ch):
            out.append(ch)
        else:
            out.extend(esc_byte(b) for b in ch.encode("utf-8"))
    name = "".join(out)
    # Leading digit or dot must be escaped.
    if name and (name[0].isdigit() or name[0] == "."):
        name = esc_byte(ord(name[0])) + name[1:]
    return name


def render_unit(storage: dict[str, Any]) -> str:
    r"""
    Render ``storage.mount.example`` with the storage config substituted.

    Args:
    - storage (`dict[str, Any]`): The ``storage`` config block.

    Returns:
    `str`: The rendered unit file contents.

    """
    text = TEMPLATE.read_text()
    fstype = str(storage.get("fstype", "ext4"))
    # Base options every mount gets: boot-safe (nofail) + bounded device wait.
    opts = ["nofail", "x-systemd.device-timeout=5s", "noatime"]
    # Filesystem-specific extras. For btrfs, mount a named subvolume (the data
    # subvolume) with zstd compression; the swap subvolume is mounted separately
    # by the memory-safety layer (nodatacow, uncompressed) and must NOT inherit
    # these options.
    if fstype == "btrfs":
        subvol = str(storage.get("subvol", "")).strip()
        if subvol:
            opts.append(f"subvol={subvol}")
        compress = str(storage.get("compress", "zstd")).strip()
        if compress:
            opts.append(f"compress={compress}")
    options = str(storage.get("options", "")).strip() or ",".join(opts)
    return (
        text.replace("@STORAGE_UUID@", str(storage.get("device_uuid", "")))
        .replace("@STORAGE_MOUNT_POINT@", str(storage.get("mount_point", "")))
        .replace("@STORAGE_FSTYPE@", fstype)
        .replace("@STORAGE_OPTIONS@", options)
    )


def main(argv: list[str] | None = None) -> int:
    r"""
    Entry point: render and (with ``--apply``) install the mount unit.

    Args:
    - argv (`list[str] | None`, optional): Argument vector (defaults to ``sys.argv``).

    Returns:
    `int`: Process exit code (``0`` on success or safe no-op).

    """
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="print the unit and target path without writing (default)",
    )
    group.add_argument(
        "--apply",
        action="store_true",
        help="write the unit to /etc/systemd/system and run daemon-reload (root, on the Pi)",
    )
    args = parser.parse_args(argv)
    apply = args.apply

    storage = load_storage_config()
    if not storage.get("enabled") or not str(storage.get("device_uuid", "")).strip():
        print("storage disabled or device_uuid empty in .whiskerframe.yaml; nothing to do.")
        return 0

    mount_point = str(storage.get("mount_point", "")).strip()
    if not mount_point:
        print("storage.mount_point is empty; refusing to generate a unit.")
        return 1

    unit_name = systemd_escape(mount_point)
    target = SYSTEMD_DIR / unit_name
    unit_text = render_unit(storage)

    if not apply:
        print(f"# --dry-run: would write {target}\n")
        print(unit_text)
        print("# re-run with --apply (as root, on the Pi) to write and daemon-reload.")
        print(f"# then enable manually:  systemctl enable --now {unit_name}")
        return 0

    target.write_text(unit_text)
    print(f"wrote {target}")
    subprocess.run(["systemctl", "daemon-reload"], check=True)
    print("daemon-reload done.")
    print(f"enable manually (separate step):  systemctl enable --now {unit_name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
