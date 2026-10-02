"""
Property/unit test for the VT100-subset terminal emulator.

**Validates: Requirements (cyd-terminal design: VT100 subset)**

Exercise :class:`terminal.vt.VTEmulator` against a `terminal.grid.Grid`:

- printable bytes fill consecutive cells and wrap at the right edge;
- ``CR``/``LF``/``BS``/``TAB`` move the cursor as specified;
- CSI cursor moves (``A``/``B``/``C``/``D``, ``H``) reposition the cursor and
  erase-in-line (``K``) / erase-in-display (``J``) clear the right cells;
- an SGR colour (``CSI 31m``) tints subsequent cells;
- advancing past the last row scrolls the grid up;
- an unknown escape sequence is consumed and leaves the grid unchanged versus a
  baseline (robustness), plus a hypothesis fuzz that random bytes never raise.

The script is pure (no hardware, no Pillow). It adds ``pi/`` to ``sys.path``,
runs as ``uv run python test/prop_vt_emulator.py``, prints ``PASS`` on success,
and exits non-zero on the first failure.
"""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "pi"))

from terminal.grid import Grid
from terminal.theme import DEFAULT_ANSI, load_theme
from terminal.vt import VTEmulator

MAX_EXAMPLES: int = 300
"""Number of generated examples for the fuzz property."""

_FG: int = 0xFD9C
_BG: int = 0x18C5


def _new() -> tuple[Grid, VTEmulator]:
    """
    Build a fresh 10x4 grid and an emulator over the a11y theme.

    Returns:
    `tuple[Grid, VTEmulator]`: The grid and its emulator.

    """
    grid = Grid(cols=10, rows=4, default_fg=_FG, default_bg=_BG)
    return grid, VTEmulator(grid, load_theme({}))


def _row_text(grid: Grid, row: int) -> str:
    """
    Return the characters of one grid row as a string.

    Args:
    - grid (`Grid`): The grid to read.
    - row (`int`): The row index.

    Returns:
    `str`: The row's characters, left to right.

    """
    return "".join(grid.cell_at(row, col).char for col in range(grid.cols))


def check_printables_and_wrap() -> None:
    """
    Assert printables fill cells left-to-right and wrap at the right edge.

    Raises:
    - `AssertionError`: If text does not fill/wrap as expected.

    Returns:
    `None`: Returns nothing on success.

    """
    grid, vt = _new()
    vt.feed(b"HELLO")
    assert _row_text(grid, 0).startswith("HELLO")
    grid, vt = _new()
    vt.feed(b"ABCDEFGHIJK")  # 11 chars into a 10-wide grid -> wraps
    assert _row_text(grid, 0) == "ABCDEFGHIJ"
    assert _row_text(grid, 1).startswith("K")


def check_control_chars() -> None:
    """
    Assert CR, LF, BS, and TAB move the cursor correctly.

    Raises:
    - `AssertionError`: If any control character misbehaves.

    Returns:
    `None`: Returns nothing on success.

    """
    grid, vt = _new()
    vt.feed(b"AB\r")
    assert grid.cursor_col == 0, "CR must return to column 0"
    vt.feed(b"X")
    assert grid.cell_at(0, 0).char == "X", "CR+print overwrites column 0"

    grid, vt = _new()
    vt.feed(b"AB\b")
    assert grid.cursor_col == 1, "BS moves left one column"

    grid, vt = _new()
    vt.feed(b"\t")
    assert grid.cursor_col == 8, "TAB advances to the 8th column"

    grid, vt = _new()
    vt.feed(b"A\nB")
    assert grid.cell_at(1, 1).char == "B", "LF moves down without CR"


def check_csi_cursor_and_erase() -> None:
    """
    Assert CSI cursor positioning and erase operations.

    Raises:
    - `AssertionError`: If positioning or erase behave incorrectly.

    Returns:
    `None`: Returns nothing on success.

    """
    grid, vt = _new()
    vt.feed(b"\x1b[2;3H")  # 1-based row 2 col 3 -> 0-based (1, 2)
    assert (grid.cursor_row, grid.cursor_col) == (1, 2)
    vt.feed(b"\x1b[A")  # up one
    assert grid.cursor_row == 0
    vt.feed(b"\x1b[2C")  # right two
    assert grid.cursor_col == 4

    grid, vt = _new()
    vt.feed(b"ABCDE\r\x1b[K")  # erase to end of line from col 0
    assert _row_text(grid, 0) == " " * grid.cols

    grid, vt = _new()
    vt.feed(b"HELLO\x1b[2J")  # erase whole display
    assert _row_text(grid, 0) == " " * grid.cols


def check_sgr_color() -> None:
    """
    Assert an SGR colour code tints subsequent cells.

    Raises:
    - `AssertionError`: If the foreground is not applied.

    Returns:
    `None`: Returns nothing on success.

    """
    grid, vt = _new()
    vt.feed(b"\x1b[31mR")
    assert grid.cell_at(0, 0).fg == DEFAULT_ANSI[1], "CSI 31m must set red fg"
    vt.feed(b"\x1b[0mN")
    assert grid.cell_at(0, 1).fg == _FG, "CSI 0m must reset fg to default"


def check_scroll_on_overflow() -> None:
    """
    Assert advancing past the last row scrolls content up.

    Raises:
    - `AssertionError`: If content does not scroll on overflow.

    Returns:
    `None`: Returns nothing on success.

    """
    grid, vt = _new()  # 4 rows
    vt.feed(b"L0\r\nL1\r\nL2\r\nL3\r\nL4")
    # The first line should have scrolled off the top.
    assert _row_text(grid, 0).startswith("L1")
    assert _row_text(grid, 3).startswith("L4")


def check_unknown_escape_ignored() -> None:
    """
    Assert an unknown escape sequence leaves the grid unchanged vs a baseline.

    Raises:
    - `AssertionError`: If the grid differs after an unknown escape.

    Returns:
    `None`: Returns nothing on success.

    """
    baseline, vt_base = _new()
    vt_base.feed(b"HI")
    probe, vt_probe = _new()
    # CSI with an unsupported final 'Z', and an unsupported ESC ] OSC-ish seq.
    vt_probe.feed(b"HI\x1b[5Z\x1b]0;title\x07")
    for row in range(probe.rows):
        assert _row_text(probe, row) == _row_text(baseline, row), f"row {row} differs"


@given(data=st.binary(min_size=0, max_size=128))
@settings(max_examples=MAX_EXAMPLES)
def check_fuzz_never_raises(data: bytes) -> None:
    """
    Assert feeding arbitrary bytes never raises and keeps the cursor in bounds.

    Args:
    - data (`bytes`): Arbitrary input bytes.

    Raises:
    - `AssertionError`: If the cursor leaves the grid bounds.

    Returns:
    `None`: Returns nothing on success.

    """
    grid, vt = _new()
    vt.feed(data)
    assert 0 <= grid.cursor_row < grid.rows
    assert 0 <= grid.cursor_col < grid.cols


def main() -> None:
    """
    Run every emulator check and report the outcome.

    Returns:
    `None`: Exits ``1`` on failure; prints ``PASS`` otherwise.

    """
    try:
        check_printables_and_wrap()
        check_control_chars()
        check_csi_cursor_and_erase()
        check_sgr_color()
        check_scroll_on_overflow()
        check_unknown_escape_ignored()
        check_fuzz_never_raises()
    except AssertionError:
        traceback.print_exc()
        sys.exit(1)
    print("PASS")


if __name__ == "__main__":
    main()
