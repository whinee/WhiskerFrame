#!/usr/bin/env python3
"""
Automated test suite for unified WhiskerFrame Cyberdeck CLI (pi/bin/wf).

Validates:
1. Strict <= 53 column enforcement on all output lines across all subcommands.
2. Complete offline manual (wf man) covering topics:
   - kb (CardKB shortcuts, sticky Ctrl latch, font chords)
   - wifi (NetworkManager, 2.4 GHz ONLY hardware bounds)
   - demo (kernel sandbox, ephemeral tmpfs, reaper, PAM autostart)
   - terminal (CYD serial link, opcodes, font geometries)
   - workspaces (session manager, lifecycle)
3. Reuse and delegation to pi/bin/wifi for wifi subcommands (status, scan, join, forget).
4. Demo sandbox (wf demo) and artwork display (wf demo art).
5. Terminal and workspace management (list, new, switch, close) with session state isolation.
6. Guest PAM login auto-start demo integration.
"""

from __future__ import annotations

import importlib.util
import io
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from importlib.machinery import SourceFileLoader
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parent.parent
WF_CLI_PATH = REPO_ROOT / "pi" / "bin" / "wf"
WIFI_CLI_PATH = REPO_ROOT / "pi" / "bin" / "wifi"

# Dynamically load pi/bin/wf
loader = SourceFileLoader("wf_cli", str(WF_CLI_PATH))
spec = importlib.util.spec_from_loader("wf_cli", loader)
if spec is None or spec.loader is None:
    msg = f"Cannot load wf script from {WF_CLI_PATH}"
    raise ImportError(msg)
wf = importlib.util.module_from_spec(spec)
sys.modules["wf_cli"] = wf
loader.exec_module(wf)


