"""
Pure VT100-subset terminal emulator: shell output bytes to grid mutations.

Consume the byte stream a login shell writes and mutate a :class:`.grid.Grid`
accordingly, covering the subset a real shell session needs: printable ASCII
(advance + wrap), the control characters ``LF``/``CR``/``BS``/``TAB``/``BEL``,
and the common CSI sequences -- cursor moves (``A``/``B``/``C``/``D``), absolute
positioning (``H``/``f``), erase-in-display (``J``) and erase-in-line (``K``), and
SGR colour selection (``m``) mapped through a :class:`.theme.Theme`.

The emulator is a pure byte-driven state machine (``GROUND`` -> ``ESC`` ->
``CSI``) with no I/O. By design it is robust: any unsupported or malformed escape
sequence is consumed and ignored without corrupting the grid, and all cursor
motion clamps to the grid bounds, so a hostile or garbled stream can never crash
the caller (field-robustness). Bytes are decoded as latin-1 so every input byte
maps to a single display cell.
"""

from __future__ import annotations

from enum import Enum, auto
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

    from .grid import Grid
    from .theme import Theme

__all__ = [
    "VTEmulator",
]

_BEL: int = 0x07
_BS: int = 0x08
_TAB: int = 0x09
_LF: int = 0x0A
_CR: int = 0x0D
_ESC: int = 0x1B
_CSI_FINAL_MIN: int = 0x40  # '@'
_CSI_FINAL_MAX: int = 0x7E  # '~'
_PRINTABLE_MIN: int = 0x20
_PRINTABLE_MAX: int = 0x7E
_DEFAULT_PARAM: int = 1


class _State(Enum):
    r"""
    Parser state for the VT byte state machine.

    Attributes:
    - GROUND: Default state; printable and control bytes act directly.
    - ESC: Saw ``ESC``; awaiting a ``[`` to begin a CSI sequence.
    - CSI: Inside a CSI sequence; accumulating parameter bytes until a final.
    - OSC: Inside an operating-system-command string; consumed until a
      terminator (``BEL`` or ``ESC \\``) and ignored.

    """

    GROUND = auto()
    ESC = auto()
    CSI = auto()
    OSC = auto()


