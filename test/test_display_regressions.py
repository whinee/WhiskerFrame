#!/usr/bin/env python3
"""
Regression test suite for WhiskerFrame display subsystems.

Covers:
1. Reboot and shutdown splash rendering order ('brb :3' vs 'bai baiii!') and
   display shutdown synchronization delay (time.sleep(0.15)) in pi/bin/goodbye_hook.
2. TERM=xterm environment configuration for child shell sessions and guest demos.
3. Smallest-font (53x30) dirty-cell refresh and stale-character corruption across
   screen clearing (ANSI ED 2 / ED 3) and geometry switching (panel clears & gutter wipes).
"""

from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import unittest
from importlib.machinery import SourceFileLoader
from pathlib import Path
from unittest.mock import MagicMock, call, patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "pi"))

# Dynamically import pi/bin/goodbye_hook
_HOOK_PATH = REPO_ROOT / "pi/bin/goodbye_hook"
_hook_loader = SourceFileLoader("goodbye_hook_regressions", str(_HOOK_PATH))
_hook_spec = importlib.util.spec_from_loader("goodbye_hook_regressions", _hook_loader)
if _hook_spec is None:
    raise ImportError(f"Cannot load goodbye_hook from {_HOOK_PATH}")
goodbye_hook = importlib.util.module_from_spec(_hook_spec)
_hook_loader.exec_module(goodbye_hook)

from terminal.bridge import BridgeConfig, TerminalBridge  # noqa: E402
from terminal.grid import Grid  # noqa: E402
from terminal.theme import load_theme  # noqa: E402
from terminal.vt import VTEmulator  # noqa: E402

from whiskerframe.models import DrawRect, DrawText  # noqa: E402
from whiskerframe.protocol import decode  # noqa: E402
from whiskerframe.preview import PreviewRenderer  # noqa: E402
from whiskerframe.terminal import (  # noqa: E402
    DISPLAY_HEIGHT,
    DISPLAY_WIDTH,
    DisplaySleep,
    DrawImage,
    TerminalGeometry,
    DrawCells,
)


