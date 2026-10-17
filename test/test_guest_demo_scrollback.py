"""
Tests for guest demo responsive geometry rendering and terminal scrollback viewport navigation (Fn+Up / Fn+Down).
"""

import pytest
import os
import sys
import importlib.util
from importlib.machinery import SourceFileLoader
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "pi"))

DEMO_PATH = REPO_ROOT / "pi" / "bin" / "demo"
loader = SourceFileLoader("demo", str(DEMO_PATH))
spec = importlib.util.spec_from_loader("demo", loader)
if spec is not None and spec.loader is not None:
    demo = importlib.util.module_from_spec(spec)
    sys.modules["demo"] = demo
    loader.exec_module(demo)

from terminal.grid import Grid, Cell
from terminal.theme import load_theme
from terminal.workspaces import Workspace, WorkspaceManager
from terminal.bridge import TerminalBridge
from whiskerframe.terminal import TerminalGeometry


def test_demo_responsive_geometries(monkeypatch):
    geos = [
        (53, 30),
        (40, 20),
        (26, 15),
        (17, 10),
    ]
    for cols, rows in geos:
        monkeypatch.setattr(os, "get_terminal_size", lambda fallback=(53, 30): os.terminal_size((cols, rows)))
        res = demo.print_demo_sandbox_banner()
        assert res == 0


def test_scrollback_viewport_navigation():
    theme = load_theme(None)
    g = Grid(26, 10, theme.fg, theme.bg)
    for i in range(15):
        g._scrollback.append(([Cell(str(i % 10), theme.fg, theme.bg) for _ in range(26)], False))

    v0 = g.render_viewport(0)
    assert v0 is g or v0.cols == 26

    v5 = g.render_viewport(5)
    assert v5.cols == 26
    assert v5.rows == 10


class DummyBridgeForScroll:
    def __init__(self):
        self._theme = load_theme(None)
        self._geometry = TerminalGeometry.for_font_size(1)
        self.painted = False

    def _clear_panel(self) -> None:
        pass

    def _paint(self, grid: Grid) -> None:
        self.painted = True


def test_workspace_scroll_history():
    bridge = DummyBridgeForScroll()
    wm = WorkspaceManager(bridge, user="root")
    ws = wm.create_workspace(ws_id=1, name="1", user="root", initial_fd=-1, initial_pid=0)
    ws._mock_alive = True
    ws.grid._scrollback.append(([Cell("A", bridge._theme.fg, bridge._theme.bg) for _ in range(53)], False))

    assert ws.scroll_offset == 0
    ws.scroll_up_history()
    assert ws.scroll_offset == 1
    ws.scroll_up_history()
    assert ws.scroll_offset == 1

    ws.scroll_down_history()
    assert ws.scroll_offset == 0
    ws.scroll_down_history()
    assert ws.scroll_offset == 0
