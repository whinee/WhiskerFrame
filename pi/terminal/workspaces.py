"""
Multi-PTY session/workspace manager (i3-style) for Whiskerframe Cyberdeck.

Manages bounded, independent shell workspaces for the Raspberry Pi Zero 2W.
Each workspace maintains:
- Dedicated pseudo-terminal (PTY master/slave pair)
- Independent shell process (bash login shell)
- Independent working directory (retained across switches)
- Dedicated character grid (screen buffer) and VT100 emulator

Provides:
- i3-style direct workspace switching via CardKB Fn chords (Fn+1..Fn+N)
- Next/previous workspace cycling
- Bounded workspace capacity (default 4, maximum 10) protecting the 416MB RAM
- Dead session detection and automated cleanup
- Clean screen restoration on workspace switch without shell resets
- UNIX domain socket IPC server and client for CLI interface
"""

from __future__ import annotations

import errno
import fcntl
import json
import os
import pty
import signal
import socket
import struct
import tempfile
import termios
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from whiskerframe.terminal import TerminalGeometry

from .debug import tracepoint
from .grid import Grid
from .vt import VTEmulator

__all__ = [
    "DEFAULT_MAX_WORKSPACES",
    "DEFAULT_SOCKET_PATH",
    "FALLBACK_SOCKET_PATH",
    "HARD_LIMIT_WORKSPACES",
    "WORKSPACE_DIRECT_CHORDS",
    "WORKSPACE_NEXT_CHORD",
    "WORKSPACE_PREV_CHORD",
    "Workspace",
    "WorkspaceClient",
    "WorkspaceLimitError",
    "WorkspaceManager",
]

DEFAULT_MAX_WORKSPACES: int = 4
"""Bounded default workspace count to preserve Pi Zero 2W memory ceiling (~416MB)."""

HARD_LIMIT_WORKSPACES: int = 10
"""Hard upper ceiling on concurrently managed workspaces."""

DEFAULT_SOCKET_PATH: str = "/run/whiskerframe/workspaces.sock"
"""Preferred UNIX domain socket for workspace IPC."""

FALLBACK_SOCKET_PATH: str = str(
    Path(tempfile.gettempdir()) / "whiskerframe_workspaces.sock",
)
"""Fallback socket path if /run is unwriteable."""

WORKSPACE_DIRECT_CHORDS: dict[int, int] = {
    0x81: 1,  # Fn+1
    0x82: 2,  # Fn+2
    0x83: 3,  # Fn+3
    0x84: 4,  # Fn+4
    0x85: 5,  # Fn+5
    0x86: 6,  # Fn+6
    0x87: 7,  # Fn+7
    0x88: 8,  # Fn+8
    0x89: 9,  # Fn+9
    0x8A: 10,  # Fn+0
}

WORKSPACE_NEXT_CHORD: int = 0xA6
"""Fn+n (0xA6) scancode for next workspace."""

WORKSPACE_PREV_CHORD: int = 0x96
"""Fn+p (0x96) scancode for previous workspace."""

_PTY_READ_BYTES: int = 4096


def _tiocswinsz(fd: int, geometry: TerminalGeometry) -> None:
    if fd < 0:
        return
    winsize = struct.pack(
        "HHHH",
        geometry.rows,
        geometry.cols,
        geometry.cols * geometry.cell_w,
        geometry.rows * geometry.cell_h,
    )
    try:
        fcntl.ioctl(fd, termios.TIOCSWINSZ, winsize)
    except OSError:
        pass


class WorkspaceLimitError(RuntimeError):
    """Raised when attempting to exceed bounded workspace capacity."""


