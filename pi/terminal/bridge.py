r"""
The CYD terminal bridge daemon: splash -> login -> shell -> login, forever.

Glue the CardKB, a real ``bash -l`` login shell on a PTY, and the CYD serial
display into one self-recovering loop. The bridge shows the boot splash, renders
the login gate (user select + masked password), authenticates via PAM, then
spawns the chosen user's shell through ``su - <user>`` on a pseudo-terminal.
Shell output is parsed by the pure VT100-subset emulator into a character grid,
the grid is diffed, and only the changed cell runs (plus whole-row ``SCROLL``
ops) are sent over serial. CardKB keystrokes are written to the PTY master.

The serial link is held exclusively while the daemon runs. The firmware
``DRAW_IMAGE`` pixels are little-endian RGB565; ``SCROLL`` carries no font size
(the firmware tracks cell height from the last ``DRAW_CELLS``), so the bridge
emits a ``DrawCells`` at the active font around every ``Scroll`` to keep the
device's cell metrics current.

Field-robustness is the top priority: every I/O surface (serial, PTY, CardKB) is
wrapped so a transient error reopens the resource with bounded backoff instead of
crashing the loop; the login screen is the safe idle state; a dead or exited
shell returns to login and NEVER auto-respawns a root shell; and a periodic
keyframe full-repaint recovers a CYD that reset mid-session. There are no
interactive prompts in the deployed path.
"""

from __future__ import annotations

import errno
import fcntl
import os
import pty
import select
import signal
import struct
import termios
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from whiskerframe.metrics import FONT_METRICS
from whiskerframe.models import DrawRect
from whiskerframe.protocol import serialize
from whiskerframe.terminal import (
    DISPLAY_HEIGHT,
    DISPLAY_WIDTH,
    DrawCells,
    TerminalGeometry,
)
from whiskerframe.transport import SerialTransport

from .debug import tracepoint
from .grid import Grid
from .login import LoginState, SubmitEvent, authenticate
from .login_view import render_login
from .theme import Theme, load_theme
from .vt import VTEmulator

if TYPE_CHECKING:
    from collections.abc import Iterator

    from .grid import CellRun

__all__ = [
    "RESIZE_CHORD",
    "RESIZE_SIZES",
    "BridgeConfig",
    "TerminalBridge",
]

RESIZE_CHORD: int = 0x1D
"""CardKB byte that cycles the font size at the login/shell boundary (Ctrl+``]``).

``Ctrl+]`` (ASCII GS, ``0x1D``) is the chosen resize chord: it is virtually never
typed in an interactive shell (it is the classic telnet escape, not a shell
editing key), so intercepting it costs no normal functionality. Pressing it in a
shell cycles the font size through :data:`RESIZE_SIZES`; it is ignored during
login so a resize can never disturb password entry.
"""

RESIZE_SIZES: tuple[int, ...] = (1, 2, 3)
"""Font sizes the resize chord cycles through (grid 53x30 / 26x15 / 17x10)."""

_SERIAL_BACKOFF_START_S: float = 0.5
_SERIAL_BACKOFF_MAX_S: float = 5.0
_POLL_TIMEOUT_S: float = 0.05
_PTY_READ_BYTES: int = 4096
_DEFAULT_FONT_SIZE: int = 2
_DEFAULT_KEYFRAME_S: float = 30.0


@dataclass
class BridgeConfig:
    """
    Resolved terminal-bridge configuration from ``.whiskerframe.yaml``.

    Attributes:
    - serial_port (`str`): Serial device path for the CYD link.
    - baud (`int`): Serial baud rate.
    - font_size (`int`): Initial font-size selector (grid geometry).
    - keyframe_interval_s (`float`): Seconds between full-repaint keyframes.
    - cardkb_bus (`int`): I2C bus number for the CardKB.
    - cardkb_address (`int`): I2C slave address of the CardKB.
    - cardkb_poll_s (`float`): CardKB poll cadence in seconds.
    - users (`list[str]`): Selectable login users.
    - password_mask (`str`): Character echoed per password keystroke.
    - splash_rgb565 (`str`): Path to the pre-converted splash blob ("" to skip).
    - theme (`Theme`): The resolved RGB565 palette.

    """

    serial_port: str = "/dev/ttyUSB0"
    baud: int = 115200
    font_size: int = _DEFAULT_FONT_SIZE
    keyframe_interval_s: float = _DEFAULT_KEYFRAME_S
    cardkb_bus: int = 0
    cardkb_address: int = 0x5F
    cardkb_poll_s: float = 0.05
    users: list[str] = field(default_factory=lambda: ["root"])
    password_mask: str = "*"  # noqa: S105 - a display mask glyph, not a secret
    splash_rgb565: str = ""
    theme: Theme = field(default_factory=load_theme)


