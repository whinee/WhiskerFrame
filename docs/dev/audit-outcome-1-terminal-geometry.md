# Outcome 1 Audit: Terminal Geometry, Reflow & Resize Resiliency

**Auditor:** Dispatched Worker (`task_64409eb3b2f2`, `ctx_f8b3a2076cd1`)  
**Date:** 2026-10-16  
**Target Specification:** Master Prompt #2, Outcome 1 ("Terminal geometry: Fix resize/geometry changes so all terminal text is correctly reflowed and redrawn without missing text, stale cells, clipping, or corruption.")  
**System Target:** Raspberry Pi Zero 2 W (`pi-midori-neko`, 416MB RAM) + ESP32 CYD (ILI9341 320x240 LCD over USB-UART)  
**Overall Verdict:** **FAIL** (8 critical defects identified, analyzed, and empirically proven)

---

## 1. Executive Summary

An exhaustive code audit and empirical verification of the terminal geometry and resize subsystem was conducted across `whiskerframe/terminal.py`, `pi/terminal/bridge.py`, `pi/terminal/workspaces.py`, `pi/terminal/grid.py`, `pi/terminal/status_bar.py`, and `pi/terminal/vt.py`.

While the multi-geometry font metrics derivation (`whiskerframe.metrics.FONT_METRICS`, 53x30, 40x20, 26x15, 17x10) and basic key chord detection (`Fn+Backspace` / `0x8B`) function without crashes, **terminal resize and geometry transitions fail all core requirements of Outcome 1**:
1. **Zero Text Reflow:** Resizing to smaller columns unconditionally truncates text past `new_cols - 1` rather than wrapping onto new lines.
2. **Active Viewport Truncation:** Resizing to fewer rows truncates from the top, permanently discarding the bottom rows containing the active prompt, user command input, and latest output.
3. **Copy-Time Grid Scroll Corruption:** Copying cells in `_copy_cells` invokes `put_char()`, which auto-scrolls the entire new grid up by one row when writing to the bottom-right cell `(rows-1, cols-1)`.
4. **Complete Output Annihilation in Non-Workspace Mode:** `bridge._rebuild_geometry()` instantiates a fresh blank grid, erasing 100% of terminal text.
5. **In-Flight Emulator State Loss:** `VTEmulator` is destroyed and re-instantiated on resize, discarding parser state, active SGR colors, and modifier attributes.
6. **Status Bar Layer Collision:** The status bar writes directly into terminal grid rows without reservation in `TIOCSWINSZ`, causing shell scrolls to push telemetry into terminal history.
7. **No Scrollback / History Retention:** The grid is strictly a visible matrix; lines scrolled or resized out of view are permanently destroyed.
8. **Gutter Debris on Hardware Display:** `workspaces.rebuild_geometry()` fails to clear the hardware display panel (`_clear_panel()`), leaving stale pixel debris in right gutters (up to 14px on Font 3).

---

## 2. Architecture & Geometry Mapping

The cyberdeck employs an ESP32 CYD running custom firmware driving a 320x240 ILI9341 LCD panel in landscape mode. Four fixed-cell typography layouts are supported:

| Font Selector | Cell Size ($W \times H$) | Grid Dimensions ($C \times R$) | Rendered Extent ($W \times H$) | Unused Gutter ($X \times Y$) |
|---|---|---|---|---|
| **Font 1** (Default) | $6 \times 8$ px | $53 \times 30$ | $318 \times 240$ px | $2 \times 0$ px |
| **Font 5** (Comic Mono) | $8 \times 12$ px | $40 \times 20$ | $320 \times 240$ px | $0 \times 0$ px |
| **Font 2** (Readable) | $12 \times 16$ px | $26 \times 15$ | $312 \times 240$ px | $8 \times 0$ px |
| **Font 3** (Presentation) | $18 \times 24$ px | $17 \times 10$ | $306 \times 240$ px | $14 \times 0$ px |

The runtime cycles through these sizes sequentially upon receiving `Fn+Backspace` (`0x8B`):
```text
53x30 (Font 1) ──▶ 40x20 (Font 5) ──▶ 26x15 (Font 2) ──▶ 17x10 (Font 3) ──▶ 53x30 (Font 1)
```

---

## 3. Detailed Findings & Empirical Proof

### Finding 1: Zero Reflow & Silent Column Truncation (DEFECT-GEO-01)
- **File:** `pi/terminal/workspaces.py:417-426`
- **Mechanism:**
  ```python
  def _copy_cells(self, old_grid: Grid, new_grid: Grid) -> None:
      min_r = min(old_grid.rows, new_grid.rows)
      min_c = min(old_grid.cols, new_grid.cols)
      for r in range(min_r):
          for c in range(min_c):
              cell = old_grid.cell_at(r, c)
              if cell.char != " " or cell.bg != old_grid.default_bg:
                  new_grid.set_cursor(r, c)
                  new_grid.put_char(cell.char, cell.fg, cell.bg)
  ```
