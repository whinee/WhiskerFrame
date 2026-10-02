"""
Pure character grid for the CYD terminal: cells, cursor, scrolling, and diffing.

Model the terminal screen as a fixed ``cols`` x ``rows`` matrix of :class:`Cell`
values (a character plus RGB565 foreground/background), with a cursor and the
editing primitives a VT100-subset emulator drives: printable advance, newline,
carriage return, backspace, tab, erase, and whole-row scrolling. The grid also
computes the incremental draw runs the serial path needs: :meth:`Grid.diff`
coalesces consecutive changed cells sharing a color pair on one row into a single
:class:`CellRun` (mapping to one ``DRAW_CELLS`` command), and
:meth:`Grid.full_repaint` returns every non-blank run for a keyframe.

This module is pure: it imports no hardware driver, no Pillow, and performs no
I/O, so it is fully unit- and property-testable on the host. By construction it
cannot crash a long-running caller: cursor moves clamp to the grid bounds and
out-of-range writes are ignored rather than raising.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import NamedTuple

__all__ = [
    "DEFAULT_TAB_WIDTH",
    "Cell",
    "CellRun",
    "Grid",
]

DEFAULT_TAB_WIDTH: int = 8
"""Default tab stop width in columns (classic 8-column tabs)."""


@dataclass(frozen=True)
class Cell:
    """
    A single terminal cell: one character with RGB565 colors.

    Attributes:
    - char (`str`): The single display character (exactly one character).
    - fg (`int`): RGB565 foreground color.
    - bg (`int`): RGB565 background color.

    """

    char: str
    fg: int
    bg: int


class CellRun(NamedTuple):
    """
    A horizontal run of cells sharing one color pair, ready for ``DRAW_CELLS``.

    Attributes:
    - row (`int`): Row of the run, in cell units.
    - col (`int`): Starting column of the run, in cell units.
    - fg (`int`): RGB565 foreground color shared by the run.
    - bg (`int`): RGB565 background color shared by the run.
    - text (`str`): The run characters, one per cell.

    """

    row: int
    col: int
    fg: int
    bg: int
    text: str


class Grid:
    """
    A mutable ``cols`` x ``rows`` character grid with a cursor.

    Hold the terminal's cell matrix, a cursor position, and the default color
    pair used to fill blanks. Expose the editing primitives a VT100-subset
    emulator drives and the diff/repaint helpers the serial path consumes. All
    mutating operations are total: coordinates are clamped and out-of-range
    writes are ignored, so a malformed escape sequence can never crash a caller.

    Attributes:
    - cols (`int`): Number of columns.
    - rows (`int`): Number of rows.
    - default_fg (`int`): RGB565 foreground used for blank cells.
    - default_bg (`int`): RGB565 background used for blank cells.
    - cursor_row (`int`): Current cursor row in ``[0, rows - 1]``.
    - cursor_col (`int`): Current cursor column in ``[0, cols - 1]``.

    """

    def __init__(
        self,
        cols: int,
        rows: int,
        default_fg: int,
        default_bg: int,
    ) -> None:
        """
        Initialize a blank grid filled with the default color pair.

        Args:
        - cols (`int`): Number of columns (must be >= 1).
        - rows (`int`): Number of rows (must be >= 1).
        - default_fg (`int`): RGB565 foreground for blank cells.
        - default_bg (`int`): RGB565 background for blank cells.

        Raises:
        - `ValueError`: If ``cols`` or ``rows`` is less than 1.

        """
        if cols < 1 or rows < 1:
            msg = f"grid dimensions must be >= 1, got cols={cols}, rows={rows}"
            raise ValueError(msg)
        self.cols = cols
        self.rows = rows
        self.default_fg = default_fg
        self.default_bg = default_bg
        self.cursor_row = 0
        self.cursor_col = 0
        self._cells: list[list[Cell]] = [
            [self._blank() for _ in range(cols)] for _ in range(rows)
        ]

    def _blank(self) -> Cell:
        """
        Return a fresh blank cell using the default color pair.

        Returns:
        `Cell`: A space cell with the grid's default foreground/background.

        """
        return Cell(char=" ", fg=self.default_fg, bg=self.default_bg)

    def cell_at(self, row: int, col: int) -> Cell:
        """
        Return the cell at ``(row, col)``.

        Args:
        - row (`int`): Row index.
        - col (`int`): Column index.

        Raises:
        - `IndexError`: If ``(row, col)`` is outside the grid.

        Returns:
        `Cell`: The cell at the given position.

        """
        return self._cells[row][col]

    def _in_bounds(self, row: int, col: int) -> bool:
        """
        Report whether ``(row, col)`` lies inside the grid.

        Args:
        - row (`int`): Row index.
        - col (`int`): Column index.

        Returns:
        `bool`: ``True`` if the position is addressable.

        """
        return 0 <= row < self.rows and 0 <= col < self.cols

    def set_cursor(self, row: int, col: int) -> None:
        """
        Move the cursor to ``(row, col)``, clamped to the grid bounds.

        Args:
        - row (`int`): Target row (clamped to ``[0, rows - 1]``).
        - col (`int`): Target column (clamped to ``[0, cols - 1]``).

        Returns:
        `None`: The cursor is updated in place.

        """
        self.cursor_row = max(0, min(row, self.rows - 1))
        self.cursor_col = max(0, min(col, self.cols - 1))

    def put_char(self, char: str, fg: int, bg: int) -> None:
        """
        Write a character at the cursor and advance, wrapping and scrolling.

        Write ``char`` with the given colors at the cursor position, then advance
        the cursor one column. On passing the right edge the cursor wraps to the
        next row; passing the last row scrolls the grid up by one.

        Args:
        - char (`str`): The single character to write.
        - fg (`int`): RGB565 foreground color.
        - bg (`int`): RGB565 background color.

        Returns:
        `None`: The grid and cursor are updated in place.

        """
        if self._in_bounds(self.cursor_row, self.cursor_col):
            self._cells[self.cursor_row][self.cursor_col] = Cell(char[:1], fg, bg)
        self.cursor_col += 1
        if self.cursor_col >= self.cols:
            self.cursor_col = 0
            self.newline()

    def newline(self) -> None:
        """
        Move the cursor down one row, scrolling up when past the last row.

        Returns:
        `None`: The cursor (and grid, when scrolling) is updated in place.

        """
        if self.cursor_row + 1 >= self.rows:
            self.scroll_up(1)
        else:
            self.cursor_row += 1

    def carriage_return(self) -> None:
        """
        Move the cursor to column 0 of the current row.

        Returns:
        `None`: The cursor is updated in place.

        """
        self.cursor_col = 0

    def backspace(self) -> None:
        """
        Move the cursor one column left, stopping at column 0.

        Returns:
        `None`: The cursor is updated in place (non-destructive).

        """
        if self.cursor_col > 0:
            self.cursor_col -= 1

    def tab(self, width: int = DEFAULT_TAB_WIDTH) -> None:
        """
        Advance the cursor to the next tab stop, clamped to the last column.

        Args:
        - width (`int`, optional): Tab stop width in columns. Defaults to `DEFAULT_TAB_WIDTH`.

        Returns:
        `None`: The cursor is updated in place.

        """
        stop = max(1, width)
        next_col = ((self.cursor_col // stop) + 1) * stop
        self.cursor_col = min(next_col, self.cols - 1)

    def clear(self) -> None:
        """
        Clear the whole grid to blanks and home the cursor.

        Returns:
        `None`: The grid and cursor are reset in place.

        """
        self._cells = [
            [self._blank() for _ in range(self.cols)] for _ in range(self.rows)
        ]
        self.cursor_row = 0
        self.cursor_col = 0

    def clear_line(self, row: int | None = None) -> None:
        """
        Clear a single row to blanks (the cursor row by default).

        Args:
        - row (`int | None`, optional): Row to clear. Defaults to the cursor row.

        Returns:
        `None`: The row is reset in place; out-of-range rows are ignored.

        """
        target = self.cursor_row if row is None else row
        if 0 <= target < self.rows:
            self._cells[target] = [self._blank() for _ in range(self.cols)]

    def clear_to_end_of_line(self) -> None:
        """
        Clear from the cursor column to the end of the cursor row.

        Returns:
        `None`: The affected cells are blanked in place.

        """
        for col in range(self.cursor_col, self.cols):
            self._cells[self.cursor_row][col] = self._blank()

    def clear_to_end_of_screen(self) -> None:
        """
        Clear from the cursor to the end of the grid.

        Blank the remainder of the cursor row (from the cursor column) and every
        row below it.

        Returns:
        `None`: The affected cells are blanked in place.

        """
        self.clear_to_end_of_line()
        for row in range(self.cursor_row + 1, self.rows):
            self._cells[row] = [self._blank() for _ in range(self.cols)]

    def scroll_up(self, n: int = 1) -> None:
        """
        Scroll the grid up by ``n`` rows, filling the bottom with blanks.

        The cursor stays on its current row index (which now shows later
        content). Scrolling by at least the row count clears the grid.

        Args:
        - n (`int`, optional): Number of rows to scroll up. Defaults to 1.

        Returns:
        `None`: The grid is shifted in place; non-positive ``n`` is a no-op.

        """
        if n <= 0:
            return
        if n >= self.rows:
            self._cells = [
                [self._blank() for _ in range(self.cols)] for _ in range(self.rows)
            ]
            return
        kept = self._cells[n:]
        blanks = [[self._blank() for _ in range(self.cols)] for _ in range(n)]
        self._cells = kept + blanks

    def scroll_down(self, n: int = 1) -> None:
        """
        Scroll the grid down by ``n`` rows, filling the top with blanks.

        Args:
        - n (`int`, optional): Number of rows to scroll down. Defaults to 1.

        Returns:
        `None`: The grid is shifted in place; non-positive ``n`` is a no-op.

        """
        if n <= 0:
            return
        if n >= self.rows:
            self._cells = [
                [self._blank() for _ in range(self.cols)] for _ in range(self.rows)
            ]
            return
        kept = self._cells[: self.rows - n]
        blanks = [[self._blank() for _ in range(self.cols)] for _ in range(n)]
        self._cells = blanks + kept

    def snapshot(self) -> Grid:
        """
        Return a deep, independent copy of this grid (including the cursor).

        A snapshot is used as the previous-frame baseline for :meth:`diff`;
        mutating this grid afterwards does not affect the snapshot.

        Returns:
        `Grid`: An independent copy with identical cells and cursor.

        """
        clone = Grid(self.cols, self.rows, self.default_fg, self.default_bg)
        clone._cells = [[replace(cell) for cell in row] for row in self._cells]
        clone.cursor_row = self.cursor_row
        clone.cursor_col = self.cursor_col
        return clone

    def _row_runs(self, row: int, changed: list[bool]) -> list[CellRun]:
        """
        Coalesce the changed cells of one row into color-consistent runs.

        Walk the row left to right, grouping consecutive cells flagged in
        ``changed`` that share the same foreground/background into a single run,
        breaking the run on an unchanged cell or a color change.

        Args:
        - row (`int`): Row index being coalesced.
        - changed (`list[bool]`): Per-column changed flags for the row.

        Returns:
        `list[CellRun]`: The coalesced runs for the row (left to right).

        """
        runs: list[CellRun] = []
        col = 0
        cells = self._cells[row]
        while col < self.cols:
            if not changed[col]:
                col += 1
                continue
            start = col
            fg = cells[col].fg
            bg = cells[col].bg
            chars: list[str] = []
            while (
                col < self.cols
                and changed[col]
                and (cells[col].fg == fg and cells[col].bg == bg)
            ):
                chars.append(cells[col].char)
                col += 1
            runs.append(CellRun(row, start, fg, bg, "".join(chars)))
        return runs

    def diff(self, prev: Grid) -> list[CellRun]:
        """
        Compute the draw runs needed to turn ``prev`` into this grid.

        Compare cell-by-cell against ``prev`` and emit, per row, coalesced
        :class:`CellRun` values for exactly the cells whose character or color
        changed. Grids of differing dimensions are treated as fully changed (a
        full repaint of every cell).

        Args:
        - prev (`Grid`): The previous-frame grid to diff against.

        Returns:
        `list[CellRun]`: The change runs, ordered by row then column.

        """
        if prev.rows != self.rows or prev.cols != self.cols:
            return self._all_runs()
        runs: list[CellRun] = []
        for row in range(self.rows):
            changed = [
                self._cells[row][col] != prev._cells[row][col]
                for col in range(self.cols)
            ]
            if any(changed):
                runs.extend(self._row_runs(row, changed))
        return runs

    def _all_runs(self) -> list[CellRun]:
        """
        Emit coalesced runs covering every cell of the grid.

        Returns:
        `list[CellRun]`: Runs spanning all cells, ordered by row then column.

        """
        runs: list[CellRun] = []
        all_changed = [True] * self.cols
        for row in range(self.rows):
            runs.extend(self._row_runs(row, all_changed))
        return runs

    def full_repaint(self) -> list[CellRun]:
        """
        Emit coalesced runs for every non-blank cell (a keyframe repaint).

        A cell is blank when it is a space drawn in the default color pair;
        blank cells are skipped so a cleared screen produces no runs.

        Returns:
        `list[CellRun]`: Runs covering all non-blank cells, row then column.

        """
        runs: list[CellRun] = []
        for row in range(self.rows):
            non_blank = [
                not self._is_blank(self._cells[row][col]) for col in range(self.cols)
            ]
            if any(non_blank):
                runs.extend(self._row_runs(row, non_blank))
        return runs

    def _is_blank(self, cell: Cell) -> bool:
        """
        Report whether a cell is a default-colored space.

        Args:
        - cell (`Cell`): The cell to test.

        Returns:
        `bool`: ``True`` if the cell is a blank in the default color pair.

        """
        return (
            cell.char == " "
            and cell.fg == self.default_fg
            and cell.bg == self.default_bg
        )
