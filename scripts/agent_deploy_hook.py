#!/usr/bin/env python3
"""
Agent Lifecycle Deployment Hook for WhiskerFrame Cyberdeck.

Integrates with Claude Code's native lifecycle hooks:
- PostToolUse (Write|Edit): Inspects modified files, ignores non-deployable paths
  (docs, tests, temp, scratchpads), and coalesces relevant changes into a queue.
- Stop: Processes queued changes as a single atomic deployment batch, runs
  preflights, triggers `just apply` or firmware flashing, verifies service health,
  and reports results back to the agent context.

Provides concurrency protection via file locks, prevents deployment loops,
avoids redundant firmware flashing using content hashing, and exposes explicit
retry commands.
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from config import PROJECT_ROOT, env  # noqa: E402

QUEUE_FILE = PROJECT_ROOT / ".claude" / "deploy_queue.json"
LOCK_FILE = PROJECT_ROOT / ".claude" / "deploy.lock"
FIRMWARE_HASH_FILE = PROJECT_ROOT / ".claude" / "last_firmware_sha.txt"
LAST_DEPLOY_FILE = PROJECT_ROOT / ".claude" / "last_deploy_state.json"

RELEVANT_PREFIXES = (
    "whiskerframe/",
    "pi/",
    "firmware/",
    "scripts/",
)

RELEVANT_EXACT_FILES = {
    ".whiskerframe.yaml",
    "justfile",
    "pyproject.toml",
}

IGNORED_DIR_PREFIXES = (
    "docs/",
    "docs copy/",
    "test/",
    ".claude/",
    ".git/",
    ".history/",
    ".ruff_cache/",
    ".mypy_cache/",
    "__pycache__/",
    "temp/",
    "tmp/",
    "3D Models/",
)

IGNORED_EXTENSIONS = (
    ".md",
    ".tmp",
    ".log",
    ".png",
    ".txt",
    ".pyc",
    ".stl",
)


def is_relevant_file(path_str: str) -> bool:
    """Return True if path_str is a cyberdeck runtime or firmware asset."""
    try:
        p = Path(path_str).resolve()
        rel = p.relative_to(PROJECT_ROOT).as_posix()
    except (ValueError, OSError):
        rel = path_str.replace("\\", "/").lstrip("./")

    # Explicit exclusion of hook self-modifications
    if rel == "scripts/agent_deploy_hook.py":
        return False

    # Check directory ignore prefixes
    for prefix in IGNORED_DIR_PREFIXES:
        if rel.startswith(prefix) or f"/{prefix}" in rel:
            return False

    # Check ignored extensions
    for ext in IGNORED_EXTENSIONS:
        if rel.endswith(ext):
            return False

    # Exact project config files
    if rel in RELEVANT_EXACT_FILES:
        return True

    # Check relevant prefixes and valid extensions
    if rel.startswith("whiskerframe/") and rel.endswith(".py"):
        return True
    if rel.startswith("pi/") and (
        rel.endswith(".py") or rel.endswith(".service") or rel.startswith("pi/bin/")
    ):
        return True
    if rel.startswith("firmware/") and (
        rel.endswith((".cpp", ".h", ".ini"))
    ):
        return True
    if rel.startswith("scripts/") and rel.endswith(".py"):
        return True

    return False


def is_firmware_file(path_str: str) -> bool:
    """Return True if path_str is part of CYD display link firmware."""
    rel = path_str.replace("\\", "/").lstrip("/")
    return rel.startswith("firmware/") and not rel.startswith("firmware/dist/")


class DeployLock:
    """Process-based concurrency lock using .claude/deploy.lock."""

    def __init__(self, lock_path: Path = LOCK_FILE, timeout_s: float = 120.0):
        self.lock_path = lock_path
        self.timeout_s = timeout_s
        self.acquired = False

    def acquire(self) -> bool:
        """Attempt to acquire the file lock; evict stale lock if PID is dead."""
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        start = time.time()
        while time.time() - start < self.timeout_s:
            try:
                fd = os.open(
                    self.lock_path,
                    os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                    0o644,
                )
                with os.fdopen(fd, "w") as f:
                    json.dump(
                        {"pid": os.getpid(), "timestamp": time.time()},
                        f,
                    )
                self.acquired = True
                return True
            except FileExistsError:
                # Check for stale lock
                try:
                    content = json.loads(self.lock_path.read_text(encoding="utf-8"))
                    pid = content.get("pid")
                    ts = content.get("timestamp", 0)
                    # Check if process is still alive
                    if pid and not self._is_pid_alive(pid):
                        # Evict stale lock
                        self.lock_path.unlink(missing_ok=True)
                        continue
                    if time.time() - ts > self.timeout_s:
                        # Timeout eviction
                        self.lock_path.unlink(missing_ok=True)
                        continue
                except Exception:
                    pass
                time.sleep(0.2)
        return False

    def release(self) -> None:
        """Release lock if acquired."""
        if self.acquired:
            self.lock_path.unlink(missing_ok=True)
            self.acquired = False

    def __enter__(self) -> DeployLock:
        if not self.acquire():
            raise RuntimeError(f"Could not acquire deploy lock at {self.lock_path}")
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.release()

    @staticmethod
    def _is_pid_alive(pid: int) -> bool:
        if pid <= 0:
            return False
        try:
            os.kill(pid, 0)
            return True
        except (OSError, ProcessLookupError):
            return False


def load_queue() -> dict[str, Any]:
    """Load deployment queue from QUEUE_FILE."""
    if not QUEUE_FILE.is_file():
        return {"files": [], "has_firmware": False, "has_runtime": False}
    try:
        data = json.loads(QUEUE_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict) and "files" in data:
            return data
    except Exception:
        pass
    return {"files": [], "has_firmware": False, "has_runtime": False}


def save_queue(data: dict[str, Any]) -> None:
    """Save deployment queue to QUEUE_FILE."""
    QUEUE_FILE.parent.mkdir(parents=True, exist_ok=True)
    QUEUE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def clear_queue() -> None:
    """Remove QUEUE_FILE."""
    QUEUE_FILE.unlink(missing_ok=True)


def compute_firmware_sha() -> str:
    """Compute sha256 hash across all firmware source files."""
    firmware_dir = PROJECT_ROOT / "firmware" / "cyd_display_link"
    if not firmware_dir.is_dir():
        return ""
    h = hashlib.sha256()
    for root, _, files in sorted(os.walk(firmware_dir)):
        # Skip .pio
        if ".pio" in root:
            continue
        for f in sorted(files):
            p = Path(root) / f
            if p.suffix in (".cpp", ".h", ".ini"):
                h.update(p.read_bytes())
    return h.hexdigest()


def handle_post_tool_use(payload: dict[str, Any]) -> dict[str, Any]:
    """Handle PostToolUse hook event by queuing relevant modified files."""
    tool_input = payload.get("tool_input", {})
    file_path = tool_input.get("file_path") or tool_input.get("path")
    if not file_path:
        return {"continue": True}

    if not is_relevant_file(file_path):
        return {"continue": True}

    try:
        rel = Path(file_path).resolve().relative_to(PROJECT_ROOT).as_posix()
    except Exception:
        rel = str(file_path)

    queue = load_queue()
    if rel not in queue["files"]:
        queue["files"].append(rel)
    if is_firmware_file(rel):
        queue["has_firmware"] = True
    else:
        queue["has_runtime"] = True
    queue["last_updated"] = time.time()
    save_queue(queue)

    return {"continue": True}


def run_command(cmd: list[str] | str, cwd: Path = PROJECT_ROOT) -> tuple[int, str]:
    """Run shell command, returning (exit_code, combined_output)."""
    shell = isinstance(cmd, str)
    proc = subprocess.run(
        cmd,
        cwd=cwd,
        shell=shell,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    return proc.returncode, proc.stdout.strip()


def deploy_queued_changes(queue: dict[str, Any]) -> dict[str, Any]:
    """Execute deployment for queued changes."""
    files = queue.get("files", [])
    if not files:
        return {"continue": True}

    with DeployLock():
        results: list[str] = []
        has_firmware = queue.get("has_firmware", False)
        has_runtime = queue.get("has_runtime", False)

        # 1. Preflight tests
        code, out = run_command(["just", "preflight"])
        if code != 0:
            error_msg = (
                f"[DEPLOY BLOCKED] Pre-deploy tests failed with code {code}:\n"
                f"{out[:600]}\n"
                f"Queued files ({len(files)}) remain pending. "
                "Fix tests and run 'just apply' to retry."
            )
            return {"continue": True, "systemMessage": error_msg}

        results.append("Preflight tests passed.")

        # 2. Firmware build & flash if needed
        if has_firmware:
            current_fw_sha = compute_firmware_sha()
            last_fw_sha = (
                FIRMWARE_HASH_FILE.read_text().strip()
                if FIRMWARE_HASH_FILE.is_file()
                else ""
            )

            if current_fw_sha and current_fw_sha != last_fw_sha:
                results.append("Firmware sources changed: building...")
                code, out = run_command(["just", "build-firmware"])
                if code != 0:
                    return {
                        "continue": True,
                        "systemMessage": f"[FIRMWARE BUILD FAILED]\n{out[:500]}",
                    }

                results.append("Flashing CYD display link over Pi serial link...")
                code, out = run_command(["just", "flash-firmware"])
                if code != 0:
                    return {
                        "continue": True,
                        "systemMessage": f"[CYD FLASH FAILED]\n{out[:500]}",
                    }

                FIRMWARE_HASH_FILE.parent.mkdir(parents=True, exist_ok=True)
                FIRMWARE_HASH_FILE.write_text(current_fw_sha)
                results.append("CYD firmware flashed successfully.")
            else:
                results.append("Firmware sources unchanged; skipping re-flash.")

        # 3. Runtime deployment (sync + restart terminal.service)
        if has_runtime:
            code, out = run_command(["just", "sync"])
            if code != 0:
                return {
                    "continue": True,
                    "systemMessage": f"[SYNC FAILED]\n{out[:500]}",
                }
            pi_host = env("PI_HOST", "10.0.0.212")
            pi_user = env("PI_USER", "root")
            key_path = env("DEFAULT_KEY_PATH", str(Path.home() / ".ssh" / "id_rsa"))
            ssh_cmd = [
                "ssh",
                "-i",
                key_path,
                f"{pi_user}@{pi_host}",
                "systemctl restart terminal && systemctl is-active terminal",
            ]
            code, out = run_command(ssh_cmd)
            if code != 0:
                return {
                    "continue": True,
                    "systemMessage": f"[RUNTIME ACTIVATION FAILED]\n{out[:500]}",
                }
            results.append("Runtime deployed and terminal.service active.")

        # 4. Save state and clear queue
        clear_queue()
        LAST_DEPLOY_FILE.parent.mkdir(parents=True, exist_ok=True)
        LAST_DEPLOY_FILE.write_text(
            json.dumps(
                {
                    "deployed_at": time.time(),
                    "files": files,
                    "status": "success",
                },
                indent=2,
            ),
        )

        summary = (
            f"[CYBERDECK AUTO-DEPLOY SUCCESS]\n"
            f"Coalesced files ({len(files)}): {', '.join(files[:6])}"
            f"{'...' if len(files) > 6 else ''}\n"
            f"Actions: {' -> '.join(results)}"
        )
        return {"continue": True, "systemMessage": summary}


def handle_stop(payload: dict[str, Any]) -> dict[str, Any]:
    """Handle Stop hook event by coalescing and deploying all queued edits."""
    queue = load_queue()
    if not queue.get("files"):
        return {"continue": True}
    return deploy_queued_changes(queue)


def main() -> int:
    """CLI entry point for lifecycle hook execution and manual triggers."""
    parser = argparse.ArgumentParser(
        description="WhiskerFrame Agent Lifecycle Deploy Hook",
    )
    parser.add_argument(
        "--event",
        choices=["PostToolUse", "Stop", "PreToolUse"],
        help="Hook event name passed by agent harness",
    )
    parser.add_argument(
        "--deploy",
        action="store_true",
        help="Manually trigger deployment of queued or current changes",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Inspect queued changes and lock status",
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear queued changes without deploying",
    )

    args, _ = parser.parse_known_args()

    if args.status:
        q = load_queue()
        print(f"Queued files: {len(q.get('files', []))}")
        for f in q.get("files", []):
            print(f"  - {f}")
        print(f"Lock active: {LOCK_FILE.exists()}")
        return 0

    if args.clear:
        clear_queue()
        print("Queue cleared.")
        return 0

    if args.deploy:
        q = load_queue()
        if not q.get("files"):
            print("No queued files. Checking git status for relevant modified files...")
            code, out = run_command(["git", "status", "--porcelain"])
            modified: list[str] = []
            for line in out.splitlines():
                if len(line) > 3:
                    path = line[3:].strip()
                    if is_relevant_file(path):
                        modified.append(path)
            if not modified:
                print("No relevant modified files found.")
                return 0
            q = {
                "files": modified,
                "has_firmware": any(is_firmware_file(f) for f in modified),
                "has_runtime": any(not is_firmware_file(f) for f in modified),
            }
        res = deploy_queued_changes(q)
        print(res.get("systemMessage", "Deployment complete."))
        return 0

    # Hook invocation via stdin
    payload: dict[str, Any] = {}
    if not sys.stdin.isatty():
        try:
            raw = sys.stdin.read()
            if raw.strip():
                payload = json.loads(raw)
        except Exception:
            pass

    event = args.event or payload.get("hook_event_name")

    if event == "PostToolUse":
        resp = handle_post_tool_use(payload)
        print(json.dumps(resp))
        return 0

    if event == "Stop":
        resp = handle_stop(payload)
        print(json.dumps(resp))
        return 0

    print(json.dumps({"continue": True}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
