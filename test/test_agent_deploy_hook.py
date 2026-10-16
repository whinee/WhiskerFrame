"""Tests for scripts/agent_deploy_hook.py."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts.agent_deploy_hook import (
    DeployLock,
    clear_queue,
    compute_firmware_sha,
    deploy_queued_changes,
    handle_post_tool_use,
    handle_stop,
    is_firmware_file,
    is_relevant_file,
    load_queue,
    save_queue,
)


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("whiskerframe/display/bridge.py", True),
        ("pi/bin/cyd-terminal", True),
        ("pi/terminal.service", True),
        ("firmware/cyd_display_link/main.cpp", True),
        ("firmware/cyd_display_link/platformio.ini", True),
        ("scripts/flash_cyd_display_link.py", True),
        ("justfile", True),
        ("pyproject.toml", True),
        (".whiskerframe.yaml", True),
        # Ignored files
        ("docs/README.md", False),
        ("docs copy/notes.md", False),
        ("test/test_bridge.py", False),
        (".claude/settings.json", False),
        (".git/HEAD", False),
        (".history/recent.json", False),
        ("temp/scratchpad.txt", False),
        ("scripts/agent_deploy_hook.py", False),
        ("3D Models/enclosure.stl", False),
        ("output.log", False),
        ("capture.png", False),
    ],
)
def test_is_relevant_file(path: str, expected: bool) -> None:
    assert is_relevant_file(path) is expected


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("firmware/cyd_display_link/main.cpp", True),
        ("firmware/cyd_display_link/platformio.ini", True),
        ("firmware/dist/firmware.bin", False),
        ("firmware/dist/checksums.sha256", False),
        ("whiskerframe/main.py", False),
    ],
)
def test_is_firmware_file(path: str, expected: bool) -> None:
    assert is_firmware_file(path) is expected


def test_queue_lifecycle(tmp_path: Path) -> None:
    test_queue_file = tmp_path / "deploy_queue.json"
    with patch("scripts.agent_deploy_hook.QUEUE_FILE", test_queue_file):
        # Empty queue initially
        assert load_queue()["files"] == []

        # PostToolUse with ignored file
        resp = handle_post_tool_use({"tool_input": {"file_path": "docs/README.md"}})
        assert resp == {"continue": True}
        assert load_queue()["files"] == []

        # PostToolUse with relevant runtime file
        resp = handle_post_tool_use(
            {"tool_input": {"file_path": "whiskerframe/display/bridge.py"}},
        )
        assert resp == {"continue": True}
        q = load_queue()
        assert "whiskerframe/display/bridge.py" in q["files"]
        assert q["has_runtime"] is True
        assert q["has_firmware"] is False

        # PostToolUse with firmware file (deduplicated)
        handle_post_tool_use(
            {"tool_input": {"file_path": "firmware/cyd_display_link/main.cpp"}},
        )
        handle_post_tool_use(
            {"tool_input": {"file_path": "firmware/cyd_display_link/main.cpp"}},
        )
        q = load_queue()
        assert len(q["files"]) == 2
        assert q["has_firmware"] is True

        # Clear queue
        clear_queue()
        assert not test_queue_file.exists()
        assert load_queue()["files"] == []


def test_deploy_lock_concurrency(tmp_path: Path) -> None:
    lock_file = tmp_path / "deploy.lock"
    lock1 = DeployLock(lock_path=lock_file, timeout_s=0.5)
    lock2 = DeployLock(lock_path=lock_file, timeout_s=0.2)

    assert lock1.acquire() is True
    assert lock1.acquired is True

    # lock2 should fail because lock1 is held by active PID
    assert lock2.acquire() is False

    lock1.release()
    assert lock1.acquired is False

    # lock2 should now succeed
    assert lock2.acquire() is True
    lock2.release()


def test_deploy_lock_stale_pid_eviction(tmp_path: Path) -> None:
    lock_file = tmp_path / "deploy.lock"
    # Write a dead PID into lock file
    lock_file.write_text(json.dumps({"pid": 9999999, "timestamp": 0}))

    lock = DeployLock(lock_path=lock_file, timeout_s=0.5)
    # Should evict dead PID and acquire
    assert lock.acquire() is True
    lock.release()


def test_deploy_blocked_by_preflight_failure(tmp_path: Path) -> None:
    lock_file = tmp_path / "deploy.lock"
    queue = {
        "files": ["whiskerframe/display/bridge.py"],
        "has_runtime": True,
        "has_firmware": False,
    }

    with (
        patch("scripts.agent_deploy_hook.LOCK_FILE", lock_file),
        patch(
            "scripts.agent_deploy_hook.run_command",
            return_value=(1, "FAILED test_bridge.py::test_fail"),
        ) as mock_run,
    ):
        result = deploy_queued_changes(queue)
        assert "[DEPLOY BLOCKED]" in result["systemMessage"]
        # Only preflight was executed, sync/activation was not called
        assert mock_run.call_count == 1
        assert "preflight" in mock_run.call_args[0][0]


def test_deploy_runtime_success(tmp_path: Path) -> None:
    lock_file = tmp_path / "deploy.lock"
    queue_file = tmp_path / "deploy_queue.json"
    queue_file.write_text(
        json.dumps(
            {
                "files": ["whiskerframe/display/bridge.py"],
                "has_runtime": True,
                "has_firmware": False,
            },
        ),
    )

    with (
        patch("scripts.agent_deploy_hook.LOCK_FILE", lock_file),
        patch("scripts.agent_deploy_hook.QUEUE_FILE", queue_file),
        patch(
            "scripts.agent_deploy_hook.run_command",
            return_value=(0, "Success"),
        ) as mock_run,
    ):
        result = deploy_queued_changes(load_queue())
        assert "[CYBERDECK AUTO-DEPLOY SUCCESS]" in result["systemMessage"]
        assert "Preflight tests passed" in result["systemMessage"]
        assert "Runtime deployed" in result["systemMessage"]
        # Calls: 1. preflight, 2. just sync, 3. ssh activate
        assert mock_run.call_count == 3
        assert not queue_file.exists()


def test_deploy_firmware_sha_caching(tmp_path: Path) -> None:
    lock_file = tmp_path / "deploy.lock"
    queue_file = tmp_path / "deploy_queue.json"
    fw_hash_file = tmp_path / "last_firmware_sha.txt"

    queue = {
        "files": ["firmware/cyd_display_link/main.cpp"],
        "has_runtime": False,
        "has_firmware": True,
    }

    current_sha = "abcdef123456"
    fw_hash_file.write_text(current_sha)

    with (
        patch("scripts.agent_deploy_hook.LOCK_FILE", lock_file),
        patch("scripts.agent_deploy_hook.QUEUE_FILE", queue_file),
        patch("scripts.agent_deploy_hook.FIRMWARE_HASH_FILE", fw_hash_file),
        patch(
            "scripts.agent_deploy_hook.compute_firmware_sha",
            return_value=current_sha,
        ),
        patch(
            "scripts.agent_deploy_hook.run_command",
            return_value=(0, "Success"),
        ) as mock_run,
    ):
        result = deploy_queued_changes(queue)
        assert "Firmware sources unchanged; skipping re-flash." in result["systemMessage"]
        # Only preflight and apply were run, NOT build-firmware or flash-firmware
        cmds = [call[0][0] for call in mock_run.call_args_list]
        assert not any("build-firmware" in cmd for cmd in cmds)
        assert not any("flash-firmware" in cmd for cmd in cmds)
