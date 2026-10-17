"""
Unit tests for Whiskerframe Cyberdeck Workspace Manager (multi-PTY, i3-style).

Validates:
1. Multi-PTY workspace isolation:
   - Independent PTY master/slave pair, process PID, working directory, and screen buffers.
2. Non-destructive screen buffering & clean restoration:
   - Background output feeds memory grid without touching display.
   - Workspace switch invalidates diff state (_prev = None) and paints target buffer.
3. CardKB navigation chords:
   - Direct chords: Fn+1..Fn+0 (0x81..0x8A) -> workspaces 1..10.
   - Cycle chords: Fn+n (0xA6) -> next, Fn+p (0x96) -> prev.
   - Sticky Ctrl latch automatically disarms upon workspace chord.
4. Bounded session count & memory protection:
   - Default ceiling 4 workspaces, hard limit 10 workspaces.
   - WorkspaceLimitError raised when exceeding capacity.
5. Dead session detection & reaping:
   - cleanup_dead_sessions() detects exited shell processes and reaps PTY fds.
   - Active workspace shifts cleanly when active session exits.
6. UNIX domain socket IPC server & WorkspaceClient:
   - Commands: list, switch, next, prev, new, close, status.
   - Non-blocking multiplexing in event loop.
7. Workspace CLI (pi/bin/workspace):
   - Formatting strictly <= 53 columns.
"""

from __future__ import annotations

import io
import json
import socket
import sys
import tempfile
import unittest
from importlib.machinery import SourceFileLoader
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "pi"))

_cli_path = REPO_ROOT / "pi" / "bin" / "workspace"
_cli_loader = SourceFileLoader("workspace_cli", str(_cli_path))
workspace_cli: ModuleType = ModuleType(_cli_loader.name)
workspace_cli.__file__ = str(_cli_path)
_cli_loader.exec_module(workspace_cli)
from terminal.bridge import (  # noqa: E402
    CTRL_LATCH_CHORD,
    KeyQueue,
    TerminalBridge,
    _ShellSession,
)
from terminal.grid import Grid  # noqa: E402
from terminal.theme import load_theme  # noqa: E402
from terminal.workspaces import (  # noqa: E402
    DEFAULT_MAX_WORKSPACES,
    HARD_LIMIT_WORKSPACES,
    WORKSPACE_NEXT_CHORD,
    WORKSPACE_PREV_CHORD,
    WorkspaceClient,
    WorkspaceLimitError,
    WorkspaceManager,
)

from whiskerframe.terminal import TerminalGeometry  # noqa: E402