class TestGoodbyeHookRegressions(unittest.TestCase):
    """
    Test suite for splash rendering order and shutdown sync in goodbye_hook.

    Validates:
    - Background clear (DrawRect) renders first.
    - Subtitle text (DrawText) renders second, BEFORE heavy 128x128 image chunks,
      guaranteeing immediate operator feedback ('brb :3' on reboot, 'bai baiii!' on shutdown).
    - Image chunks stream third.
    - Shutdown performs black wipe and DisplaySleep followed by 0.15s coprocessor sync delay
      before port closure.
    - Reboot performs hold sleep without black wipe, DisplaySleep, or shutdown sync delay.
    """

    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self.tmp_dir = Path(self._temp_dir.name)
        self.valid_blob_path = self.tmp_dir / "valid_128x128.rgb565"
        self.valid_bytes = bytes([0x18, 0xC5] * (128 * 128))
        self.valid_blob_path.write_bytes(self.valid_bytes)

    def tearDown(self) -> None:
        self._temp_dir.cleanup()

    @patch("time.sleep")
    def test_reboot_splash_rendering_order_and_text(
        self,
        mock_sleep: MagicMock,
    ) -> None:
        """Reboot sequence renders background -> 'brb :3' text -> image chunks."""
        mock_ser = MagicMock()
        written_frames: list[bytes] = []
        mock_ser.write.side_effect = written_frames.append

        with patch("serial.Serial", return_value=mock_ser):
            goodbye_hook.send_goodbye(
                port="/dev/test_reboot",
                rgb565_path=self.valid_blob_path,
                mode="reboot",
                hold_s=1.0,
            )

        # In reboot mode, only the hold sleep is called (no shutdown sync sleep)
        mock_sleep.assert_called_once_with(1.0)
        mock_ser.close.assert_called_once()

        self.assertGreaterEqual(len(written_frames), 3)

        # 1. Background clear
        cmd_0 = decode(written_frames[0])
        self.assertIsInstance(cmd_0, DrawRect)
        self.assertEqual(cmd_0.x, 0)
        self.assertEqual(cmd_0.y, 0)
        self.assertEqual(cmd_0.w, DISPLAY_WIDTH)
        self.assertEqual(cmd_0.h, DISPLAY_HEIGHT)
        self.assertEqual(cmd_0.color, goodbye_hook._THEME_BG)
        self.assertTrue(cmd_0.filled)

        # 2. Crisp subtitle text 'brb :3' renders immediately after background
        cmd_1 = decode(written_frames[1])
        self.assertIsInstance(cmd_1, DrawText)
        self.assertEqual(cmd_1.text, "brb :3")
        self.assertEqual(cmd_1.x, 160)
        self.assertEqual(cmd_1.y, 184)
        self.assertEqual(cmd_1.anchor, "mm")
        self.assertEqual(cmd_1.color, goodbye_hook._TEXT_COLOR)
        self.assertEqual(cmd_1.bg_color, goodbye_hook._THEME_BG)

        # 3. Image chunks stream after text
        cmd_2 = decode(written_frames[2])
        self.assertIsInstance(cmd_2, DrawImage)

        # Verify no black wipe or DisplaySleep in reboot mode
        decoded_cmds = [decode(f) for f in written_frames]
        self.assertFalse(any(isinstance(c, DisplaySleep) for c in decoded_cmds))
        black_wipes = [
            c
            for c in decoded_cmds
            if isinstance(c, DrawRect) and c.color == goodbye_hook._BLACK
        ]
        self.assertEqual(len(black_wipes), 0)

    @patch("time.sleep")
    def test_shutdown_splash_rendering_order_and_sync_delay(
        self,
        mock_sleep: MagicMock,
    ) -> None:
        """Shutdown sequence renders background -> 'bai baiii!' -> chunks -> black wipe -> sleep -> 0.15s delay."""
        mock_ser = MagicMock()
        written_frames: list[bytes] = []
        mock_ser.write.side_effect = written_frames.append

        with patch("serial.Serial", return_value=mock_ser):
            goodbye_hook.send_goodbye(
                port="/dev/test_shutdown",
                rgb565_path=self.valid_blob_path,
                mode="shutdown",
                hold_s=1.5,
            )

        # Check sleep calls: first hold_s=1.5, then shutdown sync 0.15s
        self.assertEqual(mock_sleep.call_count, 2)
        mock_sleep.assert_has_calls([call(1.5), call(0.15)])

        # 1. Background clear
        cmd_0 = decode(written_frames[0])
        self.assertIsInstance(cmd_0, DrawRect)
        self.assertEqual(cmd_0.color, goodbye_hook._THEME_BG)

        # 2. Text rendered before chunks
        cmd_1 = decode(written_frames[1])
        self.assertIsInstance(cmd_1, DrawText)
        self.assertEqual(cmd_1.text, "bai baiii!")
        self.assertEqual(cmd_1.x, 160)
        self.assertEqual(cmd_1.y, 184)

        # 3. Image chunks
        cmd_2 = decode(written_frames[2])
        self.assertIsInstance(cmd_2, DrawImage)

        # Final commands: black wipe and DisplaySleep
        cmd_last_2 = decode(written_frames[-2])
        self.assertIsInstance(cmd_last_2, DrawRect)
        self.assertEqual(cmd_last_2.color, goodbye_hook._BLACK)

        cmd_last = decode(written_frames[-1])
        self.assertIsInstance(cmd_last, DisplaySleep)

        # Verify serial port is closed after operations
        mock_ser.close.assert_called_once()


class TestGuestTermEnvironmentRegression(unittest.TestCase):
    """
    Test suite for TERM=xterm environment initialization in TerminalBridge.

    Validates:
    - Bridge initialization sets TERM=xterm in host environment.
    - PTY child shell spawning propagates TERM=xterm so commands like clear and demo run reliably.
    """

    def setUp(self) -> None:
        self.original_term = os.environ.get("TERM")

    def tearDown(self) -> None:
        if self.original_term is not None:
            os.environ["TERM"] = self.original_term
        else:
            os.environ.pop("TERM", None)

    def test_term_xterm_set_on_bridge_init(self) -> None:
        """TerminalBridge.__init__ ensures os.environ['TERM'] is 'xterm'."""
        if "TERM" in os.environ:
            del os.environ["TERM"]

        config = BridgeConfig(theme=load_theme(None))
        TerminalBridge(config)

        self.assertEqual(os.environ.get("TERM"), "xterm")

    @patch("pty.fork")
    @patch("terminal.bridge._tiocswinsz")
    def test_term_xterm_set_on_spawn_shell(
        self,
        mock_tiocswinsz: MagicMock,
        mock_fork: MagicMock,
    ) -> None:
        """TerminalBridge._spawn_shell guarantees TERM=xterm is exported for child sessions."""
        os.environ["TERM"] = "dumb"
        config = BridgeConfig(theme=load_theme(None))
        bridge = TerminalBridge(config)

        # Simulate parent branch of fork
        mock_fork.return_value = (4242, 10)
        pid, master_fd = bridge._spawn_shell("guest")

        self.assertEqual(pid, 4242)
        self.assertEqual(master_fd, 10)
        self.assertEqual(os.environ.get("TERM"), "xterm")
        mock_tiocswinsz.assert_called_once()


