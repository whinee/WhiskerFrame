"""
Unit test for the terminal theme's total SGR-to-RGB565 mapping.

**Validates: Requirements (cyd-terminal design: piiiiink theme / SGR map)**

Assert that :meth:`terminal.theme.Theme.sgr_to_rgb565` is **total** over every
byte value ``0..255`` (never raises and always returns an `SgrResult`), and that
the key codes map correctly: ``0`` resets to defaults, ``30``-``37`` and
``90``-``97`` select foregrounds from the ANSI table, ``40``-``47`` and
``100``-``107`` select backgrounds, ``39``/``49`` restore defaults, and an
unsupported code (e.g. bold ``1``) is a no-op.

The script is pure (no hardware, no Pillow). It adds ``pi/`` to ``sys.path``,
runs as ``uv run python test/unit_theme_sgr.py``, prints ``PASS`` on success, and
exits non-zero on the first failure.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "pi"))

from terminal.theme import DEFAULT_ANSI, load_theme

_DEFAULT_FG: int = 0x1234
_DEFAULT_BG: int = 0x5678


def check_totality() -> None:
    """
    Assert the SGR map never raises across all byte values ``0..255``.

    Raises:
    - `AssertionError`: If any code raises or returns a non-`SgrResult`.

    Returns:
    `None`: Returns nothing when the map is total.

    """
    theme = load_theme({})
    for code in range(256):
        result = theme.sgr_to_rgb565(code, _DEFAULT_FG, _DEFAULT_BG)
        assert result is not None, f"code {code} returned None"


def check_key_codes() -> None:
    """
    Assert the documented SGR codes map to the expected colour changes.

    Raises:
    - `AssertionError`: If any key code maps incorrectly.

    Returns:
    `None`: Returns nothing when every mapping is correct.

    """
    theme = load_theme({})

    reset = theme.sgr_to_rgb565(0, _DEFAULT_FG, _DEFAULT_BG)
    assert reset.reset and reset.fg == _DEFAULT_FG and reset.bg == _DEFAULT_BG

    assert theme.sgr_to_rgb565(31, _DEFAULT_FG, _DEFAULT_BG).fg == DEFAULT_ANSI[1]
    assert theme.sgr_to_rgb565(37, _DEFAULT_FG, _DEFAULT_BG).fg == DEFAULT_ANSI[7]
    assert theme.sgr_to_rgb565(91, _DEFAULT_FG, _DEFAULT_BG).fg == DEFAULT_ANSI[9]
    assert theme.sgr_to_rgb565(97, _DEFAULT_FG, _DEFAULT_BG).fg == DEFAULT_ANSI[15]

    assert theme.sgr_to_rgb565(41, _DEFAULT_FG, _DEFAULT_BG).bg == DEFAULT_ANSI[1]
    assert theme.sgr_to_rgb565(47, _DEFAULT_FG, _DEFAULT_BG).bg == DEFAULT_ANSI[7]
    assert theme.sgr_to_rgb565(101, _DEFAULT_FG, _DEFAULT_BG).bg == DEFAULT_ANSI[9]
    assert theme.sgr_to_rgb565(107, _DEFAULT_FG, _DEFAULT_BG).bg == DEFAULT_ANSI[15]

    assert theme.sgr_to_rgb565(39, _DEFAULT_FG, _DEFAULT_BG).fg == _DEFAULT_FG
    assert theme.sgr_to_rgb565(49, _DEFAULT_FG, _DEFAULT_BG).bg == _DEFAULT_BG

    noop = theme.sgr_to_rgb565(1, _DEFAULT_FG, _DEFAULT_BG)
    assert not noop.reset and noop.fg is None and noop.bg is None, "bold must be no-op"

    unknown = theme.sgr_to_rgb565(200, _DEFAULT_FG, _DEFAULT_BG)
    assert not unknown.reset and unknown.fg is None and unknown.bg is None


def main() -> None:
    """
    Run the SGR map checks and report the outcome.

    Returns:
    `None`: Exits ``1`` on failure; prints ``PASS`` otherwise.

    """
    try:
        check_totality()
        check_key_codes()
    except AssertionError as exc:
        print(f"FAIL: {exc}")
        sys.exit(1)
    print("PASS")


if __name__ == "__main__":
    main()
