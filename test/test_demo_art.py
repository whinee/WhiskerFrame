#!/usr/bin/env python3
"""
Unit and integration tests for Cyberdeck demo art pipeline (pi/bin/demo).

Validates:
1. Safe path resolution strictly preventing directory traversal (DEC-W35).
2. Proper aspect ratio preservation and centering on 320x240 CYD panel.
3. Big-endian RGB565 byte packing matching ILI9341 pushImage contract (DEC-W5).
4. Chunked transmission using DRAW_IMAGE opcode 0x05 (<=1280B payload per chunk).
5. Clean exit restoring terminal grid state without screen corruption.
6. CLI sub-command execution for 'demo' and 'demo art'.
"""

from __future__ import annotations

import importlib.util
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from importlib.machinery import SourceFileLoader
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "pi"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

# Dynamically load pi/bin/demo extensionless script
DEMO_PATH = REPO_ROOT / "pi" / "bin" / "demo"
loader = SourceFileLoader("demo", str(DEMO_PATH))
spec = importlib.util.spec_from_loader("demo", loader)
if spec is None or spec.loader is None:
    raise ImportError(f"Cannot load demo script from {DEMO_PATH}")
demo = importlib.util.module_from_spec(spec)
sys.modules["demo"] = demo
loader.exec_module(demo)

from PIL import Image  # noqa: E402
from terminal.grid import Grid  # noqa: E402
from terminal.theme import load_theme  # noqa: E402
from terminal.vt import VTEmulator  # noqa: E402

from whiskerframe.models import DrawRect  # noqa: E402
from whiskerframe.protocol import decode  # noqa: E402
from whiskerframe.terminal import (  # noqa: E402
    DrawImage,
)


class MockSink:
    """Mock sink capturing framed byte sequences transmitted to display."""

    def __init__(self) -> None:
        self.frames: list[bytes] = []
        self.flushed: bool = False

    def send(self, frame: bytes) -> None:
        self.frames.append(frame)

    def write(self, frame: bytes) -> None:
        self.frames.append(frame)

    def flush(self) -> None:
        self.flushed = True