class TestSmallestFontDirtyRefreshRegression(unittest.TestCase):
    r"""
    Test suite for 53x30 smallest-font dirty-cell refresh and stale character prevention.

    Validates:
    - Geometry calculations for font 1 (53 cols x 30 rows).
    - Grid.clear() marks grid.dirty = True.
    - Grid.diff(prev) detects dirty state and emits full wash runs (_all_runs())
      to overwrite stale cells rather than skipping diff.
    - VTEmulator handles both ANSI ED 2 (\\x1b[2J) and ED 3 (\\x1b[3J), triggering
      clean grid wipes and dirty flags.
    """

    def setUp(self) -> None:
        self.theme = load_theme(None)
        self.geometry = TerminalGeometry.for_font_size(1)
        self.assertEqual(self.geometry.cols, 53)
        self.assertEqual(self.geometry.rows, 30)

    def test_grid_clear_marks_dirty_and_diff_forces_full_wash(self) -> None:
        """grid.clear() sets dirty=True and forces diff() to emit runs for all cells."""
        grid = Grid(
            self.geometry.cols,
            self.geometry.rows,
            self.theme.fg,
            self.theme.bg,
        )

        # Write characters to simulate terminal output
        grid.put_char("H", self.theme.fg, self.theme.bg)
        grid.put_char("i", self.theme.fg, self.theme.bg)
        grid.set_cursor(29, 52)
        grid.put_char("Z", self.theme.fg, self.theme.bg)

        # Snapshot of dirty grid
        prev = grid.snapshot()
        self.assertFalse(grid.dirty)

        # Clearing grid sets dirty flag
        grid.clear()
        self.assertTrue(grid.dirty)
        self.assertEqual(grid.cursor_row, 0)
        self.assertEqual(grid.cursor_col, 0)

        # diff() must notice dirty=True and emit runs across all rows (full wash)
        runs = grid.diff(prev)
        self.assertFalse(grid.dirty)  # Cleared after diff
        self.assertEqual(len(runs), self.geometry.rows)
        # Verify all cells are now blank spaces
        for r in range(grid.rows):
            for c in range(grid.cols):
                self.assertEqual(grid.cell_at(r, c).char, " ")

    def test_vt_emulator_ed2_and_ed3_clears_dirty_state(self) -> None:
        r"""VTEmulator handles \x1b[2J and \x1b[3J by clearing grid and marking dirty."""
        grid = Grid(
            self.geometry.cols,
            self.geometry.rows,
            self.theme.fg,
            self.theme.bg,
        )
        emulator = VTEmulator(grid, self.theme)

        # 1. Test ED 2 (\\x1b[2J)
        emulator.feed(b"Some test prompt content: 12345")
        prev = grid.snapshot()
        emulator.feed(b"\x1b[2J\x1b[H")

        self.assertTrue(grid.dirty)
        self.assertEqual(grid.cursor_row, 0)
        self.assertEqual(grid.cursor_col, 0)
        runs_ed2 = grid.diff(prev)
        self.assertEqual(len(runs_ed2), self.geometry.rows)

        # 2. Test ED 3 (\\x1b[3J - xterm clear scrollback & screen)
        emulator.feed(b"New prompt content after clear")
        prev2 = grid.snapshot()
        emulator.feed(b"\x1b[3J\x1b[H")

        self.assertTrue(grid.dirty)
        self.assertEqual(grid.cursor_row, 0)
        self.assertEqual(grid.cursor_col, 0)
        runs_ed3 = grid.diff(prev2)
        self.assertEqual(len(runs_ed3), self.geometry.rows)


class TestGeometrySwitchingRegression(unittest.TestCase):
    """
    Test suite for geometry switching panel clearing and gutter corruption defense.

    Validates:
    - Font size transitions wipe the entire 320x240 panel (_clear_panel) to clear gutters.
    - _prev baseline is invalidated to force full keyframe repaint.
    - Returned grid has dirty=True to guarantee no stale cells remain.
    """

    def setUp(self) -> None:
        self.config = BridgeConfig(theme=load_theme(None), font_size=1)
        self.bridge = TerminalBridge(self.config)

    def test_rebuild_geometry_clears_panel_and_invalidates_prev(self) -> None:
        """_rebuild_geometry() calls _clear_panel(), clears _prev, and sets grid.dirty=True."""
        mock_transport = MagicMock()
        self.bridge._transport = mock_transport
        self.bridge._prev = Grid(53, 30, self.bridge._theme.fg, self.bridge._theme.bg)

        # Cycle geometry
        new_grid = self.bridge._rebuild_geometry(master_fd=None)

        # 1. _prev invalidated
        self.assertIsNone(self.bridge._prev)

        # 2. _clear_panel called over transport
        mock_transport.send.assert_called()
        written_frames = [
            call_args[0][0] for call_args in mock_transport.send.call_args_list
        ]
        self.assertTrue(len(written_frames) > 0)
        clear_cmd = decode(written_frames[0])
        self.assertIsInstance(clear_cmd, DrawRect)
        self.assertEqual(clear_cmd.x, 0)
        self.assertEqual(clear_cmd.y, 0)
        self.assertEqual(clear_cmd.w, DISPLAY_WIDTH)
        self.assertEqual(clear_cmd.h, DISPLAY_HEIGHT)
        self.assertEqual(clear_cmd.color, self.bridge._theme.bg)
        self.assertTrue(clear_cmd.filled)

        # 3. New grid marked dirty
        self.assertTrue(new_grid.dirty)


