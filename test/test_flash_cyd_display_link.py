"""
Tests for non-destructive CYD display link flashing script (scripts/flash_cyd_display_link.py).

Validates:
- Checksum verification of distribution binaries against checksums.sha256.
- Safety gate enforcement (Req 7: validated 4 MiB backup, explicit confirmation).
- Command line generation (full flash offsets, app-only, restore).
- Dry-run mode execution and safety blocks.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from flash_cyd_display_link import (  # noqa: E402
    DEFAULT_BAUD,
    FLASH_OFFSETS,
    build_flash_command,
    check_serial_exclusivity,
    main,
    resolve_serial_port,
    verify_checksums,
)


def test_verify_checksums_valid(tmp_path: Path) -> None:
    """Valid binaries matching manifest pass checksum verification."""
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()

    file_a = dist_dir / "bootloader.bin"
    file_b = dist_dir / "firmware.bin"
    file_a.write_bytes(b"bootloader_test_data")
    file_b.write_bytes(b"firmware_test_data")

    sha_a = hashlib.sha256(file_a.read_bytes()).hexdigest()
    sha_b = hashlib.sha256(file_b.read_bytes()).hexdigest()

    manifest = dist_dir / "checksums.sha256"
    manifest.write_text(
        f"{sha_a}  bootloader.bin\n{sha_b}  firmware.bin\n",
        encoding="utf-8",
    )

    is_valid, expected, errors = verify_checksums(manifest, dist_dir)
    assert is_valid is True
    assert len(expected) == 2
    assert len(errors) == 0


def test_verify_checksums_missing_file(tmp_path: Path) -> None:
    """Manifest referencing missing binary fails verification."""
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()

    manifest = dist_dir / "checksums.sha256"
    manifest.write_text("1122334455  nonexistent.bin\n", encoding="utf-8")

    is_valid, _expected, errors = verify_checksums(manifest, dist_dir)
    assert is_valid is False
    assert any("Missing release binary" in err for err in errors)


def test_verify_checksums_mismatch(tmp_path: Path) -> None:
    """Tampered or corrupted binary fails verification."""
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()

    file_a = dist_dir / "firmware.bin"
    file_a.write_bytes(b"original_content")

    manifest = dist_dir / "checksums.sha256"
    manifest.write_text(
        "0000000000000000000000000000000000000000000000000000000000000000  firmware.bin\n",
    )

    is_valid, _expected, errors = verify_checksums(manifest, dist_dir)
    assert is_valid is False
    assert any("Checksum mismatch" in err for err in errors)


def test_build_flash_command_full(tmp_path: Path) -> None:
    """Full flash command includes bootloader, partitions, firmware, and explicit size."""
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    (dist_dir / "bootloader.bin").write_bytes(b"bl")
    (dist_dir / "partitions.bin").write_bytes(b"pt")
    (dist_dir / "firmware.bin").write_bytes(b"fw")

    cmd = build_flash_command(
        port="/dev/ttyUSB0",
        baud=DEFAULT_BAUD,
        dist_dir=dist_dir,
        app_only=False,
    )

    assert "esptool" in cmd
    assert "/dev/ttyUSB0" in cmd
    assert str(DEFAULT_BAUD) in cmd
    assert "--flash_size" in cmd
    assert "4MB" in cmd
    assert "write_flash" in cmd
    assert "-z" in cmd

    # Verify offsets
    cmd_str = " ".join(cmd)
    assert hex(FLASH_OFFSETS["bootloader.bin"]) in cmd_str
    assert hex(FLASH_OFFSETS["partitions.bin"]) in cmd_str
    assert hex(FLASH_OFFSETS["firmware.bin"]) in cmd_str


def test_build_flash_command_app_only(tmp_path: Path) -> None:
    """App-only flash targets only 0x10000 firmware.bin."""
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    (dist_dir / "firmware.bin").write_bytes(b"fw")

    cmd = build_flash_command(
        port="/dev/ttyUSB0",
        baud=115200,
        dist_dir=dist_dir,
        app_only=True,
    )

    assert hex(FLASH_OFFSETS["firmware.bin"]) in cmd
    assert hex(FLASH_OFFSETS["bootloader.bin"]) not in cmd
    assert hex(FLASH_OFFSETS["partitions.bin"]) not in cmd


def test_build_flash_command_restore(tmp_path: Path) -> None:
    """Restore mode flashes full factory backup to 0x0."""
    backup_file = tmp_path / "cyd_factory_backup.bin"
    backup_file.write_bytes(b"backup_data")

    cmd = build_flash_command(
        port="/dev/ttyUSB0",
        baud=DEFAULT_BAUD,
        dist_dir=tmp_path,
        restore_file=backup_file,
    )

    cmd_str = " ".join(cmd)
    assert "0x0 " + str(backup_file) in cmd_str


def test_resolve_serial_port_cli_override() -> None:
    """Explicit CLI port overrides config and auto-discovery."""
    assert resolve_serial_port("/dev/custom_cyd") == "/dev/custom_cyd"


def test_check_serial_exclusivity_callable() -> None:
    """Serial exclusivity probe executes without error."""
    is_locked, warning = check_serial_exclusivity()
    assert isinstance(is_locked, bool)
    if is_locked:
        assert isinstance(warning, str)


def test_dry_run_with_repo_artifacts() -> None:
    """Dry run against live repository dist and backup succeeds with code 0."""
    ret = main(["--dry-run", "--confirm"])
    assert ret == 0


def test_dry_run_app_only() -> None:
    """Dry run app-only succeeds with code 0."""
    ret = main(["--dry-run", "--app-only"])
    assert ret == 0


def test_dry_run_restore() -> None:
    """Dry run restore succeeds with code 0."""
    ret = main(["--dry-run", "--restore"])
    assert ret == 0


def test_main_missing_backup_aborts(tmp_path: Path) -> None:
    """Live or dry run with invalid backup fails flash gate (Req 7.4)."""
    ret = main(["--backup", str(tmp_path / "missing.bin"), "--confirm"])
    assert ret != 0


def test_main_unconfirmed_blocks_live_run() -> None:
    """Unconfirmed live run is blocked by gate (Req 7.5)."""
    # Non-interactive stdin ensures confirmation is not granted
    ret = main(["--port", "/dev/null"])
    assert ret != 0
