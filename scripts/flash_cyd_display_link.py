#!/usr/bin/env python3
"""
Non-destructive flashing script for ESP32 CYD display coprocessor.

Flashing the CYD is safety-critical and irreversible without a backup:
- Enforces the flash-backup safety gate (Req 7, scripts.flash_gate).
- Validates the 4 MiB factory backup before any write.
- Verifies SHA256 release checksums (firmware/dist/checksums.sha256).
- Non-destructive: writes targeted partitions with `write_flash -z`
  (no full-chip erase, preserving RF calibration/NVS).
- Supports --dry-run for pre-flight validation without hardware writes.
- Supports --app-only (0x10000 firmware.bin) and --restore (0x0 backup).
- Enforces Serial Exclusivity Lock (warns if terminal.service is active).
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import sys
from pathlib import Path

# Add scripts directory to sys.path if not present
_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from config import PROJECT_ROOT, load_yaml_config  # noqa: E402
from debug import tracepoint  # noqa: E402
from flash_gate import (  # noqa: E402
    EXPECTED_FLASH_SIZE,
    GateDecision,
    gate_decision,
    validate_backup,
)

__all__ = [
    "DEFAULT_BAUD",
    "FALLBACK_BAUD",
    "FLASH_OFFSETS",
    "build_flash_command",
    "check_serial_exclusivity",
    "main",
    "resolve_serial_port",
    "verify_checksums",
]

DEFAULT_BAUD: int = 460800
"""High-speed baud rate for flashing (fast, reliable write over CH340)."""

FALLBACK_BAUD: int = 115200
"""Safe baseline baud rate matching the firmware monitor speed."""

FLASH_OFFSETS: dict[str, int] = {
    "bootloader.bin": 0x1000,
    "partitions.bin": 0x8000,
    "boot_app0.bin": 0xE000,
    "firmware.bin": 0x10000,
}
"""Standard flash memory offsets for ESP32 Arduino / PlatformIO."""


def _parse_manifest(manifest_path: Path) -> dict[str, str]:
    """Parse key-value map from checksum manifest."""
    expected: dict[str, str] = {}
    content = manifest_path.read_text(encoding="utf-8")
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(maxsplit=1)
        if len(parts) == 2:
            expected[parts[1].lstrip("*").strip()] = parts[0]
    return expected


def _sha256_of(path: Path) -> str:
    """Compute sha256 hex digest of file."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def _check_one_file(dist_dir: Path, filename: str, expected_sha: str) -> str | None:
    """Check a single release binary file against expected sha256."""
    bin_path = dist_dir / filename
    if not bin_path.is_file():
        return f"Missing release binary: {bin_path}"
    actual_sha = _sha256_of(bin_path)
    if actual_sha.lower() != expected_sha.lower():
        return f"Checksum mismatch for {filename}: expected {expected_sha}, got {actual_sha}"
    return None


def verify_checksums(
    manifest_path: Path,
    dist_dir: Path,
) -> tuple[bool, dict[str, str], list[str]]:
    """
    Verify SHA256 checksums of distribution binaries against manifest.

    Args:
    - manifest_path: Path to checksums.sha256 file.
    - dist_dir: Directory containing candidate binary files.

    Returns:
    tuple of (is_valid, expected_hashes, error_messages).

    """
    if not manifest_path.is_file():
        return False, {}, [f"Checksum manifest missing: {manifest_path}"]

    expected_hashes = _parse_manifest(manifest_path)
    if not expected_hashes:
        return False, {}, [f"No valid checksum entries in {manifest_path}"]

    errors: list[str] = []
    for filename, expected_sha in expected_hashes.items():
        err = _check_one_file(dist_dir, filename, expected_sha)
        if err:
            errors.append(err)

    is_valid = len(errors) == 0
    tracepoint(
        "flash.checksums",
        manifest=str(manifest_path),
        valid=is_valid,
        file_count=len(expected_hashes),
        error_count=len(errors),
    )
    return is_valid, expected_hashes, errors


def resolve_serial_port(cli_port: str | None = None) -> str:
    """Resolve target serial port from CLI, config, or stable device paths."""
    if cli_port:
        return cli_port

    port_from_cfg = _port_from_yaml()
    if port_from_cfg:
        return port_from_cfg

    stable_ch340 = Path("/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0")
    if stable_ch340.exists():
        return str(stable_ch340)

    return "/dev/ttyUSB0"


