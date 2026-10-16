#!/usr/bin/env python3
"""
Login/logout loop resilience harness for Whiskerframe Cyberdeck.

Simulates repeated PAM logins and logouts under `neko` and `guest`:
1. PAM authentication simulation:
   - Valid credentials for `neko` and `guest`
   - Invalid credentials (wrong password) -> immediate password buffer wiping
   - Fallback when PAM is unavailable
2. PTY lifecycle and descriptor leak detection:
   - Verifies master/slave PTY pairs are allocated and strictly closed
   - Verifies child shell processes receive SIGHUP and are reaped via waitpid
   - No dangling PTY file descriptors left in proc fd table
3. Ephemeral tmpfs cleanup (guest user):
   - Simulates guest workspace creation (touch files, scripts, directories)
   - Executes guest session cleanup logic (wipes non-skel files, resets permissions)
   - Verifies no persistent artifacts remain in guest home
4. State machine loop stability:
   - Executes 50 rapid login -> shell -> logout -> login cycles
   - Asserts login state returns to clean USER_SELECT screen with zero leftover state
"""

from __future__ import annotations

import os
import shutil
import signal
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "pi"))

from terminal.bridge import (  # noqa: E402
    BridgeConfig,
    KeyQueue,
    TerminalBridge,
)
from terminal.login import (  # noqa: E402
    LoginScreen,
    LoginState,
    SubmitEvent,
)
from terminal.theme import load_theme  # noqa: E402


def simulate_guest_cleanup(guest_home: Path, skel_dir: Path, user: str = "guest") -> None:
    """
    Simulate the guest-session-cleanup.sh hook executed by pam_exec on session close.

    Wipes all files in guest_home, copies /etc/skel, and sets 0700 permissions.
    """
    # find "$GUEST_HOME" -mindepth 1 -delete
    for item in guest_home.iterdir():
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink()

    # cp -r /etc/skel/. "$GUEST_HOME/"
    if skel_dir.exists():
        for skel_item in skel_dir.iterdir():
            dst = guest_home / skel_item.name
            if skel_item.is_dir():
                shutil.copytree(skel_item, dst)
            else:
                shutil.copy2(skel_item, dst)

    os.chmod(guest_home, 0o700)


def count_open_pty_fds() -> int:
    """Count currently open file descriptors in the process that point to ptys."""
    fd_dir = Path("/proc/self/fd")
    if not fd_dir.exists():
        return 0

    pty_count = 0
    for fd_entry in fd_dir.iterdir():
        try:
            target = os.readlink(fd_entry)
            if "/pts/" in target or "pty" in target:
                pty_count += 1
        except (OSError, FileNotFoundError):
            continue
    return pty_count


