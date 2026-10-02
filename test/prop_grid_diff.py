"""
Property test for the terminal grid diff and full-repaint helpers.

**Validates: Requirements (cyd-terminal design: grid diff / full repaint)**

Assert the three diff invariants of :class:`terminal.grid.Grid`:

1. Diffing a grid against an identical snapshot yields no runs.
2. After writing characters, the diff against the pre-write snapshot emits runs
   whose cells reproduce exactly the changed cells (and no unchanged cell).
3. :meth:`Grid.full_repaint` emits runs covering exactly the non-blank cells.

The script is pure (no hardware, no Pillow). It adds ``pi/`` to ``sys.path`` to
import the ``terminal`` package, runs as ``uv run python test/prop_grid_diff.py``,
prints ``PASS`` on success, and exits non-zero on a counterexample.
"""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "pi"))

from terminal.grid import Cell, Grid

MAX_EXAMPLES: int = 300
"""Number of generated examples per property check."""

_DEFAULT_FG: int = 0xFD9C
_DEFAULT_BG: int = 0x18C5

_writes = st.lists(
    st.tuples(
        st.integers(min_value=0, max_value=7),  # row
        st.integers(min_value=0, max_value=11),  # col
        st.characters(min_codepoint=0x21, max_codepoint=0x7E),  # non-space char
        st.integers(min_value=0, max_value=0xFFFF),  # fg
        st.integers(min_value=0, max_value=0xFFFF),  # bg
    ),
    min_size=0,
    max_size=20,
)


def _make_grid() -> Grid:
    """
    Build a fresh 12x8 grid with the default a11y color pair.

    Returns:
    `Grid`: A blank grid for the properties under test.

    """
    return Grid(cols=12, rows=8, default_fg=_DEFAULT_FG, default_bg=_DEFAULT_BG)


def _apply_writes(
    grid: Grid,
    writes: list[tuple[int, int, str, int, int]],
) -> None:
    """
    Write each generated cell directly into the grid via the cursor.

    Args:
    - grid (`Grid`): The grid to mutate.
    - writes (`list`): Generated ``(row, col, char, fg, bg)`` tuples.

    Returns:
    `None`: The grid is mutated in place.

    """
    for row, col, char, fg, bg in writes:
        grid.set_cursor(row, col)
        grid.put_char(char, fg, bg)


@given(writes=_writes)
@settings(max_examples=MAX_EXAMPLES)
def check_diff_matches_changes(  # noqa: C901 - exhaustive per-cell assertions
    writes: list[tuple[int, int, str, int, int]],
) -> None:
    """
    Assert diff emits exactly the changed cells; identical grids diff empty.

    Args:
    - writes (`list`): Generated cell writes applied after the snapshot.

    Raises:
    - `AssertionError`: If an unchanged grid diffs non-empty, or the runs do not
      reconstruct exactly the changed cells.

    Returns:
    `None`: Returns nothing when the invariants hold.

    """
    grid = _make_grid()
    prev = grid.snapshot()
    assert grid.diff(prev) == [], "unchanged grid must diff to no runs"

    _apply_writes(grid, writes)
    runs = grid.diff(prev)

    reported: dict[tuple[int, int], Cell] = {}
    for run in runs:
        for offset, char in enumerate(run.text):
            reported[(run.row, run.col + offset)] = Cell(char, run.fg, run.bg)

    for row in range(grid.rows):
        for col in range(grid.cols):
            now = grid.cell_at(row, col)
            was = prev.cell_at(row, col)
            if now != was:
                assert reported.get((row, col)) == now, f"missing change at {row},{col}"
            else:
                assert (row, col) not in reported, f"spurious run at {row},{col}"


@given(writes=_writes)
@settings(max_examples=MAX_EXAMPLES)
def check_full_repaint_non_blank(  # noqa: C901 - exhaustive per-cell assertions
    writes: list[tuple[int, int, str, int, int]],
) -> None:
    """
    Assert full_repaint covers exactly the non-blank cells.

    Args:
    - writes (`list`): Generated cell writes applied to the grid.

    Raises:
    - `AssertionError`: If a repaint run covers a blank cell or omits a non-blank.

    Returns:
    `None`: Returns nothing when the invariant holds.

    """
    grid = _make_grid()
    _apply_writes(grid, writes)
    runs = grid.full_repaint()

    covered: set[tuple[int, int]] = set()
    for run in runs:
        for offset in range(len(run.text)):
            covered.add((run.row, run.col + offset))

    for row in range(grid.rows):
        for col in range(grid.cols):
            cell = grid.cell_at(row, col)
            blank = (
                cell.char == " " and cell.fg == _DEFAULT_FG and cell.bg == _DEFAULT_BG
            )
            if blank:
                assert (row, col) not in covered, f"blank covered at {row},{col}"
            else:
                assert (row, col) in covered, f"non-blank missed at {row},{col}"


def main() -> None:
    """
    Run the diff/repaint properties and report the outcome.

    Returns:
    `None`: Exits ``1`` on a counterexample; prints ``PASS`` otherwise.

    """
    try:
        check_diff_matches_changes()
        check_full_repaint_non_blank()
    except AssertionError:
        traceback.print_exc()
        sys.exit(1)
    print("PASS")


if __name__ == "__main__":
    main()
