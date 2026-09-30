"""
Property test asserting a serialized command is never a full framebuffer.

**Property 2: Command payload is not a framebuffer**

**Validates: Requirements 1.5**

For any valid :class:`whiskerframe.models.DrawText` or
:class:`whiskerframe.models.DrawRect` command, the serialized frame length is far
below a full-display bitmap size (320 x 240 x 2 bytes = 153600 B for the ILI9341
in RGB565), so the serial command path never carries a full framebuffer.

Commands are generated with `hypothesis` strategies that respect the wire field
bounds: coordinates, dimensions, colors, and ``line_h`` are ``uint16``
(``[0, 65535]``), ``font_size`` is ``uint8`` (``[0, 255]``), the anchor is drawn
from the nine ``[lmr][tmb]`` literals, and ``text`` is a safe UTF-8 string of
bounded length. The script is pure (no hardware, no Pillow), runs as
``uv run python test/prop_non_framebuffer.py``, prints ``PASS`` on success, and
exits non-zero when `hypothesis` finds a falsifying example.
"""

from __future__ import annotations

import sys
import traceback

from hypothesis import given, settings
from hypothesis import strategies as st

from whiskerframe.anchors import Anchor
from whiskerframe.models import UINT8_MAX, UINT16_MAX, DrawRect, DrawText
from whiskerframe.protocol import serialize

MAX_EXAMPLES: int = 400
"""Number of generated examples per property check."""

DISPLAY_WIDTH: int = 320
"""ILI9341 display width in pixels."""

DISPLAY_HEIGHT: int = 240
"""ILI9341 display height in pixels."""

BYTES_PER_PIXEL: int = 2
"""RGB565 bytes per pixel."""

FRAMEBUFFER_BYTES: int = DISPLAY_WIDTH * DISPLAY_HEIGHT * BYTES_PER_PIXEL
"""Full-display RGB565 framebuffer size in bytes (153600)."""

# A generous ceiling that stays an order of magnitude under a full framebuffer:
# bounded-length text plus the fixed headers and framing can never approach this.
MAX_COMMAND_BYTES: int = FRAMEBUFFER_BYTES // 10
"""Upper bound a valid command frame must stay below (Req 1.5)."""

_MAX_TEXT_CHARS: int = 256
"""Bounded text length keeping a `DrawText` frame far below a framebuffer."""

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
_text = st.text(
    alphabet=st.characters(codec="utf-8"),
    min_size=0,
    max_size=_MAX_TEXT_CHARS,
)


@st.composite
def _draw_text(draw: st.DrawFn) -> DrawText:
    """
    Generate a valid `DrawText` command with bounded-length UTF-8 text.

    Args:
    - draw (`st.DrawFn`): `hypothesis` draw callable supplied by ``@composite``.

    Returns:
    `DrawText`: A `DrawText` whose fields lie within their ``uint16`` / ``uint8``
    ranges, with an anchor from the nine literals and bounded safe UTF-8 text.

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
def check_non_framebuffer(command: DrawText | DrawRect) -> None:
    """
    Assert the serialized frame is far below a full framebuffer size.

    Args:
    - command (`DrawText | DrawRect`): Generated command under test.

    Raises:
    - `AssertionError`: If the serialized frame reaches the non-framebuffer bound.

    Returns:
    `None`: This check returns nothing when the size bound holds.

    """
    size = len(serialize(command))
    assert size < MAX_COMMAND_BYTES, (
        f"serialized frame {size} B not far below framebuffer "
        f"{FRAMEBUFFER_BYTES} B (bound {MAX_COMMAND_BYTES} B)"
    )


def main() -> None:
    """
    Run the non-framebuffer property and report the outcome.

    Print ``PASS`` and exit ``0`` when the property holds across all generated
    examples; print the falsifying example and traceback and exit ``1`` when
    `hypothesis` finds a counterexample.

    Returns:
    `None`: This entry point exits the process on failure.

    """
    try:
        check_non_framebuffer()
    except AssertionError:
        traceback.print_exc()
        sys.exit(1)
    print("PASS")


if __name__ == "__main__":
    main()