- **Observed Behavior:** When switching from Font 1 (53 cols) to Font 2 (26 cols), columns 26 through 52 are ignored. Any text exceeding 26 characters on a line is permanently discarded. Lines do not soft-wrap or reflow into subsequent rows.
- **Empirical Test:** A 53-character test line `"The quick brown fox jumps over the lazy dog 123456789"` was placed on row 0. After resizing to 26x15, row 0 contained only `"The quick brown fox jumps "`. The remaining 27 characters were completely lost, and row 1 remained entirely blank.

### Finding 2: Bottom-Row Active Screen Truncation on Down-Sizing (DEFECT-GEO-02)
- **File:** `pi/terminal/workspaces.py:418-420`
- **Mechanism:** `min_r = min(old_grid.rows, new_grid.rows)`. Cells are copied starting strictly from row 0 downwards.
- **Observed Behavior:** In a standard interactive shell session, the active command line, bash prompt (`n~ $`), and current output reside at the bottom of the terminal window (e.g. row 29 in a 30-row terminal). When switching from 30 rows (Font 1) to 15 rows (Font 2) or 10 rows (Font 3), only the top rows 0..14 or 0..9 are copied. The active working prompt is truncated and hidden from the user.
- **Empirical Test:** Placed `"user@deck:~$ active_command"` at row 29 of a 53x30 grid. After downsizing to 26x15, the prompt was absent from all 15 rows of the new grid.

### Finding 3: Copy-Time Scrolling Corruption of Entire Grid (DEFECT-GEO-03)
- **File:** `pi/terminal/workspaces.py:424-425` and `pi/terminal/grid.py:201-215`
- **Mechanism:**
  When `new_grid.put_char()` writes a character into `(row, col)`, it advances `cursor_col`.
  ```python
  # pi/terminal/grid.py:201-204
  self.cursor_col += 1
  if self.cursor_col >= self.cols:
      self.cursor_col = 0
      self.newline()
  ```
  If a character is written to the last column (`col == new_grid.cols - 1`), `newline()` is triggered. If `row == new_grid.rows - 1`, `newline()` executes `self.scroll_up(1)`.
- **Observed Behavior:** If the old grid contains non-blank characters on its final row extending to the right edge, copying the final cell triggers an in-situ `scroll_up(1)` on `new_grid` during the copy loop. This shifts all previously copied rows up by 1, discards row 0, and misaligns every line in the terminal.
- **Empirical Test:** Initialized row 0 with `"A"` at col 0, and row 14 with `"Z"` at col 25 (last cell). Ran `_copy_cells`. Row 0 col 0 was shifted off screen to blank space, and `"Z"` was displaced to row 13 col 25.

### Finding 4: Total Output Wipe in Non-Workspace Mode (DEFECT-GEO-04)
- **File:** `pi/terminal/bridge.py:723-730`
- **Mechanism:**
  ```python
  grid = Grid(
      self._geometry.cols,
      self._geometry.rows,
      self._theme.fg,
      self._theme.bg,
  )
  grid.dirty = True
  return grid
  ```
- **Observed Behavior:** When workspaces are disabled or during standalone bridge sessions, `_rebuild_geometry()` creates an unpopulated, empty grid. All existing terminal output is erased.

### Finding 5: In-Flight VT Parser and SGR Attribute Obliteration (DEFECT-GEO-05)
- **File:** `pi/terminal/bridge.py:1091`, `pi/terminal/workspaces.py:443`
- **Mechanism:**
  ```python
  ws.emulator = VTEmulator(new_grid, theme)
  ```
- **Observed Behavior:** `VTEmulator` is completely re-instantiated. Any active SGR text styles (foreground color, background color, bold, underline) set by shell utilities (e.g. colored grep, syntax highlighting, htop) are reset to default theme colors. Any multi-byte escape sequence split across a resize chord is corrupted.
- **Empirical Test:** Fed `\x1b[31;1mHello` (bright red) into emulator. Prior to resize, `emulator.fg` was `64333` (red). After resize, `new_emu.fg` reset to `64924` (theme default pink).

### Finding 6: Status Bar Layer Collision and Scrolling Corruption (DEFECT-GEO-06)
- **File:** `pi/terminal/status_bar.py:313-320`, `pi/terminal/bridge.py:243-269`
- **Mechanism:**
  `TerminalGeometry` allocates all 240 pixels to the terminal grid (`rows = 240 // cell_h`). `TIOCSWINSZ` advertises the full row count (30, 20, 15, or 10) to the Linux kernel and PTY slave. However, `StatusBar.render_to_grid()` mutates row 0 directly.
