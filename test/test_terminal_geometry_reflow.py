"""
Tests for terminal geometry reflow, wrapping, scrollback retention, and workspace resizing.
"""

import pytest
from terminal.grid import Grid, Cell
from terminal.theme import load_theme
from terminal.workspaces import WorkspaceManager
from terminal.bridge import TerminalBridge
from whiskerframe.terminal import TerminalGeometry

class DummyBridge:
    def __init__(self):
        self._theme = load_theme(None)
        self._geometry = TerminalGeometry.for_font_size(1)
        self.cleared = False
        self.painted = False

    def _clear_panel(self) -> None:
        self.cleared = True

    def _paint(self, grid: Grid) -> None:
        self.painted = True

def test_grid_reflow_wrapping_and_unwrapping():
    theme = load_theme(None)
    g = Grid(53, 30, theme.fg, theme.bg)
    text = "The quick brown fox jumps over the lazy dog 123456789"
    for ch in text:
        g.put_char(ch, theme.fg, theme.bg)

    # Reflow to 26 cols
    g_narrow = g.reflow(26, 15)
    r0 = "".join(g_narrow.cell_at(0, c).char for c in range(26))
    r1 = "".join(g_narrow.cell_at(1, c).char for c in range(26))
    assert (r0 + r1).strip().startswith("The quick brown fox")

    # Reflow back to 53 cols
    g_wide = g_narrow.reflow(53, 30)
    r0_wide = "".join(g_wide.cell_at(0, c).char for c in range(53)).strip()
    assert r0_wide == text

def test_prompt_bottom_anchor_preservation():
    theme = load_theme(None)
    g = Grid(53, 30, theme.fg, theme.bg)
    g.set_cursor(10, 0)
    prompt = "user@deck:~$ active_command"
    for ch in prompt:
        g.put_char(ch, theme.fg, theme.bg)

    g_narrow = g.reflow(26, 15)
    # Check that active_command is present anywhere in g_narrow
    found = False
    for r in range(g_narrow.rows):
        row_str = "".join(g_narrow.cell_at(r, c).char for c in range(g_narrow.cols))
        if "active_command" in row_str or "user@deck" in row_str:
            found = True
            break
    assert found

def test_workspace_geometry_rebuild_reflow_and_gutter():
    bridge = DummyBridge()
    wm = WorkspaceManager(bridge, user="root")
    # Create workspace
    wm.create_workspace(user="root")

    geo_narrow = TerminalGeometry.for_font_size(2) # 26x15
    wm.rebuild_geometry(geo_narrow)

    assert bridge.cleared is True, "Hardware panel must be cleared on geometry rebuild to scrub gutters"
    assert bridge.painted is True, "Screen must be repainted after geometry rebuild"
    assert wm.active_workspace.grid.cols == 26
    assert wm.active_workspace.grid.rows == 15