class TestSafePathResolution(unittest.TestCase):
    """Test suite for safe path resolution and directory traversal defense."""

    def setUp(self) -> None:
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="wf_art_test_"))
        self.workspace_root = self.tmp_dir / "workspace"
        self.workspace_root.mkdir()
        self.assets_dir = self.workspace_root / "assets" / "images"
        self.assets_dir.mkdir(parents=True)

        # Create dummy image in assets
        self.valid_img = self.assets_dir / "test_art.png"
        img = Image.new("RGB", (100, 100), (255, 0, 0))
        img.save(self.valid_img)

        # Create sensitive file outside workspace
        self.secret_file = self.tmp_dir / "secret.txt"
        self.secret_file.write_text("SUPER_SECRET_TOKEN")

    def tearDown(self) -> None:
        import shutil

        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_resolve_valid_workspace_relative_path(self) -> None:
        """Valid relative path within workspace resolves successfully."""
        resolved = demo.resolve_safe_image_path(
            "assets/images/test_art.png",
            workspace_root=self.workspace_root,
        )
        self.assertEqual(resolved, self.valid_img.resolve())

    def test_resolve_shorthand_assets_path(self) -> None:
        """Shorthand path relative to assets/images resolves successfully."""
        resolved = demo.resolve_safe_image_path(
            "test_art.png",
            workspace_root=self.workspace_root,
        )
        self.assertEqual(resolved, self.valid_img.resolve())

    def test_resolve_catalog_aliases(self) -> None:
        """Catalog aliases like 'doodle' and 'market' resolve within repo root."""
        doodle_path = demo.resolve_safe_image_path("doodle", workspace_root=REPO_ROOT)
        self.assertTrue(doodle_path.is_file())
        self.assertTrue(doodle_path.is_relative_to(REPO_ROOT))

        market_path = demo.resolve_safe_image_path("market", workspace_root=REPO_ROOT)
        self.assertTrue(market_path.is_file())
        self.assertTrue(market_path.is_relative_to(REPO_ROOT))

    def test_traversal_with_dot_dot_rejected(self) -> None:
        """Traversal attempts using '..' outside workspace are strictly rejected."""
        traversal_attempts = [
            "../secret.txt",
            "../../secret.txt",
            "assets/images/../../../secret.txt",
            "../../../etc/passwd",
            "assets/images/../../../../etc/shadow",
        ]
        for attempt in traversal_attempts:
            with self.assertRaises(
                PermissionError,
                msg=f"Failed to reject traversal: {attempt}",
            ):
                demo.resolve_safe_image_path(
                    attempt,
                    workspace_root=self.workspace_root,
                )

    def test_absolute_path_outside_workspace_rejected(self) -> None:
        """Absolute system paths outside workspace are strictly rejected."""
        with self.assertRaises(PermissionError):
            demo.resolve_safe_image_path(
                str(self.secret_file),
                workspace_root=self.workspace_root,
            )
        with self.assertRaises(PermissionError):
            demo.resolve_safe_image_path(
                "/etc/passwd",
                workspace_root=self.workspace_root,
            )

    def test_symlink_escaping_workspace_rejected(self) -> None:
        """Symlinks pointing outside the workspace boundary are rejected."""
        evil_symlink = self.assets_dir / "evil_symlink.png"
        try:
            evil_symlink.symlink_to(self.secret_file)
        except OSError:
            self.skipTest("Symlinks not supported in environment")

        with self.assertRaises(PermissionError):
            demo.resolve_safe_image_path(
                "assets/images/evil_symlink.png",
                workspace_root=self.workspace_root,
            )

    def test_missing_file_within_workspace_raises_not_found(self) -> None:
        """Non-existent file within workspace boundary raises FileNotFoundError."""
        with self.assertRaises(FileNotFoundError):
            demo.resolve_safe_image_path(
                "assets/images/missing.png",
                workspace_root=self.workspace_root,
            )

    def test_empty_or_null_byte_path_raises_value_error(self) -> None:
        """Empty path or path containing null bytes raises ValueError."""
        with self.assertRaises(ValueError):
            demo.resolve_safe_image_path("", workspace_root=self.workspace_root)
        with self.assertRaises(ValueError):
            demo.resolve_safe_image_path("   ", workspace_root=self.workspace_root)
        with self.assertRaises(ValueError):
            demo.resolve_safe_image_path(
                "image\0.png",
                workspace_root=self.workspace_root,
            )


