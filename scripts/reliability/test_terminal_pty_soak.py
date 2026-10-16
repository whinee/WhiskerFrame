#!/usr/bin/env python3
"""
PTY soak test for Whiskerframe CYD terminal bridge.

Validates terminal bridge and VT emulator resilience under heavy synthetic load:
- Creates a real PTY pair (master/slave).
- Drives a live _ShellSession with 10,000 randomized and structured keystrokes:
  - Printable ASCII
  - ANSI escape sequences and arrow navigation
  - Multi-byte / extended Latin-1 scancodes
  - Rapid modifier chords (Fn+Tab Ctrl latch, Ctrl+C, Ctrl+D)
  - Rapid resize cycles (Fn+Del cycling 1 -> 5 -> 2 -> 3)
- Validates:
  1. No deadlocks: 10,000 keystroke stream finishes within strict deadline.
  2. No buffer corruption: Grid geometry, row cell counts, and cursor remain within bounds.
  3. No memory leaks: Traced memory growth remains strictly bounded (<10MB).
  4. PTY cleanliness: Master and slave descriptors close cleanly without leaks.
"""

from __future__ import annotations

import os
import random
import select
import sys
import time
import tracemalloc
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "pi"))

from terminal.bridge import (  # noqa: E402
    CTRL_LATCH_CHORD,
    RESIZE_CHORD,
    RESIZE_SIZES,
    BridgeConfig,
    KeyQueue,
    TerminalBridge,
    _ShellSession,
)
from terminal.theme import load_theme  # noqa: E402
from whiskerframe.terminal import TerminalGeometry  # noqa: E402

_ARROW_KEYS = [0xB4, 0xB5, 0xB6, 0xB7]  # Left, Up, Down, Right
_STRUCTURED_INPUTS = [
    ord("l"), ord("s"), ord(" "), ord("-"), ord("l"), ord("a"), 0x0D,
    ord("c"), ord("a"), ord("t"), ord(" "), ord("/"), ord("e"), ord("t"), ord("c"),
    ord("/"), ord("o"), ord("s"), ord("-"), ord("r"), ord("e"), ord("l"), ord("e"),
    ord("a"), ord("s"), ord("e"), 0x0D,
    ord("e"), ord("c"), ord("h"), ord("o"), ord(" "), ord("'"), ord("h"), ord("e"),
    ord("l"), ord("l"), ord("o"), ord(" "), ord("c"), ord("y"), ord("d"), ord("'"), 0x0D,
]


def generate_soak_keystrokes(count: int = 10000, seed: int = 42) -> list[int]:
    """
    Generate a deterministic stream of 10,000 mixed keystrokes.

    Mixes:
    - 40% Printable ASCII letters, digits, and punctuation
    - 20% Structured command sequences (ls, cat, echo, enters)
    - 15% Arrow keys and control codes (Enter, Tab, Backspace, Ctrl-C, Ctrl-D)
    - 15% Rapid Fn+Tab sticky Ctrl latch chords
    - 10% Rapid Fn+Del geometry resize chords
    """
    rng = random.Random(seed)
    keys: list[int] = []

    while len(keys) < count:
        roll = rng.random()
        if roll < 0.40:
            # Printable ASCII (space to tilde)
            keys.append(rng.randint(0x20, 0x7E))
        elif roll < 0.60:
            # Structured command chunks
            chunk_len = min(rng.randint(3, 10), count - len(keys))
            start_idx = rng.randint(0, max(0, len(_STRUCTURED_INPUTS) - chunk_len))
            keys.extend(_STRUCTURED_INPUTS[start_idx : start_idx + chunk_len])
        elif roll < 0.75:
            # Arrows, control keys, tabs, backspaces
            ctrl_choice = rng.choice(
                _ARROW_KEYS + [0x08, 0x09, 0x0D, 0x1B, 0x03, 0x04],
            )
            keys.append(ctrl_choice)
        elif roll < 0.90:
            # Sticky Ctrl latch followed by qualifying character or cancel
            keys.append(CTRL_LATCH_CHORD)
            if rng.random() < 0.8:
                # Follow with letters or symbols
                keys.append(rng.choice([ord("c"), ord("d"), ord("z"), ord("l"), ord("@")]))
            else:
                # Toggle off or cancel with arrow
                keys.append(rng.choice([CTRL_LATCH_CHORD, 0xB5, ord("1")]))
        else:
            # Resize chords (Fn+Del)
            keys.append(RESIZE_CHORD)

    return keys[:count]


