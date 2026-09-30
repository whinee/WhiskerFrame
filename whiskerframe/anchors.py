"""
Anchor primitives mirroring the imagesmacker 7.0.0 anchor model.

An anchor is a two-character string following the ``[lmr][tmb]`` grammar: the
first character selects the horizontal alignment (``l`` left, ``m`` middle,
``r`` right) and the second selects the vertical alignment (``t`` top, ``m``
middle, ``b`` bottom). This matches imagesmacker 7.0.0's
``Literal['lt', 'mt', 'rt', 'lm', 'mm', 'rm', 'lb', 'mb', 'rb']`` with the
default anchor ``"mm"`` (center). This module is pure: it imports no imaging
library and performs only string validation and decomposition.
"""

from __future__ import annotations

from typing import Literal

Anchor = Literal["lt", "mt", "rt", "lm", "mm", "rm", "lb", "mb", "rb"]
"""Two-character anchor string in the ``[lmr][tmb]`` grammar.

Strict parity with imagesmacker 7.0.0's anchor ``Literal``. The nine members
are every combination of a horizontal key (``l``/``m``/``r``) with a vertical
key (``t``/``m``/``b``).
"""

HorizontalKey = Literal["l", "m", "r"]
"""Horizontal alignment key: ``l`` (left), ``m`` (middle), or ``r`` (right)."""

VerticalKey = Literal["t", "m", "b"]
"""Vertical alignment key: ``t`` (top), ``m`` (middle), or ``b`` (bottom)."""

DEFAULT_ANCHOR: Anchor = "mm"
"""Default anchor (center), matching the imagesmacker 7.0.0 default of ``"mm"``."""

_HORIZONTAL_KEYS: frozenset[str] = frozenset({"l", "m", "r"})
_VERTICAL_KEYS: frozenset[str] = frozenset({"t", "m", "b"})


def validate_anchor(anchor: str = DEFAULT_ANCHOR) -> Anchor:
    """
    Validate a two-character anchor string against the ``[lmr][tmb]`` grammar.

    Enforce the imagesmacker 7.0.0 anchor model: the anchor must be exactly two
    characters, with a horizontal key in ``{l, m, r}`` followed by a vertical
    key in ``{t, m, b}``. The default ``"mm"`` (center) is returned unchanged.

    Args:
    - anchor (`str`, optional): Two-character anchor specification string. Defaults to `"mm"`.

    Raises:
    - `ValueError`: If the anchor length is not 2, or either character is not a valid key.

    Returns:
    `Anchor`: The validated anchor string, narrowed to the `Anchor` literal type.

    """
    if len(anchor) != 2:
        msg = f"Anchor must be exactly 2 characters, got {anchor!r} (length {len(anchor)})."
        raise ValueError(msg)

    horizontal, vertical = anchor[0], anchor[1]
    if horizontal not in _HORIZONTAL_KEYS:
        msg = (
            f"Invalid horizontal anchor key {horizontal!r} in {anchor!r}; "
            "expected one of 'l', 'm', 'r'."
        )
        raise ValueError(msg)
    if vertical not in _VERTICAL_KEYS:
        msg = (
            f"Invalid vertical anchor key {vertical!r} in {anchor!r}; "
            "expected one of 't', 'm', 'b'."
        )
        raise ValueError(msg)

    return anchor  # type: ignore[return-value]


def resolve_anchor(anchor: str = DEFAULT_ANCHOR) -> tuple[HorizontalKey, VerticalKey]:
    """
    Validate an anchor and decompose it into its horizontal and vertical keys.

    Validate the anchor via `validate_anchor`, then split it into the horizontal
    key (``l``/``m``/``r``) and vertical key (``t``/``m``/``b``) used to select
    left/center/right and top/middle/bottom coordinates during placement.

    Args:
    - anchor (`str`, optional): Two-character anchor specification string. Defaults to `"mm"`.

    Raises:
    - `ValueError`: If the anchor length is not 2, or either character is not a valid key.

    Returns:
    `tuple[HorizontalKey, VerticalKey]`: The ``(horizontal, vertical)`` key pair.

    """
    validated = validate_anchor(anchor)
    horizontal: HorizontalKey = validated[0]  # type: ignore[assignment]
    vertical: VerticalKey = validated[1]  # type: ignore[assignment]
    return horizontal, vertical