- **Observed Behavior:**
  1. The shell believes it owns row 0 and writes terminal text directly over the status bar.
  2. When the terminal scrolls up, the status bar contents are scrolled into terminal history as ordinary text.
  3. When telemetry updates, the status bar overwrites whatever shell output was on row 0.
- **Empirical Test:** Rendered status bar to row 0. Fed 32 lines of text into the emulator. The status bar was scrolled off, and row 0 was overwritten by `"line 2"`.

### Finding 7: Lack of Scrollback History Buffer (DEFECT-GEO-07)
- **File:** `pi/terminal/grid.py:122`
- **Mechanism:** `Grid` contains only `self._cells: list[list[Cell]]` matching visible `cols x rows`.
- **Observed Behavior:** Without a backing scrollback buffer, any line pushed off screen during resize (downsizing rows or wrapping wide lines) is permanently lost and cannot be restored when resizing back to larger geometry.

### Finding 8: Gutter Clearing and Hardware Invalidation Asymmetry (DEFECT-GEO-08)
- **File:** `pi/terminal/workspaces.py:444` (`restore_screen`) vs `pi/terminal/bridge.py:717` (`_clear_panel`)
- **Mechanism:**
  `bridge._rebuild_geometry()` calls `self._clear_panel()`, sending a full `DrawRect(0, 0, 320, 240, theme.bg)` over serial. In contrast, `workspaces.rebuild_geometry()` calls `restore_screen()`, which only sets `_prev = None` and renders active cell runs.
- **Observed Behavior:**
  Because cell runs only cover the active grid width ($cols \times cell\_w$), changing from Font 1 (318px, 2px gutter) to Font 2 (312px, 8px gutter) or Font 3 (306px, 14px gutter) leaves stale characters visible in the 8px or 14px right margin on physical hardware.

---

## 4. Preservation Constraints

Any implementation addressing Outcome 1 must adhere strictly to established architectural invariants:
1. **Pi Zero 2 W Memory Ceiling (~416 MB RAM):** Avoid heavyweight terminal libraries (`prompt_toolkit`, curses, xterm.js). Keep scrollback buffers bounded (e.g., maximum 100-200 lines per workspace, <200 KB RAM total across all 4 workspaces).
2. **Fixed Panel Dimensions:** 320x240 pixels, RGB565 big-endian serialization over USB-UART (CH340 at 115200 baud).
3. **Firmware Opcode Contracts:** Preserve wire opcodes `0x01` (DRAW_TEXT), `0x02` (DRAW_RECT), `0x03` (DRAW_CELLS), `0x04` (SCROLL), `0x05` (DRAW_IMAGE), `0x06` (SLEEP).
4. **Field-Robustness:** Mutating operations in `Grid` and `VTEmulator` must be total; out-of-bounds indices and malformed escape sequences must never raise uncaught exceptions.

---

## 5. Remediation Plan & Implementation Blueprint

To achieve a **PASS** on Outcome 1, the following concrete modifications are required:

1. **Implement Reflowing Text Buffer with Bounded Scrollback:**
   - Extend `Grid` or introduce a `TerminalBuffer` maintaining a structured sequence of logical lines (runs of characters with attributes).
   - On geometry change $(cols_{old}, rows_{old}) \to (cols_{new}, rows_{new})$, reflow the logical lines into lines of length $\le cols_{new}$, preserving explicit hard line breaks (`\n`) vs soft-wrapped lines.
   - Anchor the visible viewport to the bottom of the buffer so the active prompt and cursor remain in view.

2. **Direct Memory Copy in `_copy_cells` / Grid Repopulation:**
   - Directly populate `new_grid._cells[r][c] = cell` without invoking `put_char()`, completely eliminating spurious `scroll_up()` side-effects.

3. **Status Bar Region Decoupling (Coordination with Outcome 2):**
   - Reserve 1 row (or explicit pixel band) exclusively for the status bar.
   - Subtract reserved status rows from `TerminalGeometry.rows` before advertising window size via `_tiocswinsz` to the PTY, ensuring the shell never writes into or scrolls the status bar.

4. **Preserve VTEmulator Parser & Color State:**
   - Migrate `fg`, `bg`, and active attributes when recreating or resizing `VTEmulator`.

5. **Mandatory Hardware Panel Clearing on Workspace Resize:**
   - Ensure `workspaces.rebuild_geometry()` invokes `self.bridge._clear_panel()` to scrub gutters on physical hardware.

6. **Dedicated Test Suite:**
   - Author comprehensive regression and property tests in `test/test_terminal_geometry_reflow.py` validating wrapping, down-sizing, prompt retention, and gutter clearing.

---
*Report produced and durably recorded at `docs/dev/audit-outcome-1-terminal-geometry.md`.*