def _port_from_yaml() -> str | None:
    """Read port from .whiskerframe.yaml safely."""
    try:
        conf = load_yaml_config()
        port = conf.get("cyd", {}).get("port")
        if port:
            return str(port)
        term_port = conf.get("terminal", {}).get("serial_port")
        if term_port:
            return str(term_port)
    except (OSError, ValueError):
        return None
    return None


def check_serial_exclusivity() -> tuple[bool, str | None]:
    """
    Check Serial Exclusivity Lock: warn if terminal.service is currently running.

    Returns (is_locked, warning_message).

    """
    systemctl = shutil.which("systemctl")
    if not systemctl:
        return False, None

    try:
        res = subprocess.run(  # noqa: S603
            [systemctl, "is-active", "terminal"],
            capture_output=True,
            text=True,
            timeout=2.0,
            check=False,
        )
        if res.stdout.strip() == "active":
            return True, (
                "terminal.service is active and holds serial port exclusively. "
                "Run 'systemctl stop terminal' before flashing."
            )
    except (subprocess.SubprocessError, OSError):
        return False, None

    return False, None


def build_flash_command(
    port: str,
    baud: int,
    dist_dir: Path,
    app_only: bool = False,
    restore_file: Path | None = None,
) -> list[str]:
    """
    Construct non-destructive esptool write_flash command.

    Uses `write_flash -z` (compressed) with explicit `--flash_size 4MB` (Req 7.2),
    preserving calibration, MAC address, and unwritten flash partitions.
    """
    import importlib.util

    if importlib.util.find_spec("esptool") is not None:
        base_cmd = [sys.executable, "-m", "esptool"]
    else:
        base_cmd = ["esptool"]
    cmd = base_cmd + [
        "--chip",
        "esp32",
        "--port",
        port,
        "--baud",
        str(baud),
        "--before",
        "default_reset",
        "--after",
        "hard_reset",
        "write_flash",
        "-z",
        "--flash_mode",
        "dio",
        "--flash_freq",
        "40m",
        "--flash_size",
        "4MB",
    ]

    if restore_file:
        cmd.extend(["0x0", str(restore_file)])
        return cmd

    if app_only:
        firmware_bin = dist_dir / "firmware.bin"
        cmd.extend([hex(FLASH_OFFSETS["firmware.bin"]), str(firmware_bin)])
        return cmd

    for filename in ("bootloader.bin", "partitions.bin", "boot_app0.bin", "firmware.bin"):
        path = dist_dir / filename
        if path.is_file():
            cmd.extend([hex(FLASH_OFFSETS[filename]), str(path)])

    return cmd


def _validate_manifest_flow(dist_dir: Path) -> bool:
    """Validate release checksums and print status."""
    manifest_path = dist_dir / "checksums.sha256"
    valid_sums, expected_hashes, sum_errors = verify_checksums(manifest_path, dist_dir)
    if not valid_sums:
        print("[FAIL] Checksum verification failed:")
        for err in sum_errors:
            print(f"  - {err}")
        return False
    print(f"[PASS] Verified checksums for {len(expected_hashes)} release binaries:")
    for name, sha in expected_hashes.items():
        print(f"  - {name}: {sha[:16]}...")
    return True


def _prompt_operator_confirm(confirmed: bool, dry_run: bool) -> bool:
    """Ask operator for confirmation when needed."""
    if confirmed or dry_run:
        return confirmed
    if sys.stdin.isatty():
        try:
            ans = input("Proceed with CYD flash write? [y/N]: ").strip().lower()
            return ans in ("y", "yes")
        except (EOFError, KeyboardInterrupt):
            return False
    print("[WARN] Non-interactive execution without --confirm (-y).")
    return False


def _check_safety_gate(backup_path: Path, confirmed: bool, dry_run: bool) -> bool:
    """Check flash safety gate preconditions."""
    backup_val = validate_backup(backup_path, EXPECTED_FLASH_SIZE)
    if not backup_val.valid:
        print(f"[FAIL] Flash safety gate: backup invalid ({backup_val.reason})")
        print(f"       Backup path checked: {backup_path}")
        print("       A validated 4 MiB backup is strictly required before any write (Req 7.3, 7.4).")
        return False

    print(f"[PASS] Flash safety gate: validated backup found ({backup_val.actual_size} bytes)")
    decision: GateDecision = gate_decision(backup_val, EXPECTED_FLASH_SIZE, confirmed)
    if not decision.permitted and not dry_run:
        print(f"[BLOCKED] Flash gate refused write: {decision.detail}")
        print("          Provide --confirm (-y) to authorize the flash write.")
        return False
    return True