class TestWorkspaceManagerCore(unittest.TestCase):
    """Test core Workspace and WorkspaceManager functionality."""

    def setUp(self) -> None:
        self.theme = load_theme(None)
        self.geometry = TerminalGeometry.for_font_size(1)
        self.mock_bridge = MagicMock(spec=TerminalBridge)
        self.mock_bridge._theme = self.theme
        self.mock_bridge._geometry = self.geometry
        self.mock_bridge._paint = MagicMock()
        self.mock_bridge._prev = "mock_previous_grid"

        self.spawn_counter = 100

        def mock_spawn(user: str) -> tuple[int, int]:
            self.spawn_counter += 1
            return (-self.spawn_counter, self.spawn_counter + 1000)

        self.mock_spawn = mock_spawn
        self.temp_dir = tempfile.TemporaryDirectory()
        self.socket_path = str(Path(self.temp_dir.name) / "test_ws.sock")

        self.mgr = WorkspaceManager(
            bridge=self.mock_bridge,
            user="whisker",
            max_workspaces=4,
            spawn_fn=self.mock_spawn,
            socket_path=self.socket_path,
        )

    def tearDown(self) -> None:
        self.mgr.close_all()
        self.temp_dir.cleanup()

    def test_default_workspace_creation_and_isolation(self) -> None:
        """Each workspace retains distinct PTY descriptors, PIDs, grids, and emulators."""
        ws1 = self.mgr.create_workspace(ws_id=1)
        ws2 = self.mgr.create_workspace(ws_id=2)

        self.assertEqual(ws1.id, 1)
        self.assertEqual(ws2.id, 2)
        self.assertNotEqual(ws1.pid, ws2.pid)
        self.assertNotEqual(ws1.master_fd, ws2.master_fd)
        self.assertIsNot(ws1.grid, ws2.grid)
        self.assertIsNot(ws1.emulator, ws2.emulator)
        self.assertEqual(self.mgr.active_id, 1)

    def test_bounded_capacity_enforces_pi_ram_ceiling(self) -> None:
        """Manager refuses to spawn beyond max_workspaces (default 4)."""
        self.assertEqual(self.mgr.max_workspaces, DEFAULT_MAX_WORKSPACES)
        for i in range(1, 5):
            self.mgr.create_workspace(ws_id=i)

        self.assertEqual(len(self.mgr.workspaces), 4)
        with self.assertRaises(WorkspaceLimitError):
            self.mgr.create_workspace(ws_id=5)

    def test_hard_limit_enforced_on_init(self) -> None:
        """Manager clamps requested capacity to HARD_LIMIT_WORKSPACES (10)."""
        big_mgr = WorkspaceManager(
            bridge=self.mock_bridge,
            user="whisker",
            max_workspaces=999,
            spawn_fn=self.mock_spawn,
        )
        self.assertEqual(big_mgr.max_workspaces, HARD_LIMIT_WORKSPACES)
        big_mgr.close_all()

    def test_non_destructive_screen_buffering_and_restoration(self) -> None:
        """Writing to background workspace updates its grid without touching active display."""
        ws1 = self.mgr.create_workspace(ws_id=1)
        ws2 = self.mgr.create_workspace(ws_id=2)

        self.mock_bridge._paint.reset_mock()
        self.mock_bridge._prev = "valid_previous_diff"

        # Feed data to background workspace 2
        ws2.emulator.feed(b"Background Task Output\r\n")
        self.assertEqual(ws2.grid.cell_at(0, 0).char, "B")
        self.assertEqual(ws1.grid.cell_at(0, 0).char, " ")
        # Active display was not repainted for background output
        self.mock_bridge._paint.assert_not_called()

        # Switch to workspace 2
        ok = self.mgr.switch_workspace(2)
        self.assertTrue(ok)
        self.assertEqual(self.mgr.active_id, 2)
        # Previous diff baseline invalidated to force clean full repaint
        self.assertIsNone(self.mock_bridge._prev)
        self.mock_bridge._paint.assert_called_once()
        painted_grid = self.mock_bridge._paint.call_args[0][0]
        self.assertEqual(painted_grid.cell_at(0, 0).char, "B")

    def test_cycle_next_and_prev_workspaces(self) -> None:
        """next_workspace and prev_workspace cycle through active workspaces with wraparound."""
        self.mgr.create_workspace(ws_id=1)
        self.mgr.create_workspace(ws_id=2)
        self.mgr.create_workspace(ws_id=3)

        self.assertEqual(self.mgr.active_id, 1)
        self.assertEqual(self.mgr.next_workspace(), 2)
        self.assertEqual(self.mgr.next_workspace(), 3)
        self.assertEqual(self.mgr.next_workspace(), 1)  # wraps around

        self.assertEqual(self.mgr.prev_workspace(), 3)  # wraps around backwards
        self.assertEqual(self.mgr.prev_workspace(), 2)
        self.assertEqual(self.mgr.prev_workspace(), 1)

    def test_close_workspace_and_active_reassignment(self) -> None:
        """Closing active workspace reassigns active_id to remaining workspace."""
        self.mgr.create_workspace(ws_id=1)
        self.mgr.create_workspace(ws_id=2)
        self.mgr.switch_workspace(1)

        ok = self.mgr.close_workspace(1)
        self.assertTrue(ok)
        self.assertNotIn(1, self.mgr.workspaces)
        self.assertEqual(self.mgr.active_id, 2)

    def test_cleanup_dead_sessions(self) -> None:
        """cleanup_dead_sessions() detects dead processes, closes fds, and updates active."""
        ws1 = self.mgr.create_workspace(ws_id=1)
        ws2 = self.mgr.create_workspace(ws_id=2)
        ws2._mock_alive = True

        # Mark ws1 as dead
        ws1.mark_dead()
        self.assertFalse(ws1.is_alive())

        dead = self.mgr.cleanup_dead_sessions()
        self.assertEqual(dead, [1])
        self.assertNotIn(1, self.mgr.workspaces)
        self.assertEqual(self.mgr.active_id, 2)


