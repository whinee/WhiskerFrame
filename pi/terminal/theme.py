"""
Config-driven piiiiink terminal palette and a total SGR-to-RGB565 mapping.

Load the WCAG-AA-corrected piiiiink palette from ``.whiskerframe.yaml``
(``terminal.theme``) via ``scripts/config.py`` and expose it as a frozen
:class:`Theme`: the background, foreground, cursor, named accents, and the
16-colour ANSI table (RGB565). On top of the palette, :meth:`Theme.sgr_to_rgb565`
implements a **total** VT100 SGR colour mapping -- every integer code resolves to
a defined action (foreground/background change, default restore, full reset, or a
no-op for unsupported codes) and the function never raises -- so a malformed
escape sequence can never crash the emulator (field-robustness).

This module is pure: the only side effect is reading the committed config file at
load time, and it falls back to the baked-in a11y palette if the file or any key
is missing, so a fresh checkout still renders correctly. It imports no hardware
driver and no Pillow.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = [
    "DEFAULT_ANSI",
    "SgrResult",
    "Theme",
    "load_theme",
]

# Baked-in a11y fallback palette (RGB565), mirroring .whiskerframe.yaml
# terminal.theme so a fresh checkout renders even with no config present.
_FALLBACK_BG: int = 0x18C5
_FALLBACK_FG: int = 0xFD9C
_FALLBACK_CURSOR: int = 0x2EDF
_FALLBACK_ACCENTS: dict[str, int] = {
    "pink": 0xFB7A,
    "purple": 0xBD5F,
    "blue": 0x8CDF,
}

DEFAULT_ANSI: tuple[int, ...] = (
    0x8C76,  # 0 black
    0xFB4D,  # 1 red
    0x4EB4,  # 2 green
    0xFE8C,  # 3 yellow
    0x7D1F,  # 4 blue
    0xFBFC,  # 5 magenta
    0x4F1F,  # 6 cyan
    0xE73E,  # 7 white
    0xB5BA,  # 8 bright black
    0xFC71,  # 9 bright red
    0x6F97,  # 10 bright green
    0xFF11,  # 11 bright yellow
    0xA61F,  # 12 bright blue
    0xFCFD,  # 13 bright magenta
    0x877F,  # 14 bright cyan
    0xFFFF,  # 15 bright white
)
"""The a11y-corrected 16-colour ANSI table (RGB565), used when config lacks one."""

_SGR_RESET: int = 0
_SGR_BOLD: int = 1
_SGR_DEFAULT_FG: int = 39
_SGR_DEFAULT_BG: int = 49
_FG_NORMAL_BASE: int = 30  # 30..37 -> ansi 0..7
_FG_BRIGHT_BASE: int = 90  # 90..97 -> ansi 8..15
_BG_NORMAL_BASE: int = 40  # 40..47 -> ansi 0..7
_BG_BRIGHT_BASE: int = 100  # 100..107 -> ansi 8..15
_ANSI_SPAN: int = 8


@dataclass(frozen=True)
class SgrResult:
    """
    The effect of a single SGR code on the current foreground/background.

    A code may request a full reset (both colours back to the theme defaults), a
    foreground change, a background change, or none of these (an unsupported or
    purely-stylistic code such as bold). The emulator applies the deltas it finds
    and honours ``reset`` first.

    Attributes:
    - reset (`bool`): Whether to reset both colours to the theme defaults.
    - fg (`int | None`): New RGB565 foreground, or ``None`` to leave it unchanged.
    - bg (`int | None`): New RGB565 background, or ``None`` to leave it unchanged.

    """

    reset: bool = False
    fg: int | None = None
    bg: int | None = None


@dataclass(frozen=True)
class Theme:
    """
    The resolved piiiiink terminal palette (RGB565) and SGR colour mapping.

    Hold the terminal's background, foreground, and cursor colours, the named
    accent colours, and the 16-entry ANSI table, all as RGB565 ``uint16`` values.
    Construct via :func:`load_theme` (config-driven) rather than directly.

    Attributes:
    - bg (`int`): RGB565 background (default terminal background).
    - fg (`int`): RGB565 foreground (default terminal text colour).
    - cursor (`int`): RGB565 cursor colour.
    - accents (`Mapping[str, int]`): Named RGB565 accent colours.
    - ansi (`tuple[int, ...]`): The 16 RGB565 ANSI colours (0-7 then 8-15).

    """

    bg: int
    fg: int
    cursor: int
    accents: Mapping[str, int]
    ansi: tuple[int, ...]

    def _fg_change(self, code: int) -> SgrResult | None:
        """
        Resolve an SGR code that sets the foreground colour, if any.

        Args:
        - code (`int`): The SGR parameter code.

        Returns:
        `SgrResult | None`: A foreground delta, or ``None`` if ``code`` is not a
        foreground-setting code.

        """
        if _FG_NORMAL_BASE <= code < _FG_NORMAL_BASE + _ANSI_SPAN:
            return SgrResult(fg=self.ansi[code - _FG_NORMAL_BASE])
        if _FG_BRIGHT_BASE <= code < _FG_BRIGHT_BASE + _ANSI_SPAN:
            return SgrResult(fg=self.ansi[code - _FG_BRIGHT_BASE + _ANSI_SPAN])
        return None

    def _bg_change(self, code: int) -> SgrResult | None:
        """
        Resolve an SGR code that sets the background colour, if any.

        Args:
        - code (`int`): The SGR parameter code.

        Returns:
        `SgrResult | None`: A background delta, or ``None`` if ``code`` is not a
        background-setting code.

        """
        if _BG_NORMAL_BASE <= code < _BG_NORMAL_BASE + _ANSI_SPAN:
            return SgrResult(bg=self.ansi[code - _BG_NORMAL_BASE])
        if _BG_BRIGHT_BASE <= code < _BG_BRIGHT_BASE + _ANSI_SPAN:
            return SgrResult(bg=self.ansi[code - _BG_BRIGHT_BASE + _ANSI_SPAN])
        return None

    def sgr_to_rgb565(
        self,
        code: int,
        default_fg: int,
        default_bg: int,
    ) -> SgrResult:
        """
        Map a single VT100 SGR code to a foreground/background colour change.

        This mapping is **total**: every integer resolves to a defined
        `SgrResult` and the function never raises. Code ``0`` resets both colours
        to the theme defaults; ``30``-``37``/``90``-``97`` set the foreground from
        the ANSI table; ``40``-``47``/``100``-``107`` set the background; ``39``
        and ``49`` restore the default foreground/background; every other code
        (including bold ``1``) is a no-op (an `SgrResult` with no deltas).

        Args:
        - code (`int`): The SGR parameter code to map.
        - default_fg (`int`): RGB565 foreground to restore on reset / code 39.
        - default_bg (`int`): RGB565 background to restore on reset / code 49.

        Returns:
        `SgrResult`: The resulting colour change (possibly a no-op).

        """
        constant = {
            _SGR_RESET: SgrResult(reset=True, fg=default_fg, bg=default_bg),
            _SGR_DEFAULT_FG: SgrResult(fg=default_fg),
            _SGR_DEFAULT_BG: SgrResult(bg=default_bg),
        }.get(code)
        if constant is not None:
            return constant
        return self._fg_change(code) or self._bg_change(code) or SgrResult()


def _load_yaml_config() -> dict[str, Any]:
    """
    Load ``.whiskerframe.yaml`` via ``scripts/config.py`` with a safe fallback.

    Mirror the Pi daemon import convention: ``scripts/`` sits two levels up from
    ``pi/terminal/`` under the deploy root, so its parent is added to
    ``sys.path`` to reuse the project ``load_yaml_config``. Any failure returns
    an empty mapping so the theme falls back entirely to the baked-in palette.

    Returns:
    `dict[str, Any]`: The parsed configuration mapping (empty on any failure).

    """
    scripts_dir = Path(__file__).resolve().parent.parent.parent / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    try:
        from config import load_yaml_config  # type: ignore[import-not-found]
    except ImportError:
        return {}
    loaded = load_yaml_config()
    return loaded if isinstance(loaded, dict) else {}


def _coerce_int(value: Any, fallback: int) -> int:
    """
    Coerce a config value to an ``int``, falling back on failure.

    Args:
    - value (`Any`): The raw config value (``int`` or hex/decimal string).
    - fallback (`int`): Value to use when coercion fails.

    Returns:
    `int`: The coerced colour value or the fallback.

    """
    if isinstance(value, bool):
        return fallback
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value, 0)
        except ValueError:
            return fallback
    return fallback


def _resolve_ansi(raw: Any) -> tuple[int, ...]:
    """
    Resolve the 16-colour ANSI table from a raw config value.

    Accept the configured list only when it holds all 16 entries; otherwise fall
    back to :data:`DEFAULT_ANSI`. Individual entries are coerced to ``int``.

    Args:
    - raw (`Any`): The raw ``terminal.theme.ansi`` config value.

    Returns:
    `tuple[int, ...]`: The 16-entry RGB565 ANSI table.

    """
    if isinstance(raw, list) and len(raw) == len(DEFAULT_ANSI):
        return tuple(
            _coerce_int(entry, DEFAULT_ANSI[index]) for index, entry in enumerate(raw)
        )
    return DEFAULT_ANSI


def load_theme(config: Mapping[str, Any] | None = None) -> Theme:
    """
    Build the terminal `Theme` from ``terminal.theme`` config with a11y fallbacks.

    Read the palette from the supplied ``config`` mapping (or load
    ``.whiskerframe.yaml`` when ``None``), falling back to the baked-in
    a11y-corrected piiiiink palette for any missing key so a fresh checkout still
    renders. Colour values may be ints or hex strings in the config.

    Args:
    - config (`Mapping[str, Any] | None`, optional): A pre-loaded config mapping. Defaults to loading ``.whiskerframe.yaml``.

    Returns:
    `Theme`: The resolved RGB565 palette and SGR mapping.

    """
    source = _load_yaml_config() if config is None else dict(config)
    terminal = source.get("terminal") if isinstance(source, dict) else None
    theme_cfg = terminal.get("theme") if isinstance(terminal, dict) else None
    if not isinstance(theme_cfg, dict):
        theme_cfg = {}
    accents = {
        "pink": _coerce_int(theme_cfg.get("accent_pink"), _FALLBACK_ACCENTS["pink"]),
        "purple": _coerce_int(
            theme_cfg.get("accent_purple"),
            _FALLBACK_ACCENTS["purple"],
        ),
        "blue": _coerce_int(theme_cfg.get("accent_blue"), _FALLBACK_ACCENTS["blue"]),
    }
    return Theme(
        bg=_coerce_int(theme_cfg.get("bg"), _FALLBACK_BG),
        fg=_coerce_int(theme_cfg.get("fg"), _FALLBACK_FG),
        cursor=_coerce_int(theme_cfg.get("cursor"), _FALLBACK_CURSOR),
        accents=accents,
        ansi=_resolve_ansi(theme_cfg.get("ansi")),
    )