class TestAspectScalingAndCentering(unittest.TestCase):
    """Test suite for aspect-ratio preserving scaling and centering on 320x240."""

    def test_square_image_scaling_and_centering(self) -> None:
        """Square image (500x500) scales to 240x240 and centers at x=40, y=0."""
        img = Image.new("RGB", (500, 500), (200, 100, 50))
        canvas, offset_x, offset_y, scaled_w, scaled_h = demo.scale_and_center_image(
            img,
            320,
            240,
        )

        self.assertEqual(canvas.size, (320, 240))
        self.assertEqual(scaled_w, 240)
        self.assertEqual(scaled_h, 240)
        self.assertEqual(offset_x, 40)
        self.assertEqual(offset_y, 0)

        # Check pillarbox background color (default blurple 25, 26, 40)
        pixels = canvas.load()
        self.assertIsNotNone(pixels)
        # Left pillarbox pixel
        self.assertEqual(pixels[10, 120], (25, 26, 40))
        # Right pillarbox pixel
        self.assertEqual(pixels[300, 120], (25, 26, 40))
        # Centered image pixel
        self.assertEqual(pixels[160, 120], (200, 100, 50))

    def test_landscape_image_scaling_and_centering(self) -> None:
        """Wide landscape image (640x240) scales to 320x120 and centers at x=0, y=60."""
        img = Image.new("RGB", (640, 240), (0, 255, 0))
        canvas, offset_x, offset_y, scaled_w, scaled_h = demo.scale_and_center_image(
            img,
            320,
            240,
        )

        self.assertEqual(canvas.size, (320, 240))
        self.assertEqual(scaled_w, 320)
        self.assertEqual(scaled_h, 120)
        self.assertEqual(offset_x, 0)
        self.assertEqual(offset_y, 60)

        pixels = canvas.load()
        self.assertIsNotNone(pixels)
        # Top letterbox pixel
        self.assertEqual(pixels[160, 20], (25, 26, 40))
        # Bottom letterbox pixel
        self.assertEqual(pixels[160, 220], (25, 26, 40))
        # Center image pixel
        self.assertEqual(pixels[160, 120], (0, 255, 0))

    def test_portrait_image_scaling_and_centering(self) -> None:
        """Tall portrait image (200x600) scales to 80x240 and centers at x=120, y=0."""
        img = Image.new("RGB", (200, 600), (0, 0, 255))
        canvas, offset_x, offset_y, scaled_w, scaled_h = demo.scale_and_center_image(
            img,
            320,
            240,
        )

        self.assertEqual(canvas.size, (320, 240))
        self.assertEqual(scaled_w, 80)
        self.assertEqual(scaled_h, 240)
        self.assertEqual(offset_x, 120)
        self.assertEqual(offset_y, 0)

    def test_exact_320x240_image_no_offsets(self) -> None:
        """Image matching 320x240 exactly scales to 320x240 at offset (0, 0)."""
        img = Image.new("RGB", (320, 240), (128, 128, 128))
        canvas, offset_x, offset_y, scaled_w, scaled_h = demo.scale_and_center_image(
            img,
            320,
            240,
        )

        self.assertEqual(canvas.size, (320, 240))
        self.assertEqual(scaled_w, 320)
        self.assertEqual(scaled_h, 240)
        self.assertEqual(offset_x, 0)
        self.assertEqual(offset_y, 0)

    def test_rgba_alpha_compositing(self) -> None:
        """RGBA image with transparency is properly composited onto background."""
        # 100x100 transparent image with opaque red circle in center
        img = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
        for x in range(30, 70):
            for y in range(30, 70):
                img.putpixel((x, y), (255, 0, 0, 255))

        canvas, offset_x, offset_y, _, _ = demo.scale_and_center_image(
            img,
            320,
            240,
            bg_color=(25, 26, 40),
        )
        pixels = canvas.load()
        self.assertIsNotNone(pixels)
        # Background pixel outside red square remains theme background
        self.assertEqual(pixels[offset_x + 10, offset_y + 10], (25, 26, 40))
        # Center of scaled image is within opaque red square
        self.assertEqual(pixels[offset_x + 120, offset_y + 120], (255, 0, 0))


class TestBigEndianRGB565Packing(unittest.TestCase):
    """Test suite for big-endian RGB565 byte encoding (DEC-W5)."""

    def test_pure_color_packing(self) -> None:
        """Verify high-byte-first RGB565 encoding for primary colors."""
        # Pure Red: 0xF800 -> high byte 0xF8, low byte 0x00
        red_bytes = demo.pack_rgb565_be(255, 0, 0)
        self.assertEqual(red_bytes, bytes([0xF8, 0x00]))

        # Pure Green: 0x07E0 -> high byte 0x07, low byte 0xE0
        green_bytes = demo.pack_rgb565_be(0, 255, 0)
        self.assertEqual(green_bytes, bytes([0x07, 0xE0]))

        # Pure Blue: 0x001F -> high byte 0x00, low byte 0x1F
        blue_bytes = demo.pack_rgb565_be(0, 0, 255)
        self.assertEqual(blue_bytes, bytes([0x00, 0x1F]))

        # Pure Black: 0x0000
        black_bytes = demo.pack_rgb565_be(0, 0, 0)
        self.assertEqual(black_bytes, bytes([0x00, 0x00]))

        # Pure White: 0xFFFF
        white_bytes = demo.pack_rgb565_be(255, 255, 255)
        self.assertEqual(white_bytes, bytes([0xFF, 0xFF]))

        # Theme blurple background: RGB(25, 26, 40) -> 0x18C5
        theme_bytes = demo.pack_rgb565_be(25, 26, 40)
        self.assertEqual(theme_bytes, bytes([0x18, 0xC5]))

    def test_full_image_rgb565_conversion_size(self) -> None:
        """320x240 image converts to exactly 153,600 big-endian bytes."""
        img = Image.new("RGB", (320, 240), (25, 26, 40))
        blob = demo.image_to_rgb565_be(img)
        self.assertEqual(len(blob), 320 * 240 * 2)
        # Every pixel matches theme blurple [0x18, 0xC5]
        self.assertEqual(blob[:2], bytes([0x18, 0xC5]))
        self.assertEqual(blob[-2:], bytes([0x18, 0xC5]))