def _tiocswinsz(fd: int, geometry: TerminalGeometry) -> None:
    """
    Set the PTY window size from a terminal geometry via ``TIOCSWINSZ``.

    Pack ``(rows, cols, xpixel, ypixel)`` and apply it so shell programs reflow to
    the current grid. Any ioctl failure is swallowed (a resize must never crash
    the loop).

    Args:
    - fd (`int`): The PTY master (or slave) file descriptor.
    - geometry (`TerminalGeometry`): The active grid geometry.

    Returns:
    `None`: Best-effort; errors are ignored.

    """
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


class TerminalBridge:
    """
    Orchestrate splash, login, and shell sessions over the CYD serial link.

    Own the serial transport (reopened on error with bounded backoff), the active
    grid geometry/font size, and the per-session grid state, driving the flow
    splash -> login -> shell -> login indefinitely. Rendering is incremental:
    each new grid is diffed against the last and only changed cell runs (and
    whole-row scrolls) are serialized. The login screen is the safe idle state and
    the daemon never auto-respawns a shell without a fresh authenticated login.
    """

    def __init__(self, config: BridgeConfig) -> None:
        """
        Initialize the bridge from resolved configuration (opens no hardware).

        Args:
        - config (`BridgeConfig`): The resolved bridge configuration.

        """
        self._config = config
        self._theme: Theme = config.theme
        self._font_size = self._valid_font_size(config.font_size)
        self._geometry = TerminalGeometry.for_font_size(self._font_size)
        self._transport: SerialTransport | None = None
        self._serial_backoff = _SERIAL_BACKOFF_START_S
        self._prev: Grid | None = None

    @staticmethod
    def _valid_font_size(font_size: int) -> int:
        """
        Clamp a requested font size to one with known metrics.

        Args:
        - font_size (`int`): The requested font-size selector.

        Returns:
        `int`: ``font_size`` if it has metrics, else the default size.

        """
        return font_size if font_size in FONT_METRICS else _DEFAULT_FONT_SIZE

    # -- serial ---------------------------------------------------------------

    def _ensure_serial(self) -> SerialTransport | None:
        """
        Return an open serial transport, (re)opening it with backoff on failure.

        Returns:
        `SerialTransport | None`: The open transport, or ``None`` if it could not
        be opened this attempt (the caller retries later).

        """
        if self._transport is not None:
            return self._transport
        try:
            self._transport = SerialTransport(
                self._config.serial_port,
                self._config.baud,
            )
        except (OSError, ModuleNotFoundError) as err:
            tracepoint("terminal.serial_reopen", status="failed", error=err)
            time.sleep(self._serial_backoff)
            self._serial_backoff = min(_SERIAL_BACKOFF_MAX_S, self._serial_backoff * 2)
            return None
        self._serial_backoff = _SERIAL_BACKOFF_START_S
        self._prev = None  # force a full repaint after a reopen
        tracepoint(
            "terminal.serial_reopen",
            status="opened",
            port=self._config.serial_port,
        )
        return self._transport

    def _close_serial(self) -> None:
        """
        Close and drop the serial transport so the next send reopens it.

        Returns:
        `None`: The transport handle is released.

        """
        if self._transport is not None:
            try:
                self._transport.close()
            except OSError:
                pass
            self._transport = None

    def _send(self, frame: bytes) -> bool:
        """
        Write one framed command, dropping the port on a write error.

        Args:
        - frame (`bytes`): A complete framed drawing command.

        Returns:
        `bool`: ``True`` if written, ``False`` if the port errored (and was
        closed for reopen).

        """
        transport = self._ensure_serial()
        if transport is None:
            return False
        try:
            transport.send(frame)
        except OSError as err:
            tracepoint("terminal.serial_reopen", status="write_error", error=err)
            self._close_serial()
            return False
        return True

    # -- rendering ------------------------------------------------------------

    def _send_run(self, run: CellRun) -> bool:
        """
        Serialize one grid change run as a ``DRAW_CELLS`` command and send it.

        Args:
        - run (`CellRun`): A coalesced run of changed cells on one row.

        Returns:
        `bool`: ``True`` on a successful write, else ``False``.

        """
        command = DrawCells(
            col=run.col,
            row=run.row,
            fg=run.fg,
            bg=run.bg,
            font_size=self._font_size,
            text=run.text,
        )
        return self._send(serialize(command))

    def _paint(self, grid: Grid) -> None:
        """
        Diff a grid against the previous frame and send the changed runs.

        On the first paint after a (re)open, ``prev`` is absent so the full,
        non-blank grid is drawn; otherwise only the changed runs are sent. The
        painted grid becomes the new baseline only if every run was written, so a
        mid-paint serial drop forces a clean full repaint next time.

        Args:
        - grid (`Grid`): The grid to render to the display.

        Returns:
        `None`: Change runs are transmitted best-effort.

        """
        if self._prev is None:
            # Full repaint: clear the entire panel to the background first so no
            # earlier frame (e.g. the splash image) bleeds through the blank
            # cells that full_repaint() intentionally skips.
            self._clear_panel()
            runs = grid.full_repaint()
        else:
            runs = grid.diff(self._prev)
        ok = all(self._send_run(run) for run in runs)
        self._prev = grid.snapshot() if ok else None

    def _clear_panel(self) -> None:
        """
        Fill the whole visible panel with the theme background colour.

        Sent before every full repaint so the login/shell screen starts from a
        clean background rather than whatever was on the panel before (the splash
        image, or a previous session), since full_repaint() skips blank cells.

        Returns:
        `None`: The clear rectangle is transmitted best-effort.

        """
        clear = DrawRect(
            x=0,
            y=0,
            w=DISPLAY_WIDTH,
            h=DISPLAY_HEIGHT,
            color=self._theme.bg,
            filled=True,
        )
        self._send(serialize(clear))

    # -- login ----------------------------------------------------------------

    def _login(self, keys: Iterator[int]) -> str | None:
        """
        Render and drive the login gate until a user authenticates.

        Repaint the login screen on every keypress, feed keys to a fresh
        :class:`.login.LoginState`, and on a :class:`.login.SubmitEvent`
        authenticate via PAM: success returns the username; failure clears the
        password, shows a brief error, and stays on the gate. The resize chord is
        ignored here so it cannot disturb password entry.

        Args:
        - keys (`Iterator[int]`): The self-recovering CardKB key stream.

        Returns:
        `str | None`: The authenticated username, or ``None`` if the key stream
        ended (so the caller returns to a fresh login).

        """
        state = LoginState(
            users=list(self._config.users),
            mask=self._config.password_mask,
        )
        error = ""
        self._render_login_screen(state, error)
        tracepoint("terminal.login", status="shown", users=len(state.users))
        for key in keys:
            if key == RESIZE_CHORD:
                continue  # resize is ignored mid-login
            submit = state.feed_key(key)
            if submit is not None:
                user = self._handle_submit(state, submit)
                if user is not None:
                    return user
                error = "login failed"
            self._render_login_screen(state, error)
        return None

    def _render_login_screen(self, state: LoginState, error: str) -> None:
        """
        Render the current login state to the display.

        Args:
        - state (`LoginState`): The login UI state to paint.
        - error (`str`): A transient error message (may be empty).

        Returns:
        `None`: The login grid is diffed and sent.

        """
        grid = render_login(
            state,
            self._theme,
            self._geometry.cols,
            self._geometry.rows,
            error=error,
        )
        self._paint(grid)

    def _handle_submit(self, state: LoginState, submit: SubmitEvent) -> str | None:
        """
        Authenticate a submission, clearing the password buffer either way.

        The plaintext password is passed straight to PAM and never logged; the
        login buffer is reset immediately after so no password lingers. On failure
        the gate returns to user selection.

        Args:
        - state (`LoginState`): The login state (reset after the attempt).
        - submit (`SubmitEvent`): The user/password submission.

        Returns:
        `str | None`: The username on success, else ``None``.

        """
        try:
            ok = authenticate(submit.user, submit.password)
        except RuntimeError as err:
            tracepoint("terminal.auth", status="unavailable", error=err)
            ok = False
        tracepoint("terminal.auth", user=submit.user, success=ok)
        state.reset_to_user_select()
        return submit.user if ok else None

    # -- shell ----------------------------------------------------------------

    def _spawn_shell(self, user: str) -> tuple[int, int]:
        """
        Fork a ``su - <user>`` login shell attached to a new PTY.

        Open a PTY pair and fork; the child becomes a session leader on the slave
        side (so it owns a controlling terminal with the right uid/gid/env/PAM
        session) and execs ``su - <user>`` to start ``bash -l`` as that user. The
        parent keeps the master for I/O. The window size is set from the active
        geometry before any output.

        Args:
        - user (`str`): The authenticated user to start the shell as.

        Returns:
        `tuple[int, int]`: The ``(pid, master_fd)`` of the child shell.

        """
        pid, master_fd = pty.fork()
        if pid == 0:  # pragma: no cover - runs only in the forked child
            # su is a PAM-aware system binary resolved from PATH; it sets the
            # target uid/gid/env and starts the user's login shell. The user is
            # already authenticated via PAM before this point.
            os.execvp("su", ["su", "-", user])  # noqa: S606, S607
            os._exit(127)
        _tiocswinsz(master_fd, self._geometry)
        tracepoint("terminal.shell_start", user=user, master_fd=master_fd)
        return pid, master_fd

    def _run_shell(self, user: str, keys: Iterator[int]) -> None:
        """
        Run one shell session, pumping PTY<->CardKB<->serial until it exits.

        Build a fresh grid and emulator for the session, then loop: poll the PTY
        master for output (fed through the VT emulator and painted) while draining
        pending CardKB keys to the PTY, repainting on change and sending a
        keyframe full-repaint every ``keyframe_interval_s``. The resize chord
        rebuilds the geometry/grid live. PTY EOF or exit returns to the caller
        (which goes back to login); the shell is never auto-respawned.

        Args:
        - user (`str`): The authenticated user whose shell to run.
        - keys (`Iterator[int]`): The CardKB key stream (drained non-blocking).

        Returns:
        `None`: Returns when the shell session ends.

        """
        pid, master_fd = self._spawn_shell(user)
        session = _ShellSession(self, master_fd, keys)
        try:
            session.pump()
        finally:
            self._reap(pid, master_fd)
            tracepoint("terminal.logout", user=user)
            self._prev = None  # force a clean repaint of the next login screen

    def _reap(self, pid: int, master_fd: int) -> None:
        """
        Close the PTY master and reap the shell child process.

        Args:
        - pid (`int`): The shell child PID.
        - master_fd (`int`): The PTY master descriptor to close.

        Returns:
        `None`: Resources are released best-effort.

        """
        try:
            os.close(master_fd)
        except OSError:
            pass
        try:
            os.kill(pid, signal.SIGHUP)
        except OSError:
            pass
        try:
            os.waitpid(pid, 0)
        except OSError:
            pass

    def _rebuild_geometry(self, master_fd: int) -> Grid:
        """
        Cycle the font size, recompute geometry, and inform the PTY.

        Advance :data:`RESIZE_SIZES`, recompute the grid geometry, push the new
        window size to the PTY via ``TIOCSWINSZ`` so programs reflow, and force a
        full repaint. Returns a fresh blank grid sized to the new geometry.

        Args:
        - master_fd (`int`): The PTY master to resize.

        Returns:
        `Grid`: A new blank grid at the new geometry.

        """
        index = (
            RESIZE_SIZES.index(self._font_size)
            if self._font_size in RESIZE_SIZES
            else 0
        )
        self._font_size = RESIZE_SIZES[(index + 1) % len(RESIZE_SIZES)]
        self._geometry = TerminalGeometry.for_font_size(self._font_size)
        _tiocswinsz(master_fd, self._geometry)
        self._prev = None
        tracepoint(
            "terminal.resize",
            font_size=self._font_size,
            cols=self._geometry.cols,
        )
        return Grid(
            self._geometry.cols,
            self._geometry.rows,
            self._theme.fg,
            self._theme.bg,
        )

    # -- top-level loop -------------------------------------------------------

    def run(self, keys: Iterator[int], *, sessions: int | None = None) -> None:
        """
        Run the splash/login/shell loop until the key stream ends.

        Show the boot splash once, then repeatedly render the login gate, and on a
        successful authentication run that user's shell until it exits, returning
        to login afterwards. Bounded by ``sessions`` for tests; unbounded in the
        daemon.

        Args:
        - keys (`Iterator[int]`): The self-recovering CardKB key stream.
        - sessions (`int | None`, optional): Stop after this many shell sessions
          (for tests). Defaults to unbounded.

        Returns:
        `None`: Returns when the key stream ends or the session budget is spent.

        """
        self._show_splash()
        completed = 0
        while sessions is None or completed < sessions:
            user = self._login(keys)
            if user is None:
                return
            self._run_shell(user, keys)
            completed += 1

    def _show_splash(self) -> None:
        """
        Blit the configured boot splash, if any, before the first login.

        Returns:
        `None`: The splash is sent best-effort (missing blob is skipped).

        """
        if not self._config.splash_rgb565:
            return
        from .splash import show_splash

        transport = self._ensure_serial()
        if transport is not None:
            show_splash(transport, self._config.splash_rgb565)