class TestWhiskerFrameCLI(unittest.TestCase):
    """Test suite for pi/bin/wf executable and offline manual."""

    def setUp(self) -> None:
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="wf_test_"))
        self.ws_file = self.tmp_dir / "workspaces.json"
        os.environ["WF_WORKSPACE_FILE"] = str(self.ws_file)

    def tearDown(self) -> None:
        os.environ.pop("WF_WORKSPACE_FILE", None)
        if self.tmp_dir.exists():
            shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _run_wf(self, args: list[str]) -> tuple[int, list[str]]:
        """Run wf.main(args) capturing stdout and returning (exit_code, lines)."""
        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()
        with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
            code = wf.main(args)
        raw_output = stdout_buf.getvalue() + stderr_buf.getvalue()
        lines = [line.rstrip("\r\n") for line in raw_output.splitlines()]
        return code, lines

    def _assert_bounded_53_cols(self, lines: list[str], context: str) -> None:
        """Assert that every single output line is <= 53 columns."""
        for idx, line in enumerate(lines):
            self.assertLessEqual(
                len(line),
                53,
                f"Line {idx + 1} exceeds 53 columns in {context}: '{line}' ({len(line)} cols)",
            )

    # --- 1. Top-Level and Help Tests -----------------------------------------

    def test_wf_no_args_shows_main_help_bounded(self) -> None:
        """Invoking 'wf' without args displays help strictly <= 53 cols."""
        code, lines = self._run_wf([])
        self.assertEqual(code, 0)
        self._assert_bounded_53_cols(lines, "wf (no args)")
        joined = "\n".join(lines)
        self.assertIn("WhiskerFrame Cyberdeck (wf)", joined)
        self.assertIn("Subcommands:", joined)
        self.assertIn("man", joined)
        self.assertIn("wifi", joined)
        self.assertIn("demo", joined)
        self.assertIn("terminal", joined)
        self.assertIn("workspace", joined)

    def test_wf_help_subcommands_bounded(self) -> None:
        """Help for all subcommands strictly adheres to <= 53 cols."""
        subcommands = [
            [],
            ["help"],
            ["--help"],
            ["-h"],
            ["help", "man"],
            ["help", "wifi"],
            ["help", "power"],
            ["help", "profile"],
            ["help", "demo"],
            ["help", "terminal"],
            ["help", "workspace"],
        ]
        for sub in subcommands:
            code, lines = self._run_wf(sub)
            self.assertEqual(code, 0)
            self._assert_bounded_53_cols(lines, f"wf {' '.join(sub)}")

    def test_wf_unknown_subcommand(self) -> None:
        """Unknown subcommand returns exit code 1 and bounded error message."""
        code, lines = self._run_wf(["bogus_subcommand"])
        self.assertEqual(code, 1)
        self._assert_bounded_53_cols(lines, "unknown subcommand")
        self.assertTrue(any("Unknown subcommand" in line for line in lines))

    # --- 2. Offline Manual (wf man) Tests ------------------------------------

    def test_wf_man_index_bounded(self) -> None:
        """'wf man' index lists all required topics strictly <= 53 cols."""
        code, lines = self._run_wf(["man"])
        self.assertEqual(code, 0)
        self._assert_bounded_53_cols(lines, "wf man index")
        joined = "\n".join(lines)
        for req_topic in ["kb", "wifi", "demo", "terminal", "workspaces", "power", "profile"]:
            self.assertIn(req_topic, joined)

    def test_wf_man_topic_power_bounded(self) -> None:
        """'wf man power' documents three-tier power profiles (REQ-PWR-01)."""
        code, lines = self._run_wf(["man", "power"])
        self.assertEqual(code, 0)
        self._assert_bounded_53_cols(lines, "wf man power")
        joined = "\n".join(lines)
        self.assertIn("active", joined)
        self.assertIn("powersave", joined)
        self.assertIn("airplane", joined)

    def test_wf_man_topic_profile_bounded(self) -> None:
        """'wf man profile' documents sensory presets & overload mitigation (REQ-ENV-04, REQ-INP-08)."""
        code, lines = self._run_wf(["man", "profile"])
        self.assertEqual(code, 0)
        self._assert_bounded_53_cols(lines, "wf man profile")
        joined = "\n".join(lines)
        self.assertIn("classroom", joined)
        self.assertIn("office", joined)
        self.assertIn("commute", joined)
        self.assertIn("Sensory Overload", joined)

    def test_wf_man_topic_kb_bounded(self) -> None:
        """'wf man kb' documents CardKB, sticky Ctrl latch, and font geometry."""
        code, lines = self._run_wf(["man", "kb"])
        self.assertEqual(code, 0)
        self._assert_bounded_53_cols(lines, "wf man kb")
        joined = "\n".join(lines)
        self.assertIn("Fn+Tab", joined)
        self.assertIn("CardKB", joined)
        self.assertIn("YELLOW", joined)
        self.assertIn("Fn+Backspace", joined)
        self.assertIn("53x30", joined)

    def test_wf_man_topic_wifi_bounded(self) -> None:
        """'wf man wifi' documents 2.4 GHz constraint and NetworkManager commands."""
        code, lines = self._run_wf(["man", "wifi"])
        self.assertEqual(code, 0)
        self._assert_bounded_53_cols(lines, "wf man wifi")
        joined = "\n".join(lines)
        self.assertIn("2.4 GHz ONLY", joined)
        self.assertIn("wf wifi status", joined)
        self.assertIn("wf wifi scan", joined)
        self.assertIn("wf wifi join", joined)
        self.assertIn("wf wifi forget", joined)

    def test_wf_man_topic_demo_bounded(self) -> None:
        """'wf man demo' documents guest sandbox boundaries and PAM autostart."""
        code, lines = self._run_wf(["man", "demo"])
        self.assertEqual(code, 0)
        self._assert_bounded_53_cols(lines, "wf man demo")
        joined = "\n".join(lines)
        self.assertIn("guest / guest", joined)
        self.assertIn("tmpfs", joined)
        self.assertIn("nftables", joined)
        self.assertIn("Reaper", joined)
        self.assertIn("PAM login", joined)

    def test_wf_man_topic_terminal_bounded(self) -> None:
        """'wf man terminal' documents serial link, opcodes, and font geometries."""
        code, lines = self._run_wf(["man", "terminal"])
        self.assertEqual(code, 0)
        self._assert_bounded_53_cols(lines, "wf man terminal")
        joined = "\n".join(lines)
        self.assertIn("ILI9341", joined)
        self.assertIn("DRAW_CELLS", joined)
        self.assertIn("DRAW_IMAGE", joined)
        self.assertIn("53 cols x 30 rows", joined)

    def test_wf_man_topic_workspaces_bounded(self) -> None:
        """'wf man workspaces' documents multi-session management."""
        code, lines = self._run_wf(["man", "workspaces"])
        self.assertEqual(code, 0)
        self._assert_bounded_53_cols(lines, "wf man workspaces")
        joined = "\n".join(lines)
        self.assertIn("wf workspace list", joined)
        self.assertIn("wf workspace new", joined)
        self.assertIn("wf workspace switch", joined)
        self.assertIn("wf workspace close", joined)

    def test_wf_man_topic_aliases(self) -> None:
        """Manual topic aliases (e.g. workspace, keyboard) resolve correctly."""
        code1, lines1 = self._run_wf(["man", "workspace"])
        self.assertEqual(code1, 0)
        self._assert_bounded_53_cols(lines1, "wf man workspace")

        code2, lines2 = self._run_wf(["man", "keyboard"])
        self.assertEqual(code2, 0)
        self._assert_bounded_53_cols(lines2, "wf man keyboard")

    def test_wf_man_unknown_topic(self) -> None:
        """Unknown manual topic returns 1 and bounded error message."""
        code, lines = self._run_wf(["man", "unsupported_topic_xyz"])
        self.assertEqual(code, 1)
        self._assert_bounded_53_cols(lines, "wf man unknown")
        self.assertTrue(any("Unknown manual topic" in line for line in lines))

    # --- 3. Wi-Fi Delegation & Re-use Tests -----------------------------------

    @patch.object(wf, "_load_wifi_module")
    def test_wf_wifi_delegation_to_wifi_module(self, mock_load: MagicMock) -> None:
        """'wf wifi' reuses pi/bin/wifi by delegating arguments to its main()."""
        mock_wifi_mod = MagicMock()
        mock_wifi_mod.main.return_value = 0
        mock_load.return_value = mock_wifi_mod

        # 1. Status
        code, _ = self._run_wf(["wifi", "status"])
        self.assertEqual(code, 0)
        mock_wifi_mod.main.assert_called_with(["status"])

        # 2. Scan
        code, _ = self._run_wf(["wifi", "scan"])
        self.assertEqual(code, 0)
        mock_wifi_mod.main.assert_called_with(["scan"])

        # 3. Join
        code, _ = self._run_wf(["wifi", "join", "1", "-p", "secret"])
        self.assertEqual(code, 0)
        mock_wifi_mod.main.assert_called_with(["join", "1", "-p", "secret"])

        # 4. Forget
        code, _ = self._run_wf(["wifi", "forget", "OldNet"])
        self.assertEqual(code, 0)
        mock_wifi_mod.main.assert_called_with(["forget", "OldNet"])

    def test_real_wifi_module_can_be_loaded(self) -> None:
        """Verify that pi/bin/wifi is loaded and accessible by wf."""
        mod = wf._load_wifi_module()
        self.assertIsNotNone(mod, "pi/bin/wifi should be discoverable and loadable")
        self.assertTrue(hasattr(mod, "main"))
        self.assertTrue(hasattr(mod, "cmd_status"))

    # --- 3a. Power Management & Sensory Profile Delegation Tests -------------

    @patch.object(wf, "_load_power_module")
    def test_wf_power_delegation(self, mock_load: MagicMock) -> None:
        """'wf power' delegates arguments to power-profile CLI."""
        mock_pwr_mod = MagicMock()
        mock_pwr_mod.main.return_value = 0
        mock_load.return_value = mock_pwr_mod

        code, _ = self._run_wf(["power", "status"])
        self.assertEqual(code, 0)
        mock_pwr_mod.main.assert_called_with(["status"])

        code, _ = self._run_wf(["power", "set", "powersave"])
        self.assertEqual(code, 0)
        mock_pwr_mod.main.assert_called_with(["set", "powersave"])

    @patch.object(wf, "_load_profile_module")
    def test_wf_profile_delegation(self, mock_load: MagicMock) -> None:
        """'wf profile' delegates arguments to profile CLI."""
        mock_prof_mod = MagicMock()
        mock_prof_mod.main.return_value = 0
        mock_load.return_value = mock_prof_mod

        code, _ = self._run_wf(["profile", "status"])
        self.assertEqual(code, 0)
        mock_prof_mod.main.assert_called_with(["status"])

        code, _ = self._run_wf(["profile", "overload", "on"])
        self.assertEqual(code, 0)
        mock_prof_mod.main.assert_called_with(["overload", "on"])

    def test_real_power_and_profile_modules_loadable(self) -> None:
        """Verify dynamic loader imports real power-profile and profile scripts."""
        pwr_mod = wf._load_power_module()
        self.assertIsNotNone(pwr_mod)
        self.assertTrue(hasattr(pwr_mod, "main"))

        prof_mod = wf._load_profile_module()
        self.assertIsNotNone(prof_mod)
        self.assertTrue(hasattr(prof_mod, "main"))

    # --- 4. Demo and Demo Art Tests ------------------------------------------

    def test_wf_demo_builtin_banner_bounded(self) -> None:
        """'wf demo' outputs restricted sandbox banner strictly <= 53 cols."""
        code, lines = self._run_wf(["demo"])
        self.assertEqual(code, 0)
        self._assert_bounded_53_cols(lines, "wf demo")
        joined = "\n".join(lines)
        self.assertIn("Whiskerframe Cyberdeck", joined)
        self.assertIn("Restricted kernel sandbox", joined)
        self.assertIn("nftables", joined)
        self.assertIn("Telemetry", joined)

    def test_wf_demo_art_bounded(self) -> None:
        """'wf demo art' renders artwork gallery & ASCII art strictly <= 53 cols."""
        code, lines = self._run_wf(["demo", "art"])
        self.assertEqual(code, 0)
        self._assert_bounded_53_cols(lines, "wf demo art")
        joined = "\n".join(lines)
        self.assertIn("Art Gallery", joined)
        self.assertIn("DRAW_IMAGE", joined)
        self.assertIn("320x240", joined)

    # --- 5. Terminal and Workspace Management Tests --------------------------

    def test_workspace_lifecycle(self) -> None:
        """Test complete workspace lifecycle: list -> new -> switch -> close."""
        # 1. Initial list has default 'main' workspace
        code, lines = self._run_wf(["workspace", "list"])
        self.assertEqual(code, 0)
        self._assert_bounded_53_cols(lines, "workspace list (initial)")
        self.assertTrue(any("main" in line and "[*]" in line for line in lines))

        # 2. Create new workspace 'dev'
        code, lines = self._run_wf(["workspace", "new", "dev"])
        self.assertEqual(code, 0)
        self._assert_bounded_53_cols(lines, "workspace new dev")
        self.assertTrue(any("Created workspace 'dev'" in line for line in lines))

        # 3. Create duplicate fails
        code, lines = self._run_wf(["workspace", "new", "dev"])
        self.assertEqual(code, 1)
        self._assert_bounded_53_cols(lines, "workspace new duplicate")
        self.assertTrue(any("already exists" in line for line in lines))

        # 4. List shows both
        code, lines = self._run_wf(["workspace", "list"])
        self.assertEqual(code, 0)
        self._assert_bounded_53_cols(lines, "workspace list (after add)")
        self.assertTrue(any("dev" in line for line in lines))

        # 5. Switch to 'dev'
        code, lines = self._run_wf(["workspace", "switch", "dev"])
        self.assertEqual(code, 0)
        self._assert_bounded_53_cols(lines, "workspace switch dev")
        self.assertTrue(any("Switched to workspace 'dev'" in line for line in lines))

        # 6. Verify 'dev' is active
        code, lines = self._run_wf(["workspace", "list"])
        self.assertEqual(code, 0)
        self._assert_bounded_53_cols(lines, "workspace list (dev active)")
        self.assertTrue(any("dev" in line and "[*]" in line for line in lines))

        # 7. Close 'main'
        code, lines = self._run_wf(["workspace", "close", "main"])
        self.assertEqual(code, 0)
        self._assert_bounded_53_cols(lines, "workspace close main")
        self.assertTrue(any("Closed workspace 'main'" in line for line in lines))

        # 8. Attempting to close last remaining workspace fails
        code, lines = self._run_wf(["workspace", "close", "dev"])
        self.assertEqual(code, 1)
        self._assert_bounded_53_cols(lines, "workspace close last remaining")
        self.assertTrue(
            any("Cannot close last remaining workspace" in line for line in lines),
        )

    def test_terminal_alias_parity_with_workspace(self) -> None:
        """'wf terminal' is fully interchangeable with 'wf workspace'."""
        # Check that 'wf terminal' commands work identically
        code, lines = self._run_wf(["terminal", "list"])
        self.assertEqual(code, 0)
        self._assert_bounded_53_cols(lines, "terminal list")

        code, lines = self._run_wf(["terminal", "new", "monitoring"])
        self.assertEqual(code, 0)
        self._assert_bounded_53_cols(lines, "terminal new")

        code, lines = self._run_wf(["terminal", "switch", "monitoring"])
        self.assertEqual(code, 0)
        self._assert_bounded_53_cols(lines, "terminal switch")

        code, lines = self._run_wf(["terminal", "close", "monitoring"])
        self.assertEqual(code, 0)
        self._assert_bounded_53_cols(lines, "terminal close")

    # --- 6. Guest PAM Login Autostart Verification ---------------------------

    def test_guest_pam_login_autostart_configured(self) -> None:
        """Verify that PAM hook / profile configuration auto-starts demo upon guest login."""
        # 1. Check guest cleanup / PAM hook script template
        pam_hook_path = (
            REPO_ROOT
            / "ansible"
            / "roles"
            / "guest_demo"
            / "templates"
            / "guest-session-cleanup.sh.j2"
        )
        self.assertTrue(
            pam_hook_path.is_file(),
            "guest-session-cleanup.sh.j2 must exist",
        )
        pam_hook_content = pam_hook_path.read_text()
        self.assertIn("open_session", pam_hook_content)
        self.assertIn("wf demo", pam_hook_content)

        # 2. Check guest demo profile autostart in ansible role tasks
        tasks_path = (
            REPO_ROOT / "ansible" / "roles" / "guest_demo" / "tasks" / "main.yml"
        )
        self.assertTrue(tasks_path.is_file(), "guest_demo tasks/main.yml must exist")
        tasks_content = tasks_path.read_text()
        self.assertIn("guest-demo.sh", tasks_content)
        self.assertIn("wf demo", tasks_content)

        # 3. Check install.sh autostart configuration
        install_path = REPO_ROOT / "pi" / "terminal" / "install.sh"
        self.assertTrue(install_path.is_file(), "install.sh must exist")
        install_content = install_path.read_text()
        self.assertIn("guest-demo.sh", install_content)
        self.assertIn("wf demo", install_content)


if __name__ == "__main__":
    unittest.main()
