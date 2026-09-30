"""
Property test for the wire-protocol serialization round trip.

**Property 1: Serialization round trip**

**Validates: Requirements 1.1**

For any valid :class:`whiskerframe.models.DrawText` or
:class:`whiskerframe.models.DrawRect` command, decoding the framed bytes produced
by :func:`whiskerframe.protocol.serialize` yields a command equal to the original,
i.e. ``decode(serialize(command)) == command``.

Commands are generated with `hypothesis` strategies that respect the wire field
bounds: coordinates, dimensions, colors, and ``line_h`` are ``uint16``
(``[0, 65535]``), ``font_size`` is ``uint8`` (``[0, 255]``), the anchor is drawn
from the nine ``[lmr][tmb]`` literals, and ``text`` is a safe UTF-8 string. The
script is pure (no hardware, no Pillow), runs as
``uv run python test/prop_serialization_roundtrip.py``, prints ``PASS`` on
success, and exits non-zero when `hypothesis` finds a falsifying example.
"""

from __future__ import annotations

import sys
import traceback

from hypothesis import given, settings
from hypothesis import strategies as st

from whiskerframe.anchors import Anchor
from whiskerframe.models import UINT8_MAX, UINT16_MAX, DrawRect, DrawText
from whiskerframe.protocol import decode, serialize

MAX_EXAMPLES: int = 400
"""Number of generated examples per property check."""

_ANCHORS: tuple[Anchor, ...] = (
    "lt",
    "mt",
    "rt",
    "lm",
    "mm",
    "rm",
    "lb",
    "mb",
    "rb",
)

_uint16 = st.integers(min_value=0, max_value=UINT16_MAX)
_uint8 = st.integers(min_value=0, max_value=UINT8_MAX)
_anchors = st.sampled_from(_ANCHORS)
# Text is decoded from UTF-8 on the wire; restrict the alphabet to characters that
# round-trip through UTF-8 (excludes lone surrogates). Length is bounded so the
# payload stays well within a frame.
_text = st.text(
    alphabet=st.characters(codec="utf-8"),
    min_size=0,
    max_size=64,
)


@st.composite
def _draw_text(draw: st.DrawFn) -> DrawText:
    """
    Generate a valid `DrawText` command respecting every wire field bound.

    Args:
    - draw (`st.DrawFn`): `hypothesis` draw callable supplied by ``@composite``.

    Returns:
    `DrawText`: A `DrawText` whose fields lie within their ``uint16`` / ``uint8``
    ranges, with an anchor from the nine literals and safe UTF-8 text.

    """
    return DrawText(
        x=draw(_uint16),
        y=draw(_uint16),
        anchor=draw(_anchors),
        color=draw(_uint16),
        bg_color=draw(_uint16),
        font_size=draw(_uint8),
        inverted=draw(st.booleans()),
        multiline=draw(st.booleans()),
        line_h=draw(_uint16),
        text=draw(_text),
    )


@st.composite
def _draw_rect(draw: st.DrawFn) -> DrawRect:
    """
    Generate a valid `DrawRect` command respecting every wire field bound.

    Args:
    - draw (`st.DrawFn`): `hypothesis` draw callable supplied by ``@composite``.

    Returns:
    `DrawRect`: A `DrawRect` whose coordinates, dimensions, and color lie within
    their ``uint16`` range.

    """
    return DrawRect(
        x=draw(_uint16),
        y=draw(_uint16),
        w=draw(_uint16),
        h=draw(_uint16),
        color=draw(_uint16),
        filled=draw(st.booleans()),
    )


_commands = st.one_of(_draw_text(), _draw_rect())


@given(command=_commands)
@settings(max_examples=MAX_EXAMPLES)
def check_round_trip(command: DrawText | DrawRect) -> None:
    """
    Assert that decoding the serialized frame reproduces the original command.

    Args:
    - command (`DrawText | DrawRect`): Generated command under test.

    Raises:
    - `AssertionError`: If ``decode(serialize(command))`` differs from ``command``.

    Returns:
    `None`: This check returns nothing when the round trip holds.

    """
    decoded = decode(serialize(command))
    assert decoded == command, f"round-trip mismatch: {decoded!r} != {command!r}"


def main() -> None:
    """
    Run the round-trip property and report the outcome.

    Print ``PASS`` and exit ``0`` when the property holds across all generated
    examples; print the falsifying example and traceback and exit ``1`` when
    `hypothesis` finds a counterexample.

    Returns:
    `None`: This entry point exits the process on failure.

    """
    try:
        check_round_trip()
    except AssertionError:
        traceback.print_exc()
        sys.exit(1)
    print("PASS")


if __name__ == "__main__":
    main()