class TestChunkedTransmission(unittest.TestCase):
    """Test suite for chunked transmission via DRAW_IMAGE opcode 0x05 (DEC-W35)."""

    def setUp(self) -> None:
        self.pixel_data = bytes([0x18, 0xC5] * (320 * 240))  # 153,600 bytes

    def test_chunk_count_and_sizing(self) -> None:
        """Streaming 320x240 image with chunk_rows=2 yields exactly 120 chunks of 1280B."""
        sink = MockSink()
        count = demo.stream_image_chunks(
            sink,
            self.pixel_data,
            width=320,
            height=240,
            chunk_rows=2,
        )

        self.assertEqual(count, 120)
        self.assertEqual(len(sink.frames), 120)

        # Inspect and decode each frame
        for i, frame in enumerate(sink.frames):
            cmd = decode(frame)
            self.assertIsInstance(cmd, DrawImage, f"Chunk {i} must decode as DrawImage")
            self.assertEqual(cmd.x, 0)
            self.assertEqual(cmd.y, i * 2, f"Chunk {i} Y-coordinate mismatch")
            self.assertEqual(cmd.w, 320)
            self.assertEqual(cmd.h, 2)
            self.assertEqual(
                len(cmd.data),
                1280,
                f"Chunk {i} payload must be 1280 bytes",
            )

            # Frame size must be bounded below kMaxFrameLen (2048)
            self.assertLess(len(frame), 2048)

    def test_custom_chunk_rows(self) -> None:
        """Custom chunk_rows=4 yields 60 chunks of 2560 bytes."""
        sink = MockSink()
        count = demo.stream_image_chunks(
            sink,
            self.pixel_data,
            width=320,
            height=240,
            chunk_rows=4,
        )
        self.assertEqual(count, 60)
        self.assertEqual(len(sink.frames), 60)

        first_cmd = decode(sink.frames[0])
        self.assertIsInstance(first_cmd, DrawImage)
        self.assertEqual(first_cmd.h, 4)
        self.assertEqual(len(first_cmd.data), 320 * 4 * 2)

    def test_invalid_data_length_raises_value_error(self) -> None:
        """Mismatched pixel data buffer raises ValueError."""
        sink = MockSink()
        with self.assertRaises(ValueError):
            demo.stream_image_chunks(sink, b"too_short", width=320, height=240)