@dataclass
class Workspace:
    """
    An independent terminal workspace.

    Retains dedicated PTY master, shell process, working directory,
    character grid buffer, and VT emulator state.
    """

    id: int
    name: str
    user: str
    pid: int
    master_fd: int
    grid: Grid
    emulator: VTEmulator
    created_at: float = field(default_factory=time.monotonic)
    last_active: float = field(default_factory=time.monotonic)
    _alive: bool = True
    _mock_cwd: str | None = None
    _mock_alive: bool | None = None

    @property
    def cwd(self) -> str:
        """Return the current working directory of this workspace shell."""
        if self._mock_cwd is not None:
            return self._mock_cwd
        if self.pid > 0:
            try:
                target = os.readlink(f"/proc/{self.pid}/cwd")
                if target:
                    return target
            except (OSError, FileNotFoundError):
                pass
        return f"/home/{self.user}" if self.user != "root" else "/root"

    def _poll_proc(self) -> bool:
        try:
            res_pid, _ = os.waitpid(self.pid, os.WNOHANG)
            if res_pid == self.pid:
                return False
            os.kill(self.pid, 0)
            return True
        except (OSError, ProcessLookupError):
            return False

    def is_alive(self) -> bool:
        """Check if the shell child process is still running."""
        if not self._alive:
            return False
        if self._mock_alive is not None:
            return self._mock_alive
        if self.pid > 0 and not self._poll_proc():
            self._alive = False
        return self._alive

    def mark_dead(self) -> None:
        """Mark workspace process as terminated."""
        self._alive = False

    def _close_fd(self) -> None:
        if self.master_fd >= 0:
            try:
                os.close(self.master_fd)
            except OSError:
                pass
            self.master_fd = -1

    def _kill_pid(self) -> None:
        if self.pid > 0:
            try:
                os.kill(self.pid, signal.SIGHUP)
            except OSError:
                pass
            try:
                os.waitpid(self.pid, os.WNOHANG)
            except OSError:
                pass

    def close(self) -> None:
        """Terminate workspace shell and release PTY master."""
        self._alive = False
        self._close_fd()
        self._kill_pid()