def _exec_subprocess(cmd: list[str]) -> int:
    """Execute flash subprocess."""
    try:
        proc = subprocess.run(cmd, check=False)  # noqa: S603
        if proc.returncode == 0:
            print("[SUCCESS] CYD flash completed successfully.")
            return 0
        print(f"[FAIL] esptool exited with error code {proc.returncode}")
        return proc.returncode
    except FileNotFoundError:
        print(f"[FAIL] Python interpreter or esptool not found: {sys.executable}")
        return 127
    except OSError as e:
        print(f"[FAIL] Error during flashing: {e}")
        return 1


def _run_flash(cmd: list[str], port: str, baud: int, dry_run: bool, confirmed: bool) -> int:
    """Execute flash subprocess or report dry run."""
    cmd_str = " ".join(cmd)
    print("\nPlanned Flash Command:")
    print(f"  {cmd_str}\n")

    if dry_run:
        print("[DRY-RUN] Pre-flight checks passed. No flash writes performed.")
        if not confirmed:
            print("[DRY-RUN] Note: Write would require --confirm to authorize on live run.")
        return 0

    print(f"Writing to CYD at {port} ({baud} baud)...")
    return _exec_subprocess(cmd)


def _create_arg_parser() -> argparse.ArgumentParser:
    """Create CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="Non-destructive flashing tool for WhiskerFrame CYD display link.",
    )
    parser.add_argument(
        "--port",
        "-p",
        help="Target serial port (default: from .whiskerframe.yaml or /dev/serial/by-id/...)",
    )
    parser.add_argument(
        "--baud",
        "-b",
        type=int,
        default=DEFAULT_BAUD,
        help=f"Flashing baud rate (default: {DEFAULT_BAUD})",
    )
    parser.add_argument(
        "--dist-dir",
        "-d",
        type=Path,
        default=PROJECT_ROOT / "firmware" / "dist",
        help="Directory with release binaries (default: firmware/dist)",
    )
    parser.add_argument(
        "--backup",
        type=Path,
        default=PROJECT_ROOT / "cyd_factory_backup.bin",
        help="Path to factory backup file (default: cyd_factory_backup.bin)",
    )
    parser.add_argument(
        "--app-only",
        action="store_true",
        help="Flash application firmware only (0x10000 firmware.bin)",
    )
    parser.add_argument(
        "--restore",
        action="store_true",
        help="Non-destructive rollback: restore 4 MiB factory backup to 0x0",
    )
    parser.add_argument(
        "--dry-run",
        "-n",
        action="store_true",
        help="Simulate validation, checks, and command generation without writing flash",
    )
    parser.add_argument(
        "--confirm",
        "-y",
        action="store_true",
        help="Explicit operator confirmation required to authorize flash write (Req 7.5)",
    )
    parser.add_argument(
        "--skip-checksums",
        action="store_true",
        help="Skip release checksum verification (not recommended)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for non-destructive CYD flashing."""
    parser = _create_arg_parser()
    args = parser.parse_args(argv)

    print("=== WhiskerFrame CYD Display Link Flasher ===")

    dist_dir = args.dist_dir.resolve()
    backup_path = args.backup.resolve()
    port = resolve_serial_port(args.port)

    is_locked, lock_warning = check_serial_exclusivity()
    if is_locked and lock_warning:
        print(f"[WARN] {lock_warning}")

    if not args.restore and not args.skip_checksums and not _validate_manifest_flow(dist_dir):
        return 1

    confirmed = _prompt_operator_confirm(args.confirm, args.dry_run)
    if not _check_safety_gate(backup_path, confirmed, args.dry_run):
        return 1

    restore_target = backup_path if args.restore else None
    cmd = build_flash_command(
        port=port,
        baud=args.baud,
        dist_dir=dist_dir,
        app_only=args.app_only,
        restore_file=restore_target,
    )

    return _run_flash(cmd, port, args.baud, args.dry_run, confirmed)


if __name__ == "__main__":
    sys.exit(main())