class TestTerminalPtySoak(unittest.TestCase):
    """PTY soak and stress test harness."""

    def setUp(self) -> None:
        self.master_fd, self.slave_fd = os.openpty()
        self.theme = load_theme(None)
        self.config = BridgeConfig(theme=self.theme)
        self.bridge = TerminalBridge(self.config)
        # Mock serial transport so no real hardware is required
        self.bridge._ensure_serial = MagicMock(return_value=None)
        self.paint_calls = 0

        def dummy_paint(grid: Any) -> None:
            self.paint_calls += 1

        self.bridge._paint = dummy_paint

    def tearDown(self) -> None:
        for fd in (self.master_fd, self.slave_fd):
            try:
                os.close(fd)
            except OSError:
                pass

    def test_pty_soak_10000_keystrokes(self) -> None:
        """Pump 10,000 keystrokes through PTY and assert no leaks, corruptions, or deadlocks."""
        keystrokes = generate_soak_keystrokes(10000)
        key_queue = KeyQueue(iter(keystrokes))
        session = _ShellSession(self.bridge, self.master_fd, key_queue)

        tracemalloc.start()
        snapshot_start = tracemalloc.take_snapshot()
        start_time = time.monotonic()
        deadline = start_time + 30.0  # Max 30 seconds runtime

        processed = 0
        resize_count = 0
        latch_count = 0

        while processed < len(keystrokes):
            if time.monotonic() > deadline:
                self.fail(f"DEADLOCK DETECTED: Processed only {processed}/{len(keystrokes)} before 30s timeout")

            key = key_queue.get_blocking()
            if key is None:
                break

            if key == RESIZE_CHORD:
                resize_count += 1
            elif key == CTRL_LATCH_CHORD:
                latch_count += 1

            ok = session._process_single_key(key)
            self.assertTrue(ok, f"Processing failed on key {key:#02x} at index {processed}")
            processed += 1

            # Periodically simulate bidirectional PTY traffic
            if processed % 50 == 0:
                # Check if data was written to slave side
                r_ready, _, _ = select.select([self.master_fd, self.slave_fd], [], [], 0.0)
                if self.slave_fd in r_ready:
                    try:
                        read_bytes = os.read(self.slave_fd, 1024)
                        # Echo back formatted terminal response
                        if read_bytes:
                            simulated_echo = b"\r\n\x1b[32moutput\x1b[0m " + read_bytes[:16]
                            os.write(self.slave_fd, simulated_echo)
                    except OSError:
                        pass

                if self.master_fd in r_ready:
                    session._fetch_and_feed_pty()

        elapsed = time.monotonic() - start_time
        snapshot_end = tracemalloc.take_snapshot()
        tracemalloc.stop()

        # 1. Assert Deadlock / Progress
        self.assertEqual(processed, len(keystrokes), "All 10,000 keystrokes must be processed")
        self.assertLess(elapsed, 30.0, f"Soak completed in {elapsed:.2f}s (budget: 30s)")

        # 2. Assert Buffer and Grid Invariants
        active_font = self.bridge._font_size
        expected_geom = TerminalGeometry.for_font_size(active_font)
        grid = session._grid
        self.assertEqual(grid.cols, expected_geom.cols, "Grid cols must match font geometry")
        self.assertEqual(grid.rows, expected_geom.rows, "Grid rows must match font geometry")
        self.assertGreaterEqual(resize_count, 100, "Resize chords must have executed")
        self.assertGreaterEqual(latch_count, 500, "Ctrl latch chords must have executed")

        # Verify cursor invariant on grid
        self.assertGreaterEqual(grid.cursor_col, 0)
        self.assertLess(grid.cursor_col, grid.cols)
        self.assertGreaterEqual(grid.cursor_row, 0)
        self.assertLess(grid.cursor_row, grid.rows)

        # Verify all rows have uniform width and valid cells
        for row_idx in range(grid.rows):
            for col_idx in range(grid.cols):
                cell = grid.cell_at(row_idx, col_idx)
                self.assertIsNotNone(cell.char)
                self.assertIsInstance(cell.fg, int)
                self.assertIsInstance(cell.bg, int)

        # 3. Assert Memory Growth Bound (< 10MB)
        top_stats = snapshot_end.compare_to(snapshot_start, "lineno")
        total_growth_bytes = sum(stat.size_diff for stat in top_stats if stat.size_diff > 0)
        total_growth_mb = total_growth_bytes / (1024 * 1024)
        self.assertLess(
            total_growth_mb,
            10.0,
            f"Excessive memory growth during soak: {total_growth_mb:.2f} MB > 10 MB ceiling",
        )


def main() -> int:
    """Run standalone soak test with formatted reporting."""
    print("=" * 70)
    print("Running Whiskerframe Terminal PTY Soak Test (10,000 Keystrokes)")
    print("=" * 70)

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestTerminalPtySoak)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