class WorkspaceManager:
    """Manages bounded multi-PTY workspaces for the CYD terminal."""

    def __init__(
        self,
        bridge: Any,
        user: str,
        max_workspaces: int = DEFAULT_MAX_WORKSPACES,
        spawn_fn: Callable[[str], tuple[int, int]] | None = None,
        socket_path: str | None = None,
    ) -> None:
        self.bridge = bridge
        self.user = user
        self.max_workspaces = min(max(1, max_workspaces), HARD_LIMIT_WORKSPACES)
        self.spawn_fn = spawn_fn or getattr(bridge, "_spawn_shell", None) or self._default_spawn
        self.socket_path = socket_path
        self.workspaces: dict[int, Workspace] = {}
        self.active_id: int = 1
        self._ipc_server: socket.socket | None = None
        self._ipc_clients: list[socket.socket] = []
        self.actual_socket_path: str | None = None

    @staticmethod
    def _default_spawn(user: str) -> tuple[int, int]:
        pid, master_fd = pty.fork()
        if pid == 0:  # pragma: no cover
            os.execvp("bash", ["bash", "-l"])  # noqa: S606, S607
            os._exit(127)
        return pid, master_fd

    @property
    def active_workspace(self) -> Workspace | None:
        """Return the currently active workspace, or None."""
        return self.workspaces.get(self.active_id)

    def _alloc_target_id(self, ws_id: int | None) -> int:
        if ws_id is not None:
            return ws_id
        cand = 1
        while cand in self.workspaces:
            cand += 1
        return cand

    def _init_ws_env(self, master_fd: int) -> tuple[Grid, VTEmulator]:
        geometry = getattr(self.bridge, "_geometry", None)
        theme = getattr(self.bridge, "_theme", None)
        cols = geometry.cols if geometry else 53
        rows = geometry.rows if geometry else 30
        fg = theme.fg if theme else 0xFFFF
        bg = theme.bg if theme else 0x0000

        if geometry and master_fd >= 0:
            _tiocswinsz(master_fd, geometry)

        grid = Grid(cols, rows, fg, bg)
        emulator = VTEmulator(grid, theme)
        return grid, emulator

    def create_workspace(
        self,
        ws_id: int | None = None,
        name: str | None = None,
        user: str | None = None,
        initial_fd: int | None = None,
        initial_pid: int | None = None,
    ) -> Workspace:
        """Create a new independent workspace."""
        if len(self.workspaces) >= self.max_workspaces:
            raise WorkspaceLimitError(
                f"Maximum workspace count ({self.max_workspaces}) reached",
            )

        target_id = self._alloc_target_id(ws_id)
        if target_id in self.workspaces:
            return self.workspaces[target_id]

        target_user = user or self.user
        if initial_fd is not None and initial_pid is not None:
            pid, master_fd = initial_pid, initial_fd
        else:
            pid, master_fd = self.spawn_fn(target_user)

        grid, emulator = self._init_ws_env(master_fd)
        now = time.monotonic()
        ws = Workspace(
            id=target_id,
            name=name or str(target_id),
            user=target_user,
            pid=pid,
            master_fd=master_fd,
            grid=grid,
            emulator=emulator,
            created_at=now,
            last_active=now,
        )
        self.workspaces[target_id] = ws
        if len(self.workspaces) == 1:
            self.active_id = target_id

        tracepoint("workspace.created", id=target_id, pid=pid, user=target_user)
        return ws

    def switch_workspace(self, target_id: int) -> bool:
        """Switch active workspace, restoring screen cleanly without resetting shells."""
        if target_id == self.active_id and target_id in self.workspaces:
            return True

        if target_id not in self.workspaces:
            if target_id > self.max_workspaces:
                return False
            try:
                self.create_workspace(ws_id=target_id)
            except WorkspaceLimitError:
                return False

        self.active_id = target_id
        ws = self.workspaces[target_id]
        ws.last_active = time.monotonic()
        tracepoint("workspace.switch", id=target_id)
        self.restore_screen()
        return True

    def next_workspace(self) -> int:
        """Switch to next active workspace (wrapping around)."""
        if not self.workspaces:
            return self.active_id
        sorted_ids = sorted(self.workspaces.keys())
        if self.active_id not in sorted_ids:
            next_id = sorted_ids[0]
        else:
            idx = (sorted_ids.index(self.active_id) + 1) % len(sorted_ids)
            next_id = sorted_ids[idx]
        self.switch_workspace(next_id)
        return next_id

    def prev_workspace(self) -> int:
        """Switch to previous active workspace (wrapping around)."""
        if not self.workspaces:
            return self.active_id
        sorted_ids = sorted(self.workspaces.keys())
        if self.active_id not in sorted_ids:
            prev_id = sorted_ids[-1]
        else:
            idx = (sorted_ids.index(self.active_id) - 1) % len(sorted_ids)
            prev_id = sorted_ids[idx]
        self.switch_workspace(prev_id)
        return prev_id

    def close_workspace(self, target_id: int | None = None) -> bool:
        """Close specified workspace (or active if None), reaping its process."""
        ws_id = target_id if target_id is not None else self.active_id
        if ws_id not in self.workspaces:
            return False

        ws = self.workspaces.pop(ws_id)
        ws.close()
        tracepoint("workspace.closed", id=ws_id)

        if self.active_id == ws_id:
            if self.workspaces:
                sorted_ids = sorted(self.workspaces.keys())
                self.active_id = min(sorted_ids, key=lambda x: abs(x - ws_id))
                self.restore_screen()
            else:
                self.active_id = 0
        return True

    def cleanup_dead_sessions(self) -> list[int]:
        """Audit workspaces, closing and reaping any dead shell processes."""
        dead = [ws_id for ws_id, ws in self.workspaces.items() if not ws.is_alive()]
        if not dead:
            return []

        active_died = self.active_id in dead
        for ws_id in dead:
            ws = self.workspaces.pop(ws_id)
            ws.close()
            tracepoint("workspace.reaped", id=ws_id)

        if active_died:
            if self.workspaces:
                sorted_ids = sorted(self.workspaces.keys())
                self.active_id = sorted_ids[0]
                self.restore_screen()
            else:
                self.active_id = 0
        return dead

    def has_alive_workspaces(self) -> bool:
        """Return True if at least one workspace is currently alive."""
        return bool(self.workspaces)

    def restore_screen(self) -> None:
        """Force clean display restoration of active workspace buffer."""
        ws = self.active_workspace
        if ws is None:
            return
        if hasattr(self.bridge, "_prev"):
            self.bridge._prev = None
        self.paint_active()

    def paint_active(self, ctrl_armed: bool = False) -> None:
        """Paint active workspace grid with cursor highlight to display."""
        ws = self.active_workspace
        if ws is None or not hasattr(self.bridge, "_paint"):
            return
        theme = getattr(self.bridge, "_theme", None)
        if theme:
            cursor_bg = theme.ansi[11] if ctrl_armed else theme.cursor
            display_grid = ws.grid.render_with_cursor(
                cursor_fg=theme.bg,
                cursor_bg=cursor_bg,
            )
        else:
            display_grid = ws.grid
        self.bridge._paint(display_grid)

    def _copy_cells(self, old_grid: Grid, new_grid: Grid) -> None:
        min_r = min(old_grid.rows, new_grid.rows)
        min_c = min(old_grid.cols, new_grid.cols)
        for r in range(min_r):
            for c in range(min_c):
                cell = old_grid.cell_at(r, c)
                if cell.char != " " or cell.bg != old_grid.default_bg:
                    new_grid.set_cursor(r, c)
                    new_grid.put_char(cell.char, cell.fg, cell.bg)

    def rebuild_geometry(self, geometry: TerminalGeometry) -> None:
        """Update window geometry across all workspaces and redraw active."""
        theme = getattr(self.bridge, "_theme", None)
        fg = theme.fg if theme else 0xFFFF
        bg = theme.bg if theme else 0x0000

        for ws in self.workspaces.values():
            if ws.master_fd >= 0:
                _tiocswinsz(ws.master_fd, geometry)
            new_grid = Grid(geometry.cols, geometry.rows, fg, bg)
            self._copy_cells(ws.grid, new_grid)
            new_grid.set_cursor(
                min(ws.grid.cursor_row, geometry.rows - 1),
                min(ws.grid.cursor_col, geometry.cols - 1),
            )
            ws.grid = new_grid
            ws.emulator = VTEmulator(new_grid, theme)
        self.restore_screen()

    def list_workspaces(self) -> list[dict[str, Any]]:
        """Return serializable summary of all workspaces."""
        return [
            {
                "id": ws.id,
                "name": ws.name,
                "user": ws.user,
                "pid": ws.pid,
                "active": ws.id == self.active_id,
                "cwd": ws.cwd,
                "alive": ws.is_alive(),
            }
            for ws in sorted(self.workspaces.values(), key=lambda w: w.id)
        ]

    def close_all(self) -> None:
        """Close all managed workspaces and IPC server."""
        for ws in list(self.workspaces.values()):
            ws.close()
        self.workspaces.clear()
        self.active_id = 0
        self.stop_ipc_server()

    # -- IPC Server -----------------------------------------------------------

    def start_ipc_server(self) -> socket.socket | None:
        """Start UNIX domain socket server for CLI control."""
        paths = [self.socket_path, DEFAULT_SOCKET_PATH, FALLBACK_SOCKET_PATH]
        for path_str in paths:
            if not path_str:
                continue
            sock_path = Path(path_str)
            try:
                sock_path.parent.mkdir(parents=True, exist_ok=True)
                if sock_path.exists():
                    sock_path.unlink()
                srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                srv.bind(str(sock_path))
                srv.listen(5)
                srv.setblocking(False)
                self._ipc_server = srv
                self.actual_socket_path = str(sock_path)
                return srv
            except (OSError, PermissionError):
                continue
        return None

    def _close_sockets(self) -> None:
        for client in self._ipc_clients:
            try:
                client.close()
            except OSError:
                pass
        self._ipc_clients.clear()

        if self._ipc_server is not None:
            try:
                self._ipc_server.close()
            except OSError:
                pass
            self._ipc_server = None

    def stop_ipc_server(self) -> None:
        """Close IPC server and clean up socket file."""
        self._close_sockets()
        if self.actual_socket_path and os.path.exists(self.actual_socket_path):
            try:
                os.unlink(self.actual_socket_path)
            except OSError:
                pass
            self.actual_socket_path = None

    def get_read_fds(self) -> list[int]:
        """Return list of readable file descriptors (PTYs + IPC sockets)."""
        fds = [ws.master_fd for ws in self.workspaces.values() if ws.master_fd >= 0]
        if self._ipc_server is not None:
            fds.append(self._ipc_server.fileno())
        for client in self._ipc_clients:
            fds.append(client.fileno())
        return fds

    def is_ipc_fd(self, fd: int) -> bool:
        """Report whether an fd belongs to IPC server or client."""
        if self._ipc_server is not None and fd == self._ipc_server.fileno():
            return True
        return any(c.fileno() == fd for c in self._ipc_clients)

    def handle_ipc_fd(self, fd: int) -> None:
        """Process activity on an IPC server or client descriptor."""
        if self._ipc_server is not None and fd == self._ipc_server.fileno():
            self._accept_client()
            return
        client_match = next((c for c in self._ipc_clients if c.fileno() == fd), None)
        if client_match is not None:
            self._read_client(client_match)

    def _accept_client(self) -> None:
        if self._ipc_server is None:
            return
        try:
            client, _ = self._ipc_server.accept()
            client.setblocking(False)
            self._ipc_clients.append(client)
        except OSError:
            pass

    def _handle_client_line(self, client: socket.socket, line: str) -> None:
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            resp = {"ok": False, "error": "Invalid JSON request"}
            client.sendall(json.dumps(resp).encode("utf-8") + b"\n")
            return
        resp = self.dispatch_ipc_command(req)
        client.sendall(json.dumps(resp).encode("utf-8") + b"\n")

    def _read_client(self, client: socket.socket) -> None:
        try:
            data = client.recv(4096)
            if not data:
                self._close_client(client)
                return
            for line in data.decode("utf-8", errors="ignore").splitlines():
                if line.strip():
                    self._handle_client_line(client, line)
        except OSError:
            self._close_client(client)

    def _close_client(self, client: socket.socket) -> None:
        try:
            client.close()
        except OSError:
            pass
        if client in self._ipc_clients:
            self._ipc_clients.remove(client)

    def _cmd_list(self, _req: dict[str, Any]) -> dict[str, Any]:
        return {
            "ok": True,
            "workspaces": self.list_workspaces(),
            "active": self.active_id,
            "max": self.max_workspaces,
        }

    def _cmd_switch(self, req: dict[str, Any]) -> dict[str, Any]:
        target_id = req.get("id")
        if target_id is None:
            return {"ok": False, "error": "Missing workspace id"}
        try:
            tid = int(target_id)
        except (ValueError, TypeError):
            return {"ok": False, "error": f"Invalid id: {target_id}"}
        ok = self.switch_workspace(tid)
        return {"ok": ok, "active": self.active_id}

    def _cmd_new(self, req: dict[str, Any]) -> dict[str, Any]:
        name = req.get("name")
        target_id = req.get("id")
        tid = int(target_id) if target_id is not None else None
        try:
            ws = self.create_workspace(ws_id=tid, name=name)
            return {"ok": True, "id": ws.id, "active": self.active_id}
        except WorkspaceLimitError as err:
            return {"ok": False, "error": str(err)}

    def _cmd_close(self, req: dict[str, Any]) -> dict[str, Any]:
        target_id = req.get("id")
        tid = int(target_id) if target_id is not None else self.active_id
        return {"ok": self.close_workspace(tid), "active": self.active_id}

    def _cmd_status(self, _req: dict[str, Any]) -> dict[str, Any]:
        return {
            "ok": True,
            "active": self.active_id,
            "count": len(self.workspaces),
            "max": self.max_workspaces,
            "workspaces": self.list_workspaces(),
        }

    def dispatch_ipc_command(self, req: dict[str, Any]) -> dict[str, Any]:
        """Dispatch a single parsed IPC command dictionary."""
        cmd = req.get("cmd", "").lower()
        handlers: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
            "list": self._cmd_list,
            "ls": self._cmd_list,
            "switch": self._cmd_switch,
            "goto": self._cmd_switch,
            "next": lambda _r: {"ok": True, "active": self.next_workspace()},
            "prev": lambda _r: {"ok": True, "active": self.prev_workspace()},
            "new": self._cmd_new,
            "close": self._cmd_close,
            "kill": self._cmd_close,
            "status": self._cmd_status,
        }
        handler = handlers.get(cmd)
        if handler is None:
            return {"ok": False, "error": f"Unknown command: {cmd}"}
        return handler(req)

    def _read_fd_bytes(self, ws: Workspace) -> bytes | None:
        try:
            data = os.read(ws.master_fd, _PTY_READ_BYTES)
            if not data:
                ws.mark_dead()
                return None
            return data
        except OSError as err:
            if err.errno not in (errno.EAGAIN, errno.EINTR):
                ws.mark_dead()
            return None

    def read_pty_fd(self, fd: int, ctrl_armed: bool = False) -> bool:
        """Read pending output from a workspace PTY master."""
        ws = next((w for w in self.workspaces.values() if w.master_fd == fd), None)
        if ws is None:
            return False
        data = self._read_fd_bytes(ws)
        if data is None:
            return False

        ws.emulator.feed(data)
        if ws.id == self.active_id:
            self.paint_active(ctrl_armed=ctrl_armed)
        return True


