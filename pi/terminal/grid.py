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
        status_bar_rows: int = 0,
        status_bar_position: str = "top",
    ) -> None:
        """
        Initialize a blank grid filled with the default color pair.

        Args:
        - cols (`int`): Number of columns (must be >= 1).
        - rows (`int`): Number of rows (must be >= 1).
        - default_fg (`int`): RGB565 foreground for blank cells.
        - default_bg (`int`): RGB565 background for blank cells.
        - status_bar_rows (`int`, optional): Number of reserved status bar rows. Defaults to 0.
        - status_bar_position (`str`, optional): "top" or "bottom". Defaults to "top".

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
        self.status_bar_rows = max(0, status_bar_rows)
        self.status_bar_position = status_bar_position.lower()

        if self.status_bar_rows > 0:
            if self.status_bar_position == "bottom":
                self.viewport_top = 0
                self.viewport_bottom = max(0, rows - 1 - self.status_bar_rows)
            else:
                self.viewport_top = min(rows - 1, self.status_bar_rows)
                self.viewport_bottom = rows - 1
        else:
            self.viewport_top = 0
            self.viewport_bottom = rows - 1

        self.cursor_row = self.viewport_top
        self.cursor_col = 0
        self.dirty: bool = False
        self._wrapped: list[bool] = [False] * rows
        self._scrollback: list[tuple[list[Cell], bool]] = []
        self.max_scrollback: int = 200
        self._cells: list[list[Cell]] = [
            [self._blank() for _ in range(cols)] for _ in range(rows)
        ]

    @property
    def scrollback(self) -> list[tuple[list[Cell], bool]]:
        """Return the scrollback buffer lines (read-only snapshot)."""
        return list(self._scrollback)

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
        Report whether ``(row, col)`` lies inside the grid viewport.

        Args:
        - row (`int`): Row index.
        - col (`int`): Column index.

        Returns:
        `bool`: ``True`` if the position is addressable within the viewport.

        """
        return self.viewport_top <= row <= self.viewport_bottom and 0 <= col < self.cols

    def set_cursor(self, row: int, col: int) -> None:
        """
        Move the cursor to ``(row, col)``, clamped to the grid viewport bounds.

        Args:
        - row (`int`): Target row (clamped to viewport bounds).
        - col (`int`): Target column (clamped to ``[0, cols - 1]``).

        Returns:
        `None`: The cursor is updated in place.

        """
        self.cursor_row = max(self.viewport_top, min(row, self.viewport_bottom))
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
            self._wrapped[self.cursor_row] = True
            self.cursor_col = 0
            self.newline()

    def newline(self) -> None:
        """
        Move the cursor down one row, scrolling up when past the viewport bottom.

        Returns:
        `None`: The cursor (and grid, when scrolling) is updated in place.

        """
        if self.cursor_row + 1 > self.viewport_bottom:
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
        Clear the viewport to blanks and home the cursor, leaving reserved rows untouched.

        Returns:
        `None`: The viewport and cursor are reset in place.

        """
        for r in range(self.viewport_top, self.viewport_bottom + 1):
            self._cells[r] = [self._blank() for _ in range(self.cols)]
            self._wrapped[r] = False
        self.cursor_row = self.viewport_top
        self.cursor_col = 0
        self.dirty = True

    def clear_line(self, row: int | None = None) -> None:
        """
        Clear a single viewport row to blanks (the cursor row by default).

        Args:
        - row (`int | None`, optional): Row to clear. Defaults to the cursor row.

        Returns:
        `None`: The row is reset in place; out-of-range rows are ignored.

        """
        target = self.cursor_row if row is None else row
        if self.viewport_top <= target <= self.viewport_bottom:
            self._cells[target] = [self._blank() for _ in range(self.cols)]
            self._wrapped[target] = False

    def clear_to_end_of_line(self) -> None:
        """
        Clear from the cursor column to the end of the cursor row.

        Returns:
        `None`: The affected cells are blanked in place.

        """
        for col in range(self.cursor_col, self.cols):
            self._cells[self.cursor_row][col] = self._blank()
        self._wrapped[self.cursor_row] = False

    def clear_to_end_of_screen(self) -> None:
        """
        Clear from the cursor to the end of the viewport.

        Blank the remainder of the cursor row (from the cursor column) and every
        row below it within the viewport.

        Returns:
        `None`: The affected cells are blanked in place.

        """
        self.clear_to_end_of_line()
        for row in range(self.cursor_row + 1, self.viewport_bottom + 1):
            self._cells[row] = [self._blank() for _ in range(self.cols)]
            self._wrapped[row] = False

    def scroll_up(self, n: int = 1) -> None:
        """
        Scroll the viewport up by ``n`` rows, filling the bottom with blanks.

        The cursor stays on its current row index. Reserved status bar rows are untouched.

        Args:
        - n (`int`, optional): Number of rows to scroll up. Defaults to 1.

        Returns:
        `None`: The viewport is shifted in place; non-positive ``n`` is a no-op.

        """
        n = max(0, n)
        if n <= 0:
            return
        region_h = self.viewport_bottom - self.viewport_top + 1
        if n >= region_h:
            for r in range(self.viewport_top, self.viewport_bottom + 1):
                self._scrollback.append((self._cells[r], self._wrapped[r]))
            if len(self._scrollback) > self.max_scrollback:
                self._scrollback = self._scrollback[-self.max_scrollback:]
            for r in range(self.viewport_top, self.viewport_bottom + 1):
                self._cells[r] = [self._blank() for _ in range(self.cols)]
                self._wrapped[r] = False
            return
        for r in range(self.viewport_top, self.viewport_top + n):
            self._scrollback.append((self._cells[r], self._wrapped[r]))
        if len(self._scrollback) > self.max_scrollback:
            self._scrollback = self._scrollback[-self.max_scrollback:]

        for r in range(self.viewport_top, self.viewport_bottom + 1 - n):
            self._cells[r] = self._cells[r + n]
            self._wrapped[r] = self._wrapped[r + n]
        for r in range(self.viewport_bottom + 1 - n, self.viewport_bottom + 1):
            self._cells[r] = [self._blank() for _ in range(self.cols)]
            self._wrapped[r] = False

    def scroll_down(self, n: int = 1) -> None:
        """
        Scroll the viewport down by ``n`` rows, filling the top with blanks.

        Args:
        - n (`int`, optional): Number of rows to scroll down. Defaults to 1.

        Returns:
        `None`: The viewport is shifted in place; non-positive ``n`` is a no-op.

        """
        n = max(0, n)
        if n <= 0:
            return
        region_h = self.viewport_bottom - self.viewport_top + 1
        if n >= region_h:
            for r in range(self.viewport_top, self.viewport_bottom + 1):
                self._cells[r] = [self._blank() for _ in range(self.cols)]
                self._wrapped[r] = False
            return
        kept = self._cells[self.viewport_top : self.viewport_bottom + 1 - n]
        kept_wrapped = self._wrapped[self.viewport_top : self.viewport_bottom + 1 - n]
        blanks = [[self._blank() for _ in range(self.cols)] for _ in range(n)]
        blanks_wrapped = [False] * n
        self._cells[self.viewport_top : self.viewport_bottom + 1] = blanks + kept
        self._wrapped[self.viewport_top : self.viewport_bottom + 1] = blanks_wrapped + kept_wrapped

    def snapshot(self) -> Grid:
        """
        Return a deep, independent copy of this grid (including the cursor).

        A snapshot is used as the previous-frame baseline for :meth:`diff`;
        mutating this grid afterwards does not affect the snapshot.

        Returns:
        `Grid`: An independent copy with identical cells and cursor.

        """
        clone = Grid(
            self.cols,
            self.rows,
            self.default_fg,
            self.default_bg,
            status_bar_rows=self.status_bar_rows,
            status_bar_position=self.status_bar_position,
        )
        clone._cells = [[replace(cell) for cell in row] for row in self._cells]
        clone._wrapped = list(self._wrapped)
        clone._scrollback = [(list(row), wrap) for row, wrap in self._scrollback]
        clone.max_scrollback = self.max_scrollback
        clone.cursor_row = self.cursor_row
        clone.cursor_col = self.cursor_col
        clone.dirty = self.dirty
        return clone

    def render_with_cursor(self, cursor_fg: int, cursor_bg: int) -> Grid:
        """
        Return a copy of the grid with the cursor position highlighted.

        Args:
        - cursor_fg (`int`): RGB565 foreground for the cursor cell.
        - cursor_bg (`int`): RGB565 background for the cursor cell.

        Returns:
        `Grid`: A grid copy with the cursor position highlighted.

        """
        clone = self.snapshot()
        if clone._in_bounds(clone.cursor_row, clone.cursor_col):
            cell = clone.cell_at(clone.cursor_row, clone.cursor_col)
            clone._cells[clone.cursor_row][clone.cursor_col] = Cell(
                char=cell.char,
                fg=cursor_fg,
                bg=cursor_bg,
            )
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
        if self.dirty or prev.rows != self.rows or prev.cols != self.cols:
            self.dirty = False
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

    def reflow(self, new_cols: int, new_rows: int) -> Grid:
        """
        Reflow text and cursor into a new geometry (cols x rows).

        Reconstruct logical lines from scrollback and active screen rows,
        respecting soft-wrapped line boundaries. Re-chunk the logical lines into
        lines of width ``new_cols``, anchor the visible viewport to the bottom
        of the reflowed content so the active prompt is preserved, and store any
        overflowing upper rows into the new grid's scrollback.

        Args:
        - new_cols (`int`): Target column count (>= 1).
        - new_rows (`int`): Target row count (>= 1).

        Raises:
        - `ValueError`: If ``new_cols`` or ``new_rows`` is less than 1.

        Returns:
        `Grid`: Newly allocated grid with reflowed content and clamped cursor.

        """
        if new_cols < 1 or new_rows < 1:
            msg = f"grid dimensions must be >= 1, got cols={new_cols}, rows={new_rows}"
            raise ValueError(msg)

        new_grid = Grid(
            new_cols,
            new_rows,
            self.default_fg,
            self.default_bg,
            status_bar_rows=self.status_bar_rows,
            status_bar_position=self.status_bar_position,
        )
        new_grid.dirty = True
        new_grid.max_scrollback = self.max_scrollback

        all_rows: list[tuple[list[Cell], bool]] = list(self._scrollback)
        for r in range(self.rows):
            all_rows.append((self._cells[r], self._wrapped[r]))

        # Keep rows up to max(cursor_row, last_non_blank_row)
        last_active_row = self.cursor_row
        for r in range(self.rows - 1, -1, -1):
            if any(cell.char != " " or cell.bg != self.default_bg for cell in self._cells[r]):
                last_active_row = max(last_active_row, r)
                break

        n_scroll = len(self._scrollback)
        relevant_rows = all_rows[: n_scroll + last_active_row + 1]

        logical_lines: list[list[Cell]] = []
        target_cursor_r = n_scroll + self.cursor_row
        target_cursor_c = self.cursor_col

        cur_logical_line: list[Cell] = []
        cursor_found = False
        cursor_log_line = 0
        cursor_log_offset = 0

        for idx, (cells, wrapped) in enumerate(relevant_rows):
            if idx == target_cursor_r:
                cursor_log_line = len(logical_lines)
                cursor_log_offset = len(cur_logical_line) + target_cursor_c
                cursor_found = True

            if not wrapped:
                last_nb = len(cells)
                while (
                    last_nb > 0
                    and cells[last_nb - 1].char == " "
                    and cells[last_nb - 1].bg == self.default_bg
                ):
                    last_nb -= 1
                cur_logical_line.extend(cells[:last_nb])
                logical_lines.append(cur_logical_line)
                cur_logical_line = []
            else:
                cur_logical_line.extend(cells)

        if cur_logical_line or not logical_lines:
            logical_lines.append(cur_logical_line)

        if not cursor_found:
            cursor_log_line = len(logical_lines) - 1
            cursor_log_offset = len(logical_lines[-1])

        new_all_rows: list[tuple[list[Cell], bool]] = []
        new_cursor_row_global = 0
        new_cursor_col = 0

        for l_idx, line in enumerate(logical_lines):
            if not line:
                row_cells = [new_grid._blank() for _ in range(new_cols)]
                if l_idx == cursor_log_line:
                    new_cursor_row_global = len(new_all_rows)
                    new_cursor_col = 0
                new_all_rows.append((row_cells, False))
                continue

            cursor_placed = False
            offset = 0
            while offset < len(line):
                chunk = line[offset : offset + new_cols]
                is_soft_wrap = (offset + new_cols) < len(line)
                row_cells = list(chunk)
                if len(row_cells) < new_cols:
                    row_cells.extend(
                        [new_grid._blank() for _ in range(new_cols - len(row_cells))]
                    )

                if (
                    not cursor_placed
                    and l_idx == cursor_log_line
                    and offset <= cursor_log_offset < offset + new_cols
                ):
                    new_cursor_row_global = len(new_all_rows)
                    new_cursor_col = cursor_log_offset - offset
                    cursor_placed = True

                new_all_rows.append((row_cells, is_soft_wrap))
                offset += new_cols

            if not cursor_placed and l_idx == cursor_log_line:
                new_cursor_row_global = len(new_all_rows) - 1
                new_cursor_col = min(
                    new_cols - 1,
                    max(0, cursor_log_offset - (offset - new_cols)),
                )

        total_new_rows = len(new_all_rows)
        if total_new_rows <= new_rows:
            new_grid._scrollback = []
            for r in range(total_new_rows):
                new_grid._cells[r] = new_all_rows[r][0]
                new_grid._wrapped[r] = new_all_rows[r][1]
            for r in range(total_new_rows, new_rows):
                new_grid._cells[r] = [new_grid._blank() for _ in range(new_cols)]
                new_grid._wrapped[r] = False
            new_grid.cursor_row = min(new_rows - 1, new_cursor_row_global)
            new_grid.cursor_col = min(new_cols - 1, new_cursor_col)
        else:
            scrollback_count = total_new_rows - new_rows
            raw_scrollback = new_all_rows[:scrollback_count]
            if len(raw_scrollback) > new_grid.max_scrollback:
                raw_scrollback = raw_scrollback[-new_grid.max_scrollback :]
            new_grid._scrollback = raw_scrollback
            visible_rows = new_all_rows[scrollback_count:]
            for r in range(new_rows):
                new_grid._cells[r] = visible_rows[r][0]
                new_grid._wrapped[r] = visible_rows[r][1]
            new_grid.cursor_row = max(
                0, min(new_rows - 1, new_cursor_row_global - scrollback_count)
            )
            new_grid.cursor_col = min(new_cols - 1, new_cursor_col)

        return new_grid

    def render_viewport(self, scroll_offset: int = 0) -> Grid:
        """
        Return a temporary Grid instance rendering the viewport with scroll_offset applied.
        """
        if scroll_offset <= 0 or not self._scrollback:
            return self

        clone = Grid(
            self.cols,
            self.rows,
            self.default_fg,
            self.default_bg,
            status_bar_rows=self.status_bar_rows,
            status_bar_position=self.status_bar_position,
        )
        clone._scrollback = list(self._scrollback)
        clone._cells = [list(row) for row in self._cells]
        clone._wrapped = list(self._wrapped)
        clone.cursor_row = self.cursor_row
        clone.cursor_col = self.cursor_col

        vp_top = self.viewport_top
        vp_bot = self.viewport_bottom
        vp_height = vp_bot - vp_top + 1

        all_lines = list(self._scrollback) + [(self._cells[r], self._wrapped[r]) for r in range(self.rows)]
        total_lines = len(all_lines)

        base_start = len(self._scrollback) + vp_top
        max_offset = len(self._scrollback)
        offset = max(0, min(max_offset, scroll_offset))
        start_idx = base_start - offset

        for r in range(vp_height):
            idx = start_idx + r
            target_row = vp_top + r
            if 0 <= idx < total_lines:
                cells_tuple, wrapped_val = all_lines[idx]
                clone._cells[target_row] = [Cell(c.char, c.fg, c.bg) for c in cells_tuple]
                clone._wrapped[target_row] = wrapped_val
            else:
                clone._cells[target_row] = [clone._blank() for _ in range(clone.cols)]
                clone._wrapped[target_row] = False

        return clone
