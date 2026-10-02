"""
Property test for the new terminal wire ops' serialization round trip.

**Validates: Requirements (cyd-terminal design: new wire ops)**

For any valid :class:`whiskerframe.terminal.DrawCells`, :class:`~.Scroll`, or
:class:`~.DrawImage` command, decoding the framed bytes produced by
:func:`whiskerframe.protocol.serialize` yields a command equal to the original,
i.e. ``decode(serialize(command)) == command``. The `Scroll` strategy covers the
full signed ``int8`` range (including negatives) to exercise the signed row
count, and `DrawImage` generates ``data`` of exactly ``w * h * 2`` RGB565 bytes.

The script is pure (no hardware, no Pillow), runs as
``uv run python test/prop_terminal_protocol.py``, prints ``PASS`` on success, and
exits non-zero when `hypothesis` finds a counterexample.
"""

from __future__ import annotations

import sys
import traceback

from hypothesis import given, settings
from hypothesis import strategies as st

from whiskerframe.models import UINT8_MAX, UINT16_MAX
from whiskerframe.protocol import decode, serialize
from whiskerframe.terminal import INT8_MAX, INT8_MIN, DrawCells, DrawImage, Scroll

MAX_EXAMPLES: int = 300
"""Number of generated examples per property check."""

_uint16 = st.integers(min_value=0, max_value=UINT16_MAX)
_uint8 = st.integers(min_value=0, max_value=UINT8_MAX)
_int8 = st.integers(min_value=INT8_MIN, max_value=INT8_MAX)
# Cell text is one byte per cell (latin-1 round-trips the full 0..255 range).
_cell_text = st.text(
    alphabet=st.characters(min_codepoint=0, max_codepoint=0xFF),
    min_size=0,
    max_size=64,
)


@st.composite
def _draw_cells(draw: st.DrawFn) -> DrawCells:
    """
    Generate a valid `DrawCells` within every wire field bound.

    Args:
    - draw (`st.DrawFn`): `hypothesis` draw callable supplied by ``@composite``.

    Returns:
    `DrawCells`: A command with ``uint16`` coords/colors and ``uint8`` font size.

    """
    return DrawCells(
        col=draw(_uint16),
        row=draw(_uint16),
        fg=draw(_uint16),
        bg=draw(_uint16),
        font_size=draw(_uint8),
        text=draw(_cell_text),
    )


@st.composite
def _scroll(draw: st.DrawFn) -> Scroll:
    """
    Generate a valid `Scroll` with a signed ``int8`` row count.

    Args:
    - draw (`st.DrawFn`): `hypothesis` draw callable supplied by ``@composite``.

    Returns:
    `Scroll`: A command whose ``rows`` spans the signed ``int8`` range.

    """
    return Scroll(
        rows=draw(_int8),
        fill=draw(_uint16),
        top=draw(_uint16),
        bottom=draw(_uint16),
    )


@st.composite
def _draw_image(draw: st.DrawFn) -> DrawImage:
    """
    Generate a valid `DrawImage` with ``data`` sized to ``w * h * 2``.

    Dimensions are kept small so the payload stays within a single frame.

    Args:
    - draw (`st.DrawFn`): `hypothesis` draw callable supplied by ``@composite``.

    Returns:
    `DrawImage`: A command carrying a correctly sized RGB565 pixel block.

    """
    w = draw(st.integers(min_value=0, max_value=16))
    h = draw(st.integers(min_value=0, max_value=16))
    data = draw(st.binary(min_size=w * h * 2, max_size=w * h * 2))
    return DrawImage(x=draw(_uint16), y=draw(_uint16), w=w, h=h, data=data)


_commands = st.one_of(_draw_cells(), _scroll(), _draw_image())


@given(command=_commands)
@settings(max_examples=MAX_EXAMPLES)
def check_round_trip(command: DrawCells | Scroll | DrawImage) -> None:
    """
    Assert that decoding the serialized frame reproduces the command.

    Args:
    - command (`DrawCells | Scroll | DrawImage`): Generated command under test.

    Raises:
    - `AssertionError`: If ``decode(serialize(command))`` differs from the input.

    Returns:
    `None`: Returns nothing when the round trip holds.

    """
    decoded = decode(serialize(command))
    assert decoded == command, f"round-trip mismatch: {decoded!r} != {command!r}"


def main() -> None:
    """
    Run the round-trip property and report the outcome.

    Returns:
    `None`: Exits ``1`` on a counterexample; prints ``PASS`` otherwise.

    """
    try:
        check_round_trip()
    except AssertionError:
        traceback.print_exc()
        sys.exit(1)
    print("PASS")


if __name__ == "__main__":
    main()