class TestCleanExitAndGridRestoration(unittest.TestCase):
    """Test suite for clean exit and screen restoration without corruption."""

    def test_restore_terminal_grid_sends_clear_and_ansi(self) -> None:
        """Screen restoration sends panel DrawRect wipe and ANSI clear screen."""
        sink = MockSink()
        stdout_buf = io.StringIO()

        with redirect_stdout(stdout_buf):
            demo.restore_terminal_grid(sink, clear_color=0x18C5)

        # 1. Hardware panel wipe
        self.assertEqual(len(sink.frames), 1)
        clear_cmd = decode(sink.frames[0])
        self.assertIsInstance(clear_cmd, DrawRect)
        self.assertEqual(clear_cmd.x, 0)
        self.assertEqual(clear_cmd.y, 0)
        self.assertEqual(clear_cmd.w, 320)
        self.assertEqual(clear_cmd.h, 240)
        self.assertEqual(clear_cmd.color, 0x18C5)
        self.assertTrue(clear_cmd.filled)

        # 2. Terminal ANSI escape sequence
        ansi_out = stdout_buf.getvalue()
        self.assertIn("\033[2J\033[H", ansi_out)

    def test_vt_emulator_grid_restoration_parity(self) -> None:
        """ANSI clear screen resets VTEmulator grid cleanly with cursor homed."""
        theme = load_theme()
        grid = Grid(cols=53, rows=30, default_fg=theme.fg, default_bg=theme.bg)
        emulator = VTEmulator(grid=grid, theme=theme)
        # Dirty the grid
        emulator.feed(b"Some dirty text from interactive session\r\nline 2")
        self.assertTrue(
            any(
                emulator.grid.cell_at(r, c).char != " "
                for r in range(grid.rows)
                for c in range(grid.cols)
            ),
        )

        # Feed the clear sequence emitted by restore_terminal_grid
        emulator.feed(b"\033[2J\033[H")

        # Grid must be completely empty and cursor at (0, 0)
        self.assertTrue(
            all(
                emulator.grid.cell_at(r, c).char == " "
                for r in range(grid.rows)
                for c in range(grid.cols)
            ),
        )
        self.assertEqual(emulator.grid.cursor_row, 0)
        self.assertEqual(emulator.grid.cursor_col, 0)

    @patch("time.sleep")
    def test_run_demo_art_lifecycle_with_mock_sink(self, mock_sleep: MagicMock) -> None:
        """Full run_demo_art execution: clear -> stream chunks -> hold -> restore grid."""
        sink = MockSink()
        stdout_buf = io.StringIO()

        with redirect_stdout(stdout_buf):
            code = demo.run_demo_art(
                image_arg="doodle",
                hold_s=1.0,
                sink=sink,
                clear_on_exit=True,
            )

        self.assertEqual(code, 0)
        mock_sleep.assert_called()

        # Frames: 1 initial clear + 120 image chunks + 1 final clear = 122 frames
        self.assertEqual(len(sink.frames), 122)

        # Initial frame is clear
        first_cmd = decode(sink.frames[0])
        self.assertIsInstance(first_cmd, DrawRect)
        self.assertEqual(first_cmd.color, 0x18C5)

        # Middle frames are DrawImage chunks
        mid_cmd = decode(sink.frames[1])
        self.assertIsInstance(mid_cmd, DrawImage)

        # Final frame is clean restoration DrawRect
        last_cmd = decode(sink.frames[-1])
        self.assertIsInstance(last_cmd, DrawRect)
        self.assertEqual(last_cmd.color, 0x18C5)


class TestDemoCLIIntegration(unittest.TestCase):
    """Test suite for CLI dispatch and arguments."""

    def test_default_demo_invocation_prints_sandbox_banner(self) -> None:
        """'demo' with no arguments prints the 53-col sandbox telemetry banner."""
        stdout_buf = io.StringIO()
        with redirect_stdout(stdout_buf):
            code = demo.main([])

        self.assertEqual(code, 0)
        output = stdout_buf.getvalue()
        self.assertIn("Whiskerframe Cyberdeck v0.1 Demo Sandbox", output)
        self.assertIn("Restricted kernel sandbox:", output)
        self.assertIn("nftables egress drop", output)
        self.assertIn("Live Deck Telemetry", output)

    def test_demo_art_list_catalog(self) -> None:
        """'demo art --list' displays artwork catalog without error."""
        stdout_buf = io.StringIO()
        with redirect_stdout(stdout_buf):
            code = demo.main(["art", "--list"])

        self.assertEqual(code, 0)
        output = stdout_buf.getvalue()
        self.assertIn("Artwork Catalog", output)
        self.assertIn("doodle", output)
        self.assertIn("market", output)

    def test_demo_art_dry_run_execution(self) -> None:
        """'demo art --dry-run --hold 0' executes clean dry run."""
        stdout_buf = io.StringIO()
        with redirect_stdout(stdout_buf):
            code = demo.main(["art", "doodle", "--dry-run", "--hold", "0"])

        self.assertEqual(code, 0)
        output = stdout_buf.getvalue()
        self.assertIn("Rendered 'lyra-doodle-transparent.png'", output)
        self.assertIn("320x240", output)

    def test_demo_art_invalid_path_fails(self) -> None:
        """'demo art ../../etc/passwd' fails with non-zero exit and error."""
        stderr_buf = io.StringIO()
        with redirect_stderr(stderr_buf):
            code = demo.main(["art", "../../etc/passwd"])

        self.assertNotEqual(code, 0)
        err = stderr_buf.getvalue()
        self.assertIn("Path traversal detected", err)


if __name__ == "__main__":
    unittest.main()