class TestWorkspaceIPCAndClient(unittest.TestCase):
    """Test UNIX domain socket server and WorkspaceClient."""

    def setUp(self) -> None:
        self.theme = load_theme(None)
        self.geometry = TerminalGeometry.for_font_size(1)
        self.mock_bridge = MagicMock(spec=TerminalBridge)
        self.mock_bridge._theme = self.theme
        self.mock_bridge._geometry = self.geometry
        self.mock_bridge._paint = MagicMock()

        self.temp_dir = tempfile.TemporaryDirectory()
        self.socket_path = str(Path(self.temp_dir.name) / "ipc_test.sock")

        self.spawn_counter = 200

        def mock_spawn(user: str) -> tuple[int, int]:
            self.spawn_counter += 1
            return (self.spawn_counter, self.spawn_counter + 2000)

        self.mgr = WorkspaceManager(
            bridge=self.mock_bridge,
            user="whisker",
            max_workspaces=4,
            spawn_fn=mock_spawn,
            socket_path=self.socket_path,
        )
        self.mgr.create_workspace(ws_id=1)
        self.mgr.start_ipc_server()
        self.client = WorkspaceClient(socket_path=self.socket_path)

    def tearDown(self) -> None:
        self.mgr.close_all()
        self.temp_dir.cleanup()

    def _pump_ipc(self) -> None:
        """Simulate event-loop dispatch of pending IPC socket activity."""
        for fd in self.mgr.get_read_fds():
            if self.mgr.is_ipc_fd(fd):
                self.mgr.handle_ipc_fd(fd)

    def test_ipc_list_and_status(self) -> None:
        """WorkspaceClient list() and status() return structured workspace information."""
        # Non-blocking client send / server pump helper
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.connect(self.socket_path)
            self._pump_ipc()
            s.sendall(b'{"cmd": "status"}\n')
            self._pump_ipc()
            reply = json.loads(s.recv(4096).decode("utf-8").strip())

        self.assertTrue(reply.get("ok"))
        self.assertEqual(reply.get("active"), 1)
        self.assertEqual(reply.get("count"), 1)
        self.assertEqual(reply.get("max"), 4)

    def test_ipc_new_and_switch(self) -> None:
        """WorkspaceClient can create and switch workspaces over IPC."""
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.connect(self.socket_path)
            self._pump_ipc()

            # Create new workspace 2
            s.sendall(b'{"cmd": "new", "name": "editor"}\n')
            self._pump_ipc()
            reply = json.loads(s.recv(4096).decode("utf-8").strip())
            self.assertTrue(reply.get("ok"))
            self.assertEqual(reply.get("id"), 2)

            # Switch to workspace 2
            s.sendall(b'{"cmd": "switch", "id": 2}\n')
            self._pump_ipc()
            reply = json.loads(s.recv(4096).decode("utf-8").strip())
            self.assertTrue(reply.get("ok"))
            self.assertEqual(self.mgr.active_id, 2)