class VTEmulator:
    """
    A pure VT100-subset emulator driving a `Grid` from shell output bytes.

    Maintain the current foreground/background colours (seeded from the theme
    defaults) and a small parser state machine, mutating the attached grid as
    bytes arrive via :meth:`feed`. Unsupported escape sequences are consumed and
    ignored so the grid is never corrupted.

    Attributes:
    - grid (`Grid`): The character grid mutated by the emulator.
    - theme (`Theme`): The palette and SGR mapping used for colours.
    - fg (`int`): Current RGB565 foreground colour.
    - bg (`int`): Current RGB565 background colour.

    """

    def __init__(self, grid: Grid, theme: Theme) -> None:
        """
        Initialize the emulator over a grid and theme.

        Args:
        - grid (`Grid`): The grid to mutate.
        - theme (`Theme`): The palette and SGR mapping; its defaults seed the
          current colours.

        """
        self.grid = grid
        self.theme = theme
        self.fg = theme.fg
        self.bg = theme.bg
        self._state = _State.GROUND
        self._params: list[str] = []
        self._param_digits: list[str] = []

    def feed(self, data: bytes) -> None:
        """
        Feed a chunk of shell output bytes, mutating the grid.

        Dispatch each byte through the parser state machine. The method is
        total: it never raises on malformed input and may be called repeatedly
        with partial chunks (parser state persists across calls).

        Args:
        - data (`bytes`): Raw bytes from the shell's PTY output.

        Returns:
        `None`: The grid is mutated in place.

        """
        for byte in data:
            self._consume(byte)

    def _consume(self, byte: int) -> None:
        """
        Advance the state machine by one byte.

        Args:
        - byte (`int`): The next input byte in ``[0, 255]``.

        Returns:
        `None`: State and/or grid are updated in place.

        """
        if self._state is _State.GROUND:
            self._consume_ground(byte)
        elif self._state is _State.ESC:
            self._consume_esc(byte)
        elif self._state is _State.OSC:
            self._consume_osc(byte)
        else:
            self._consume_csi(byte)

    def _consume_ground(self, byte: int) -> None:
        """
        Handle a byte in the GROUND state (printables and control codes).

        Args:
        - byte (`int`): The input byte.

        Returns:
        `None`: The grid/cursor is updated in place.

        """
        if byte == _ESC:
            self._state = _State.ESC
        elif _PRINTABLE_MIN <= byte <= _PRINTABLE_MAX:
            self.grid.put_char(chr(byte), self.fg, self.bg)
        elif byte >= 0x80:
            # High-bit bytes (CP437/latin-1 glyphs) print as single cells.
            self.grid.put_char(chr(byte), self.fg, self.bg)
        else:
            self._consume_control(byte)

    def _consume_control(self, byte: int) -> None:
        """
        Handle a C0 control byte in the GROUND state.

        Args:
        - byte (`int`): The control byte (``LF``/``CR``/``BS``/``TAB``/``BEL``).

        Returns:
        `None`: The grid/cursor is updated in place; unknown controls are ignored.

        """
        if byte == _LF:
            self.grid.newline()
        elif byte == _CR:
            self.grid.carriage_return()
        elif byte == _BS:
            self.grid.backspace()
        elif byte == _TAB:
            self.grid.tab()
        # BEL and any other C0 control are intentionally ignored.

    def _consume_esc(self, byte: int) -> None:
        """
        Handle the byte following an ``ESC``.

        A ``[`` begins a CSI sequence; anything else aborts the escape and is
        reprocessed in the GROUND state so no byte is lost.

        Args:
        - byte (`int`): The byte after ``ESC``.

        Returns:
        `None`: State is updated in place.

        """
        if byte == ord("["):
            self._state = _State.CSI
            self._params = []
            self._param_digits = []
        elif byte == ord("]"):
            # OSC string (e.g. window-title set): consume until BEL/ST, ignore.
            self._state = _State.OSC
        else:
            # Other unsupported escapes (e.g. ESC ( charset, ESC = / >): consume
            # the single following byte and return to GROUND. The grid is left
            # intact (no printing), matching the unknown-escape-safe contract.
            self._state = _State.GROUND

    def _consume_osc(self, byte: int) -> None:
        r"""
        Consume an OSC string byte, ending on a ``BEL`` terminator.

        OSC payloads (window titles, colour queries) are ignored entirely. The
        string ends at ``BEL``; a bare ``ESC`` (start of a possible ``ESC \\``
        string terminator) also returns to GROUND so the stream resynchronizes.

        Args:
        - byte (`int`): The next byte of the OSC string.

        Returns:
        `None`: State is updated in place; no grid mutation occurs.

        """
        if byte in (_BEL, _ESC):
            self._state = _State.GROUND

    def _consume_csi(self, byte: int) -> None:
        """
        Accumulate CSI parameter bytes and dispatch on the final byte.

        Digits and ``;`` separators build the parameter list; a final byte in
        ``@``..``~`` dispatches the sequence. Private-marker and intermediate
        bytes are tolerated and the sequence is ignored if its final is
        unsupported.

        Args:
        - byte (`int`): The next CSI byte.

        Returns:
        `None`: State and/or grid are updated in place.

        """
        char = chr(byte)
        if char.isdigit():
            self._param_digits.append(char)
            return
        if char == ";":
            self._params.append("".join(self._param_digits))
            self._param_digits = []
            return
        if _CSI_FINAL_MIN <= byte <= _CSI_FINAL_MAX:
            self._params.append("".join(self._param_digits))
            self._dispatch_csi(char)
            self._state = _State.GROUND
            self._params = []
            self._param_digits = []
            return
        # Intermediate / private marker byte (e.g. '?'): keep accumulating.

    def _int_params(self, default: int = _DEFAULT_PARAM) -> list[int]:
        """
        Parse the accumulated CSI parameters into integers.

        Empty parameters resolve to ``default`` (the VT100 convention). Any
        non-numeric parameter also resolves to ``default`` so parsing never
        raises.

        Args:
        - default (`int`, optional): Value for empty/absent parameters. Defaults to 1.

        Returns:
        `list[int]`: The parsed parameter integers.

        """
        result: list[int] = []
        for raw in self._params:
            if raw == "":
                result.append(default)
            else:
                try:
                    result.append(int(raw))
                except ValueError:
                    result.append(default)
        return result

    def _dispatch_csi(self, final: str) -> None:
        """
        Dispatch a completed CSI sequence on its final byte.

        Handle cursor motion (``A``/``B``/``C``/``D``), absolute positioning
        (``H``/``f``), erase display (``J``), erase line (``K``), and SGR (``m``).
        Any other final byte is ignored (consumed without mutating the grid).

        Args:
        - final (`str`): The CSI final character.

        Returns:
        `None`: The grid/cursor and colours are updated in place.

        """
        if final in ("A", "B", "C", "D"):
            self._move_cursor(final)
        elif final in ("H", "f"):
            self._set_position()
        elif final in _CSI_SIMPLE:
            # Erase display (J), erase line (K), or SGR (m).
            _CSI_SIMPLE[final](self)
        # Unsupported finals are ignored, leaving the grid intact.

    def _move_cursor(self, final: str) -> None:
        """
        Apply a relative cursor move for ``A``/``B``/``C``/``D``.

        Args:
        - final (`str`): The direction final (up/down/right/left).

        Returns:
        `None`: The cursor is updated in place (clamped by the grid).

        """
        params = self._int_params()
        count = params[0] if params else _DEFAULT_PARAM
        row = self.grid.cursor_row
        col = self.grid.cursor_col
        if final == "A":
            row -= count
        elif final == "B":
            row += count
        elif final == "C":
            col += count
        else:  # "D"
            col -= count
        self.grid.set_cursor(row, col)

    def _set_position(self) -> None:
        """
        Apply an absolute cursor position for ``H``/``f`` (1-based params).

        Returns:
        `None`: The cursor is moved to the 0-based equivalent (clamped).

        """
        params = self._int_params()
        row = (params[0] if len(params) >= 1 else _DEFAULT_PARAM) - 1
        col = (params[1] if len(params) >= 2 else _DEFAULT_PARAM) - 1
        self.grid.set_cursor(row, col)

    def _erase_display(self) -> None:
        """
        Apply erase-in-display (``J``): mode 0 clears cursor to end, 2 clears all.

        Returns:
        `None`: The grid is updated in place.

        """
        params = self._int_params(default=0)
        mode = params[0] if params else 0
        if mode == 2:
            self.grid.clear()
        else:
            self.grid.clear_to_end_of_screen()

    def _erase_line(self) -> None:
        """
        Apply erase-in-line (``K``): clear from the cursor to the end of line.

        Returns:
        `None`: The grid is updated in place.

        """
        self.grid.clear_to_end_of_line()

    def _apply_sgr(self) -> None:
        """
        Apply SGR colour selection (``m``) through the theme mapping.

        Each parameter is mapped via `Theme.sgr_to_rgb565`; a reset restores the
        theme defaults, and foreground/background deltas update the current
        colours. An empty parameter list is treated as a reset (VT100 ``CSI m``).

        Returns:
        `None`: The current foreground/background colours are updated in place.

        """
        params = self._int_params(default=0) or [0]
        for code in params:
            self._apply_sgr_code(code)

    def _apply_sgr_code(self, code: int) -> None:
        """
        Apply a single SGR parameter code to the current colours.

        Args:
        - code (`int`): The SGR parameter code.

        Returns:
        `None`: The current foreground/background colours are updated in place.

        """
        result = self.theme.sgr_to_rgb565(code, self.theme.fg, self.theme.bg)
        if result.reset:
            self.fg = self.theme.fg
            self.bg = self.theme.bg
        if result.fg is not None:
            self.fg = result.fg
        if result.bg is not None:
            self.bg = result.bg


_CSI_SIMPLE: dict[str, Callable[[VTEmulator], None]] = {
    "J": VTEmulator._erase_display,
    "K": VTEmulator._erase_line,
    "m": VTEmulator._apply_sgr,
}
"""CSI finals with no cursor argument -> their `VTEmulator` handler method."""
