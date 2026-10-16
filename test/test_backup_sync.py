"""
test/test_backup_sync.py: Automated test suite for REQ-STORAGE-05 network-gated snapshot sync.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


def test_backup_sync_help():
    script = Path("scripts/backup-sync.sh").resolve()
    res = subprocess.run([str(script), "--help"], capture_output=True, text=True, check=True)
    assert "Usage:" in res.stdout
    assert "--dry-run" in res.stdout
    assert "--check-network" in res.stdout


def test_backup_sync_network_gate_unmetered(tmp_path: Path):
    script = Path("scripts/backup-sync.sh").resolve()
    env = dict(os.environ)
    env["CYBERDECK_MOCK_INTERFACE"] = "wlan0"
    res = subprocess.run(
        [str(script), "--check-network"],
        capture_output=True,
        text=True,
        env=env,
    )
    assert res.returncode == 0
    assert "PASS" in res.stdout or "Network gate approved" in res.stdout


def test_backup_sync_network_gate_blocks_cellular(tmp_path: Path):
    script = Path("scripts/backup-sync.sh").resolve()
    env = dict(os.environ)
    env["CYBERDECK_MOCK_INTERFACE"] = "usb0"
    res = subprocess.run(
        [str(script), "--check-network"],
        capture_output=True,
        text=True,
        env=env,
    )
    assert res.returncode == 2
    assert "BLOCKED on cellular/LTE" in res.stderr


def test_backup_sync_network_gate_override_with_force():
    script = Path("scripts/backup-sync.sh").resolve()
    env = dict(os.environ)
    env["CYBERDECK_MOCK_INTERFACE"] = "usb0"
    res = subprocess.run(
        [str(script), "--check-network", "--force"],
        capture_output=True,
        text=True,
        env=env,
    )
    assert res.returncode == 0
    assert "--force passed" in res.stdout


def test_backup_sync_dry_run(tmp_path: Path):
    script = Path("scripts/backup-sync.sh").resolve()
    dest = tmp_path / "backup_dest"
    env = dict(os.environ)
    env["CYBERDECK_MOCK_INTERFACE"] = "wlan0"
    env["CYBERDECK_BACKUP_DEST"] = str(dest)
    res = subprocess.run(
        [str(script), "--dry-run"],
        capture_output=True,
        text=True,
        env=env,
    )
    assert res.returncode == 0
    assert "DRY-RUN" in res.stdout