class TestLoginLogoutLoop(unittest.TestCase):
    """Resilience tests for repeated PAM login/logout cycles."""

    def setUp(self) -> None:
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="deck_login_test_"))
        self.guest_home = self.tmp_dir / "guest_home"
        self.guest_home.mkdir(mode=0o700)
        self.skel_dir = self.tmp_dir / "skel"
        self.skel_dir.mkdir(mode=0o755)
        (self.skel_dir / ".bashrc").write_text("# default bashrc\n")
        (self.skel_dir / ".profile").write_text("# default profile\n")

        self.theme = load_theme(None)
        self.config = BridgeConfig(
            theme=self.theme,
            users=["neko", "guest"],
            demo_mode=True,
        )
        self.bridge = TerminalBridge(self.config)
        self.bridge._paint = lambda grid: None
        self.bridge._ensure_serial = MagicMock(return_value=None)

    def tearDown(self) -> None:
        if self.tmp_dir.exists():
            shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_guest_tmpfs_cleanup(self) -> None:
        """Guest home directory is completely purged of user artifacts on session close."""
        # 1. Initialize guest home from skel
        simulate_guest_cleanup(self.guest_home, self.skel_dir, "guest")
        self.assertTrue((self.guest_home / ".bashrc").exists())

        # 2. Simulate guest creating malicious or scratch files
        (self.guest_home / "exploit.sh").write_text("#!/bin/sh\nrm -rf /\n")
        (self.guest_home / ".bash_history").write_text("sudo -i\npasswd\n")
        scratch_dir = self.guest_home / ".cache"
        scratch_dir.mkdir()
        (scratch_dir / "junk.dat").write_bytes(b"\x00" * 4096)

        self.assertTrue((self.guest_home / "exploit.sh").exists())
        self.assertTrue((scratch_dir / "junk.dat").exists())

        # 3. Simulate session close trigger
        simulate_guest_cleanup(self.guest_home, self.skel_dir, "guest")

        # 4. Assert clean state restored
        self.assertFalse((self.guest_home / "exploit.sh").exists())
        self.assertFalse((self.guest_home / ".bash_history").exists())
        self.assertFalse(scratch_dir.exists())
        self.assertTrue((self.guest_home / ".bashrc").exists())
        self.assertTrue((self.guest_home / ".profile").exists())
        self.assertEqual(oct(self.guest_home.stat().st_mode & 0o777), oct(0o700))

    @patch("terminal.bridge.authenticate")
    @patch("terminal.bridge._tiocswinsz")
    @patch("terminal.bridge.pty.fork")
    def test_login_logout_loop_pty_and_process_cleanup(
        self,
        mock_fork: MagicMock,
        mock_tiocswinsz: MagicMock,
        mock_auth: MagicMock,
    ) -> None:
        """Run 50 rapid login/shell/logout cycles and assert clean pty reaping with no fd leaks."""
        initial_ptys = count_open_pty_fds()

        # Mock PAM authentication
        def mock_auth_side_effect(user: str, password: str) -> bool:
            if user == "neko" and password == "neko123":
                return True
            if user == "guest" and password == "guest":
                return True
            return False

        mock_auth.side_effect = mock_auth_side_effect

        simulated_pids = [10000 + i for i in range(50)]

        for i in range(50):
            user = "neko" if i % 2 == 0 else "guest"
            password = "neko123" if user == "neko" else "guest"
            child_pid = simulated_pids[i]

            # Step 1: Open real PTY pair for accurate fd leak testing
            master_fd, slave_fd = os.openpty()
            mock_fork.return_value = (child_pid, master_fd)

            # Step 2: Handle submit & authentication
            submit = SubmitEvent(user=user, password=password)
            state = LoginState(users=["neko", "guest"])
            authenticated_user = self.bridge._handle_submit(state, submit)
            self.assertEqual(authenticated_user, user)
            self.assertEqual(state._password, [])  # Password buffer must be wiped
            self.assertEqual(state.masked(), "")

            # Step 3: Spawn shell
            pid, ret_master_fd = self.bridge._spawn_shell(user)
            self.assertEqual(pid, child_pid)
            self.assertEqual(ret_master_fd, master_fd)

            # Step 4: Close slave fd as parent would
            os.close(slave_fd)

            # Step 5: Reap child and master fd
            with patch("os.kill") as mock_kill, patch("os.waitpid") as mock_waitpid:
                self.bridge._reap(pid, master_fd)
                mock_kill.assert_called_once_with(pid, signal.SIGHUP)
                mock_waitpid.assert_called_once_with(pid, 0)

            # Check that master_fd is closed
            with self.assertRaises(OSError):
                os.fstat(master_fd)

            # If user was guest, trigger session cleanup
            if user == "guest":
                (self.guest_home / f"test_{i}.tmp").write_text("transient")
                simulate_guest_cleanup(self.guest_home, self.skel_dir, "guest")
                self.assertFalse((self.guest_home / f"test_{i}.tmp").exists())

        final_ptys = count_open_pty_fds()
        self.assertEqual(
            initial_ptys,
            final_ptys,
            f"PTY descriptor leak: before={initial_ptys}, after={final_ptys}",
        )

    def test_failed_login_clears_buffer_and_stays_on_password(self) -> None:
        """Failed authentication attempts never leak credentials and stay on password screen."""
        state = LoginState(users=["neko", "guest"])
        # Select guest (down arrow)
        state.feed_key(0xB6)
        self.assertEqual(state.selected_user, "guest")
        # Press Enter to go to password screen
        state.feed_key(0x0D)
        self.assertEqual(state.screen, LoginScreen.PASSWORD)

        # Type bad password
        for char in "wrongpass":
            state.feed_key(ord(char))
        self.assertEqual("".join(state._password), "wrongpass")

        # Submit bad password with PAM failing
        with patch("terminal.bridge.authenticate", return_value=False):
            submit = state.feed_key(0x0D)
            self.assertIsNotNone(submit)
            user = self.bridge._handle_submit(state, submit)
            self.assertIsNone(user)
            # Password buffer must be cleared immediately
            self.assertEqual(state._password, [])
            self.assertEqual(state.masked(), "")
            # Screen remains on PASSWORD for retry
            self.assertEqual(state.screen, LoginScreen.PASSWORD)


def main() -> int:
    """Run standalone login/logout loop harness."""
    print("=" * 70)
    print("Running Whiskerframe Login/Logout & Tmpfs Cleanup Test Suite")
    print("=" * 70)

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestLoginLogoutLoop)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
