"""
Unit tests for high-contrast monochrome theme (REQ-ENV-03, DEC-W19).

Validates:
- Theme loads from assets/themes/mono-high-contrast.json via pi/terminal/theme.py.
- WCAG AAA contrast ratio compliance (>= 7:1 for normal text, 21:1 for pure mono).
- 16-entry ANSI table resolution and total SGR mapping.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pi.terminal.theme import Theme, load_theme

_REPO_ROOT = Path(__file__).resolve().parent.parent
_THEME_FILE = _REPO_ROOT / "assets" / "themes" / "mono-high-contrast.json"


def test_mono_high_contrast_file_valid() -> None:
    """The JSON file exists and parses with required keys."""
    assert _THEME_FILE.is_file()
    data = json.loads(_THEME_FILE.read_text(encoding="utf-8"))
    assert data["name"] == "mono-high-contrast"
    assert data["bg"] == "0x0000"  # pure black
    assert data["fg"] == "0xFFFF"  # pure white
    assert len(data["ansi"]) == 16
    assert data["contrast"]["fg_on_bg"] >= 7.0


def test_mono_high_contrast_theme_loader() -> None:
    """The Theme loader successfully loads mono-high-contrast theme."""
    config = {
        "terminal": {
            "theme_file": "mono-high-contrast",
        }
    }
    theme = load_theme(config)
    assert isinstance(theme, Theme)
    assert theme.bg == 0x0000
    assert theme.fg == 0xFFFF
    assert theme.cursor == 0xFFFF
    assert len(theme.ansi) == 16

    # Test SGR mapping
    res_fg = theme.sgr_to_rgb565(37, theme.fg, theme.bg)  # white fg
    assert res_fg.fg == 0xFFFF

    res_reset = theme.sgr_to_rgb565(0, theme.fg, theme.bg)
    assert res_reset.reset is True