class WorkspaceClient:
    """Client for controlling Whiskerframe workspaces over UNIX domain socket."""

    def __init__(self, socket_path: str | None = None) -> None:
        self.socket_path = socket_path

    def _connect(self) -> socket.socket:
        paths = [self.socket_path, DEFAULT_SOCKET_PATH, FALLBACK_SOCKET_PATH]
        last_err: Exception | None = None
        for p in paths:
            if not p or not os.path.exists(p):
                continue
            try:
                s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                s.connect(p)
                return s
            except OSError as err:
                last_err = err
                continue
        msg = f"Cannot connect to Whiskerframe workspace socket: {last_err or 'socket not found'}"
        raise ConnectionError(msg)

    def send_cmd(self, req: dict[str, Any]) -> dict[str, Any]:
        """Send command dict and return parsed JSON reply."""
        with self._connect() as s:
            payload = json.dumps(req).encode("utf-8") + b"\n"
            s.sendall(payload)
            s.settimeout(2.0)
            data = b""
            while b"\n" not in data:
                chunk = s.recv(4096)
                if not chunk:
                    break
                data += chunk
            if not data:
                return {"ok": False, "error": "No response received"}
            return json.loads(data.decode("utf-8").strip())

    def list(self) -> dict[str, Any]:
        """List active workspaces."""
        return self.send_cmd({"cmd": "list"})

    def switch(self, ws_id: int) -> dict[str, Any]:
        """Switch to workspace ws_id."""
        return self.send_cmd({"cmd": "switch", "id": ws_id})

    def next(self) -> dict[str, Any]:
        """Switch to next workspace."""
        return self.send_cmd({"cmd": "next"})

    def prev(self) -> dict[str, Any]:
        """Switch to previous workspace."""
        return self.send_cmd({"cmd": "prev"})

    def new(self, name: str | None = None) -> dict[str, Any]:
        """Create new workspace."""
        return self.send_cmd({"cmd": "new", "name": name})

    def close(self, ws_id: int | None = None) -> dict[str, Any]:
        """Close workspace."""
        return self.send_cmd({"cmd": "close", "id": ws_id})

    def status(self) -> dict[str, Any]:
        """Get workspace status."""
        return self.send_cmd({"cmd": "status"})