class _ShellSession:
    """
    One live shell session's PTY/CardKB/serial pump loop.

    Hold the per-session grid, VT emulator, and keyframe clock for a single
    ``_run_shell`` call, so the pump logic stays small and the bridge keeps the
    long-lived serial/geometry state. Robust by construction: PTY read errors end
    the session cleanly (back to login) and CardKB/serial errors are handled by
    their own layers.
    """

    def __init__(
        self,
        bridge: TerminalBridge,
        master_fd: int,
        keys: Iterator[int],
    ) -> None:
        """
        Initialize a shell session pump over an open PTY master.

        Args:
        - bridge (`TerminalBridge`): The owning bridge (serial, geometry, paint).
        - master_fd (`int`): The PTY master descriptor.
        - keys (`Iterator[int]`): The CardKB key stream to drain.

        """
        self._bridge = bridge
        self._master_fd = master_fd
        self._keys = keys
        self._grid = Grid(
            bridge._geometry.cols,
            bridge._geometry.rows,
            bridge._theme.fg,
            bridge._theme.bg,
        )
        self._emulator = VTEmulator(self._grid, bridge._theme)
        self._last_keyframe = time.monotonic()

    def pump(self) -> None:
        """
        Pump PTY output to the display and CardKB keys to the PTY until exit.

        Loop until the PTY signals EOF or errors: read any available shell output
        into the emulator and repaint, drain pending keystrokes to the PTY
        (intercepting the resize chord), and emit a periodic keyframe repaint.

        Returns:
        `None`: Returns when the shell session ends.

        """
        self._bridge._paint(self._grid)
        running = True
        while running:
            running = self._read_pty()
            self._drain_keys()
            self._maybe_keyframe()

    def _read_pty(self) -> bool:
        """
        Read one chunk of PTY output, feeding the emulator and repainting.

        Returns:
        `bool`: ``True`` if the shell is still running, ``False`` on EOF/error.

        """
        try:
            readable, _, _ = select.select([self._master_fd], [], [], _POLL_TIMEOUT_S)
        except OSError:
            return False
        if not readable:
            return True
        try:
            data = os.read(self._master_fd, _PTY_READ_BYTES)
        except OSError as err:
            return err.errno == errno.EAGAIN
        if not data:
            return False
        self._emulator.feed(data)
        self._bridge._paint(self._grid)
        return True

    def _drain_keys(self) -> None:
        """
        Write any immediately-available CardKB keys to the PTY master.

        Pull keys without blocking the pump (the CardKB iterator yields only
        pressed keys); the resize chord is intercepted and rebuilds the geometry
        rather than reaching the shell. A write error ends the session cleanly.

        Returns:
        `None`: Keys are forwarded best-effort.

        """
        for key in self._pending_keys():
            if key == RESIZE_CHORD:
                self._grid = self._bridge._rebuild_geometry(self._master_fd)
                self._emulator = VTEmulator(self._grid, self._bridge._theme)
                self._bridge._paint(self._grid)
                continue
            try:
                os.write(self._master_fd, bytes((key,)))
            except OSError:
                return

    def _pending_keys(self) -> list[int]:
        """
        Collect CardKB keys that are ready right now, without blocking.

        The CardKB stream is poll-backed; this reads one key per pump turn so the
        PTY stays responsive without starving output. Returns an empty list when
        no key is pending.

        Returns:
        `list[int]`: Zero or one pending key byte.

        """
        try:
            key = next(self._keys)
        except StopIteration:
            return []
        return [key]

    def _maybe_keyframe(self) -> None:
        """
        Force a full-repaint keyframe once the keyframe interval elapses.

        Dropping the previous-frame baseline makes the next paint a full repaint,
        which recovers a CYD that reset mid-session.

        Returns:
        `None`: May trigger a full repaint.

        """
        interval = self._bridge._config.keyframe_interval_s
        if interval <= 0:
            return
        now = time.monotonic()
        if now - self._last_keyframe >= interval:
            self._last_keyframe = now
            self._bridge._prev = None
            self._bridge._paint(self._grid)
            tracepoint("terminal.keyframe", font_size=self._bridge._font_size)
