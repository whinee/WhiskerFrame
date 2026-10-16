#!/usr/bin/env python3
"""
Hardware key-probe test and interactive diagnostic for M5Stack CardKB.

Runs in two modes:
1. Automated unit test (default or when run via unittest / pytest / --test):
   Validates scancode decoding, Ctrl latch resolution, and mock I2C reads.
2. Live hardware probe (when run directly with --live or when /dev/i2c-0 exists):
   Connects to CardKB on /dev/i2c-0 @ 0x5F and logs scancodes live.
"""

from __future__ import annotations

import argparse
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

_this = Path(__file__).resolve()
for candidate in [
    _this.parent.parent / "pi",
    _this.parent.parent,
    Path("/opt/cyd-display-link/pi"),
]:
    if candidate.exists() and str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from cardkb.reader import CardKB  # noqa: E402
from terminal.bridge import (  # noqa: E402
    _CTRL_VALID_CHARS,
    CTRL_LATCH_CHORD,
    RESIZE_CHORDS,
)

_CHORD_NAMES: dict[int, str] = {
    CTRL_LATCH_CHORD: "Fn+Tab (Sticky Ctrl Latch)",
    0x8B: "Fn+Del (Geometry Resize)",
    0xB4: "Arrow Left",
    0xB5: "Arrow Up",
    0xB6: "Arrow Down",
    0xB7: "Arrow Right",
    0x08: "Backspace",
    0x09: "Tab",
    0x0D: "Enter",
    0x1B: "Escape",
    0x7F: "Shift+Del (DEL)",
}


def describe_key(byte_val: int) -> str:
    """Format a raw byte with hex, decimal, and human-readable description."""
    chord_desc = _CHORD_NAMES.get(byte_val)
    if chord_desc:
        return f"0x{byte_val:02X} ({byte_val:3d}) -> {chord_desc}"
    if byte_val in _CTRL_VALID_CHARS:
        ctrl_code = byte_val & 0x1F
        char_repr = (
            f"'{chr(byte_val)}'" if 0x20 <= byte_val <= 0x7E else f"0x{byte_val:02X}"
        )
        return f"0x{byte_val:02X} ({byte_val:3d}) -> {char_repr} (Ctrl -> 0x{ctrl_code:02X})"
    if 0x20 <= byte_val <= 0x7E:
        return f"0x{byte_val:02X} ({byte_val:3d}) -> Printable ASCII '{chr(byte_val)}'"
    return f"0x{byte_val:02X} ({byte_val:3d}) -> Raw Scancode"


def run_live_probe(bus: int = 0, address: int = 0x5F, max_keys: int = 0) -> int:
    """Read CardKB continuously and print each decoded key to stdout."""
    print(f"Opening CardKB on /dev/i2c-{bus} @ 0x{address:02X}...")
    try:
        kb = CardKB(bus=bus, address=address)
        kb.open()
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: Cannot open CardKB: {exc}")
        return 1

    print("CardKB opened successfully. Press keys (Ctrl+C to exit):")
    count = 0
    try:
        for key in kb.robust_keys():
            print(f"[{count:04d}] {describe_key(key)}")
            count += 1
            if max_keys and count >= max_keys:
                break
    except KeyboardInterrupt:
        print("\nProbe stopped by user.")
    finally:
        kb.close()
    return 0


class TestCardKBHardwareProbe(unittest.TestCase):
    """Unit test suite for scancode decoder and probe logic."""

    def test_describe_special_chords(self) -> None:
        """Verify descriptions for sticky Ctrl and resize chords."""
        desc_ctrl = describe_key(CTRL_LATCH_CHORD)
        self.assertIn("Fn+Tab", desc_ctrl)
        self.assertIn("Sticky Ctrl", desc_ctrl)

        for chord in RESIZE_CHORDS:
            desc_resize = describe_key(chord)
            self.assertIn("Resize", desc_resize)

    def test_describe_printable(self) -> None:
        """Verify printable ASCII characters are rendered accurately."""
        desc = describe_key(ord("A"))
        self.assertIn("'A'", desc)
        self.assertIn("0x41", desc)

    def test_describe_ctrl_maskable(self) -> None:
        """Verify Ctrl-maskable letters show resulting control code."""
        desc_c = describe_key(ord("c"))
        self.assertIn("Ctrl -> 0x03", desc_c)

    @patch("cardkb.reader.os.close")
    @patch("cardkb.reader.os.read")
    @patch("cardkb.reader.os.open")
    @patch("cardkb.reader.fcntl.ioctl")
    def test_mock_live_probe_reading(
        self,
        mock_ioctl: MagicMock,
        mock_open: MagicMock,
        mock_read: MagicMock,
        mock_close: MagicMock,
    ) -> None:
        """Verify probe reads keys through CardKB without error."""
        mock_open.return_value = 10
        # Return 0x8C (Fn+Tab), then 0x63 ('c')
        mock_read.side_effect = [bytes([CTRL_LATCH_CHORD]), b"c"]

        kb = CardKB(bus=0, address=0x5F)
        kb.open()
        self.assertEqual(kb.read_key(), CTRL_LATCH_CHORD)
        self.assertEqual(kb.read_key(), ord("c"))
        kb.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="CardKB Hardware Key Probe")
    parser.add_argument(
        "--live",
        action="store_true",
        help="Run interactive live I2C probe",
    )
    parser.add_argument("--bus", type=int, default=0, help="I2C bus number")
    parser.add_argument(
        "--address",
        type=lambda x: int(x, 0),
        default=0x5F,
        help="I2C address",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=0,
        help="Stop after N keys (0 = infinite)",
    )
    args, unknown = parser.parse_known_args()

    if args.live:
        return run_live_probe(bus=args.bus, address=args.address, max_keys=args.count)

    # Otherwise run unit tests
    unittest.main(argv=[sys.argv[0], *unknown])
    return 0


if __name__ == "__main__":
    sys.exit(main())