class TestRestoredFontRegression(unittest.TestCase):
    """
    Test suite enforcing the restored readable built-in font from October 2, 2026.

    Validates:
    - render.h does not include custom Comic Mono bitmap font headers (font_*.h).
    - render.h uses native TFT_eSPI tft.drawString for cell rendering.
    - No Comic Mono font files or generator scripts exist in the repository.
    """

    def test_render_h_uses_builtin_font_and_no_custom_font_includes(self) -> None:
        render_h_path = REPO_ROOT / "firmware/cyd_display_link/render.h"
        self.assertTrue(render_h_path.is_file())
        content = render_h_path.read_text(encoding="utf-8")

        # Must not include font headers
        self.assertNotIn("font_6x8.h", content)
        self.assertNotIn("font_8x12.h", content)
        self.assertNotIn("font_12x16.h", content)
        self.assertNotIn("font_18x24.h", content)
        self.assertNotIn("glyph_6x8_bitmap", content)

        # Must use tft.drawString for cells (October 2 reference behavior)
        self.assertIn("tft.drawString(ch", content)

    def test_no_comic_mono_artifacts_present(self) -> None:
        forbidden_paths = [
            REPO_ROOT / "assets/fonts/ComicMono.ttf",
            REPO_ROOT / "scripts/generate_comic_mono_fonts.py",
            REPO_ROOT / "firmware/cyd_display_link/font_6x8.h",
            REPO_ROOT / "firmware/cyd_display_link/font_8x12.h",
            REPO_ROOT / "firmware/cyd_display_link/font_12x16.h",
            REPO_ROOT / "firmware/cyd_display_link/font_18x24.h",
        ]
        for p in forbidden_paths:
            self.assertFalse(p.exists(), f"Forbidden Comic Mono artifact still exists: {p}")


class TestGeometryParity(unittest.TestCase):
    """
    Test suite for font scaling, layout, and preview parity across all 3 supported geometries
    (53x30, 40x20, 17x10).

    Distinguishes simulated desktop preview (Pillow-based reconstruction) from
    physical ILI9341 hardware execution.
    """

    def test_geometries_desktop_preview_rendering(self) -> None:
        """Simulate desktop preview rendering across all 3 geometries with representative terminal content."""
        geometries = [
            (1, 53, 30, 6, 8),
            (5, 40, 20, 8, 12),
            (3, 17, 10, 18, 24),
        ]

        renderer = PreviewRenderer(width=320, height=240, background=0x0000)
        representative_content = [
            "Punctuation: !@#$%^&*()_+{}[]|;:,.<>?/",
            "Lowercase: abcdefghijklmnopqrstuvwxyz 0123456789",
            "Status: [OK] WS1:bash BAT:95% CPU:42C",
            "Multiline:\nLine 1: init\nLine 2: ready\nLine 3: active",
        ]

        for font_size, exp_cols, exp_rows, exp_w, exp_h in geometries:
            geom = TerminalGeometry.for_font_size(font_size)
            self.assertEqual(geom.cols, exp_cols)
            self.assertEqual(geom.rows, exp_rows)
            self.assertEqual(geom.cell_w, exp_w)
            self.assertEqual(geom.cell_h, exp_h)

            commands = []
            for r, text in enumerate(representative_content):
                if r < exp_rows:
                    commands.append(
                        DrawCells(
                            col=0,
                            row=r,
                            fg=0xFFFF,
                            bg=0x0000,
                            font_size=font_size,
                            text=text[:exp_cols],
                        )
                    )

            # Simulated preview (Pillow-based host reconstruction)
            img = renderer.render(commands)
            self.assertEqual(img.size, (320, 240))


if __name__ == "__main__":
    unittest.main()