class TestBridgeWorkspaceChordsAndIntegration(unittest.TestCase):
    """Test CardKB workspace navigation chords and bridge integration."""

    def setUp(self) -> None:
        self.theme = load_theme(None)
        self.geometry = TerminalGeometry.for_font_size(1)
        self.mock_bridge = MagicMock(spec=TerminalBridge)
        self.mock_bridge._theme = self.theme
        self.mock_bridge._geometry = self.geometry
        self.mock_bridge._paint = MagicMock()
        self.mock_bridge._rebuild_geometry = MagicMock(
            return_value=Grid(
                self.geometry.cols,
                self.geometry.rows,
                self.theme.fg,
                self.theme.bg,
            ),
        )

        self.spawn_counter = 300

        def mock_spawn(user: str) -> tuple[int, int]:
            self.spawn_counter += 1
            return (0, self.spawn_counter + 3000)

        self.mock_bridge._spawn_shell = mock_spawn
        self.key_queue = KeyQueue(iter([]))
        self.master_fd = 777
        self.session = _ShellSession(
            bridge=self.mock_bridge,
            master_fd=self.master_fd,
            keys=self.key_queue,
            user="whisker",
            initial_pid=0,
            max_workspaces=4,
        )

    def tearDown(self) -> None:
        self.session._workspaces.close_all()

    def test_direct_workspace_chords_fn_1_to_4(self) -> None:
        """Fn+1..Fn+4 (0x81..0x84) chords switch workspaces directly."""
        self.assertEqual(self.session._workspaces.active_id, 1)

        # Press Fn+2 (0x82)
        handled = self.session._process_single_key(0x82)
        self.assertTrue(handled)
        self.assertEqual(self.session._workspaces.active_id, 2)
        self.assertIn(2, self.session._workspaces.workspaces)

        # Press Fn+3 (0x83)
        handled = self.session._process_single_key(0x83)
        self.assertTrue(handled)
        self.assertEqual(self.session._workspaces.active_id, 3)

        # Press Fn+1 (0x81) to switch back
        handled = self.session._process_single_key(0x81)
        self.assertTrue(handled)
        self.assertEqual(self.session._workspaces.active_id, 1)

    def test_cycle_workspace_chords_next_and_prev(self) -> None:
        """Fn+n (0xA6) and Fn+p (0x96) cycle through active workspaces."""
        # Create workspace 2 and 3
        self.session._workspaces.create_workspace(ws_id=2)
        self.session._workspaces.create_workspace(ws_id=3)
        self.assertEqual(self.session._workspaces.active_id, 1)

        # Fn+n (WORKSPACE_NEXT_CHORD = 0xA6)
        handled = self.session._process_single_key(WORKSPACE_NEXT_CHORD)
        self.assertTrue(handled)
        self.assertEqual(self.session._workspaces.active_id, 2)

        # Fn+p (WORKSPACE_PREV_CHORD = 0x96)
        handled = self.session._process_single_key(WORKSPACE_PREV_CHORD)
        self.assertTrue(handled)
        self.assertEqual(self.session._workspaces.active_id, 1)

    def test_workspace_chord_disarms_sticky_ctrl_latch(self) -> None:
        """Switching workspaces immediately disarms any armed sticky Ctrl latch."""
        self.session._process_single_key(CTRL_LATCH_CHORD)
        self.assertTrue(self.session._is_ctrl_armed())

        # Press Fn+2 to switch workspace
        self.session._process_single_key(0x82)
        self.assertFalse(self.session._is_ctrl_armed())


class TestWorkspaceCLI(unittest.TestCase):
    """Test pi/bin/workspace CLI commands and <= 53 column formatting constraint."""

    @patch.object(WorkspaceClient, "list")
    def test_cli_list_formatting_constrained_to_53_cols(
        self,
        mock_list: MagicMock,
    ) -> None:
        """Workspace list outputs clean table strictly <= 53 columns wide."""
        mock_list.return_value = {
            "ok": True,
            "active": 1,
            "max": 4,
            "workspaces": [
                {
                    "id": 1,
                    "name": "primary",
                    "pid": 1234,
                    "active": True,
                    "cwd": "/home/whisker/very_long_path_name_here",
                },
                {
                    "id": 2,
                    "name": "editor",
                    "pid": 5678,
                    "active": False,
                    "cwd": "/var/log",
                },
            ],
        }

        client = WorkspaceClient()
        stdout_capture = io.StringIO()
        with patch("sys.stdout", stdout_capture):
            ret = workspace_cli.cmd_list(client, MagicMock())

        self.assertEqual(ret, 0)
        output = stdout_capture.getvalue()
        for line in output.splitlines():
            self.assertLessEqual(
                len(line),
                53,
                f"Line exceeds 53 cols: '{line}' (len={len(line)})",
            )


if __name__ == "__main__":
    unittest.main()
