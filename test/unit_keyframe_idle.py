"""
Unit test: the diff-gated keyframe transmits zero runs when the screen is idle.

**Validates: Requirements (cyd-terminal: idle serial traffic eliminated)**

The firmware link is host->device only (no reset/hello byte to watch for), so the
periodic keyframe is diff-gated rather than a blind full repaint: it paints the
session grid against the existing ``_prev`` baseline. The bridge sends one
``DRAW_CELLS`` frame per :class:`terminal.grid.CellRun` returned by that diff and
nothing otherwise, so "idle keyframe sends zero bytes" reduces to "an unchanged
grid diffs to zero runs". This asserts exactly that, plus that a real change
still produces runs (the timer is not dead).

Pure plain-python over ``terminal.grid`` only (no pydantic, no hypothesis, no
hardware), so it runs even when the full whiskerframe dependency chain is absent.
Adds ``pi/`` to ``sys.path``, prints ``PASS`` on success, exits non-zero on
failure. Run: ``uv run python test/unit_keyframe_idle.py``.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "pi"))

from terminal.grid import Grid

_FG: int = 0xFD9C
_BG: int = 0x18C5


def _grid() -> Grid:
    return Grid(cols=53, rows=30, default_fg=_FG, default_bg=_BG)


def check_idle_keyframe_diffs_empty() -> None:
    """An unchanged grid diffed against its own snapshot yields zero runs.

    This is the frame count a diff-gated keyframe sends when nothing changed.
    """
    grid = _grid()
    grid.set_cursor(5, 10)
    grid.put_char("$", _FG, _BG)
    baseline = grid.snapshot()  # the _prev the keyframe paints against
    runs = grid.diff(baseline)
    assert runs == [], f"idle keyframe would send {len(runs)} runs, expected 0"


def check_changed_keyframe_sends_runs() -> None:
    """After a real change the keyframe diff still produces runs."""
    grid = _grid()
    baseline = grid.snapshot()
    grid.set_cursor(2, 0)
    grid.put_char("X", _FG, _BG)
    runs = grid.diff(baseline)
    assert runs, "keyframe after a change should produce at least one run"


def main() -> int:
    try:
        check_idle_keyframe_diffs_empty()
        check_changed_keyframe_sends_runs()
    except AssertionError:
        import traceback

        traceback.print_exc()
        print("FAIL")
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
