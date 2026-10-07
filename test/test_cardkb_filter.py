"""
Unit test for the CardKB input filter (`cardkb.reader.KeyFilter`).

**Validates: Requirements (cyd-terminal: CardKB ghost/noise filtering)**

Assert the pure, hardware-free `KeyFilter.accept` behavior:

- whitelist drops idle ``0x00``, floating-bus ``0xFF``, and stray high bytes;
- valid bytes pass: printable ``'A'``, control ``Ctrl-C``, ``Enter``, an arrow;
- debounce rejects an identical raw byte repeated within the window, accepts the
  same byte once the window elapses, and always accepts a different byte.

Debounce is driven with injected ``now`` timestamps, so the script is pure (no
hardware, no sleeping, deterministic). It adds ``pi/`` to ``sys.path``, runs as
``python test/test_cardkb_filter.py``, prints ``PASS`` on success, and exits
non-zero on the first failure.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "pi"))

from cardkb.reader import DEBOUNCE_WINDOW_S, KeyFilter


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        print(f"FAIL: {msg}")
        sys.exit(1)


def check_whitelist_drops() -> None:
    kf = KeyFilter()
    _assert(not kf.accept(0x00, now=0.0), "idle 0x00 must be dropped")
    _assert(not kf.accept(0xFF, now=0.0), "floating-bus 0xFF must be dropped")
    _assert(not kf.accept(0xB0, now=0.0), "stray high byte 0xB0 (above Fn layer) must be dropped")
    _assert(not kf.accept(0xB8, now=0.0), "stray high byte 0xB8 (above arrows) must be dropped")


def check_whitelist_passes() -> None:
    # Fresh filter per byte so debounce never interferes with validity checks.
    _assert(KeyFilter().accept(0x41, now=0.0), "printable 'A' (0x41) must pass")
    _assert(KeyFilter().accept(0x03, now=0.0), "Ctrl-C (0x03) must pass")
    _assert(KeyFilter().accept(0x0D, now=0.0), "Enter (0x0D) must pass")
    _assert(KeyFilter().accept(0xB5, now=0.0), "arrow up (0xB5) must pass")
    _assert(KeyFilter().accept(0x7F, now=0.0), "Shift+Del (0x7F) must pass")
    _assert(KeyFilter().accept(0x8B, now=0.0), "Fn+Del resize chord (0x8B) must pass")
    _assert(KeyFilter().accept(0x80, now=0.0), "Fn layer start (0x80) must pass")
    _assert(KeyFilter().accept(0xAF, now=0.0), "Fn layer end (0xAF) must pass")


def check_debounce_identical_within_window() -> None:
    kf = KeyFilter()
    _assert(kf.accept(0x41, now=0.0), "first 'A' must pass")
    _assert(
        not kf.accept(0x41, now=DEBOUNCE_WINDOW_S / 2),
        "identical 'A' within window must be rejected",
    )


def check_debounce_same_byte_after_window() -> None:
    kf = KeyFilter()
    _assert(kf.accept(0x41, now=0.0), "first 'A' must pass")
    _assert(
        kf.accept(0x41, now=DEBOUNCE_WINDOW_S + 0.001),
        "same 'A' after window must pass (held-repeat / double-letter)",
    )


def check_debounce_different_byte_within_window() -> None:
    kf = KeyFilter()
    _assert(kf.accept(0x41, now=0.0), "first 'A' must pass")
    _assert(
        kf.accept(0x42, now=DEBOUNCE_WINDOW_S / 2),
        "different 'B' within window must pass immediately",
    )


def main() -> None:
    check_whitelist_drops()
    check_whitelist_passes()
    check_debounce_identical_within_window()
    check_debounce_same_byte_after_window()
    check_debounce_different_byte_within_window()
    print("PASS")


if __name__ == "__main__":
    main()
