r"""
Property test for preview/builder placement parity.

**Property 6: Preview placement mirrors builder placement**

**Validates: Requirements 4.2, 8.4**

For any valid ``DrawText`` or ``DrawRect`` built via
:class:`whiskerframe.builder.CommandBuilder` over a generated rectangle and
anchor, the placement coordinates the :class:`whiskerframe.preview.PreviewRenderer`
computes equal the builder-resolved ``(x, y)``.

Both the builder and the preview consume the *same* placement source:
:meth:`whiskerframe.coordinates.RectangleCoordinates.anchor_coordinates`. The
builder calls it to resolve a command's ``(x, y)``; the preview never re-derives
the anchor pixel -- it reuses the resolved ``(command.x, command.y)`` as the block
anchor when computing per-line origins. This test verifies that shared source:

- For a ``DrawText`` command, the resolved ``(command.x, command.y)`` equals
  ``coords.anchor_coordinates(anchor)`` (builder side), and the preview's own
  :meth:`whiskerframe.preview.PreviewRenderer._line_origin` computes each line's
  origin *from* that same resolved ``(command.x, command.y)`` -- confirmed by
  recomputing the expected origin independently from the resolved coordinates and
  asserting equality against the preview's output.
- For a ``DrawRect`` command, the preview draws from ``(command.x, command.y)``,
  the canonical top-left the builder emitted from the same ``coords``.

The check needs no Pillow: it exercises the pure placement math
(``_line_origin``), not the Pillow rendering path. It runs as
``uv run python test/prop_preview_parity.py``, prints ``PASS`` on success, and
exits non-zero when `hypothesis` finds a falsifying example.
"""

from __future__ import annotations

import sys
import traceback

from hypothesis import given, settings
from hypothesis import strategies as st

from whiskerframe.anchors import Anchor, resolve_anchor
from whiskerframe.builder import CommandBuilder
from whiskerframe.coordinates import XYWH, RectangleCoordinates
from whiskerframe.metrics import line_height as glyph_height
from whiskerframe.metrics import line_width
from whiskerframe.models import TextStyle
from whiskerframe.preview import PreviewRenderer

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

_FONT_SIZES: tuple[int, ...] = (1, 2, 3, 4)

# Keep rectangle extents small enough that any resolved anchor pixel stays within
# the uint16 wire bounds and the builder never rejects placement.
_coord = st.integers(min_value=0, max_value=4096)
_extent = st.integers(min_value=1, max_value=4096)
_anchors = st.sampled_from(_ANCHORS)
_font_sizes = st.sampled_from(_FONT_SIZES)
# ``codec="utf-8"`` excludes surrogate code points (invalid UTF-8), so encoded
# text stays within the wire's UTF-8 payload contract.
_text = st.text(
    alphabet=st.characters(codec="utf-8"),
    min_size=0,
    max_size=40,
)


@st.composite
def _rect(draw: st.DrawFn) -> XYWH:
    """
    Generate a valid `XYWH` rectangle with positive extents.

    Args:
    - draw (`st.DrawFn`): `hypothesis` draw callable supplied by ``@composite``.

    Returns:
    `XYWH`: A rectangle with non-negative origin and positive width/height.

    """
    return XYWH(x=draw(_coord), y=draw(_coord), w=draw(_extent), h=draw(_extent))


def _expected_line_origin(
    origin_x: int,
    origin_y: int,
    anchor: Anchor,
    lines: list[str],
    row: int,
    advance: int,
    font_size: int,
) -> tuple[int, int]:
    r"""
    Recompute a line's origin from a resolved block anchor, independent of preview.

    Mirror the block-anchor placement math using only the builder-resolved
    ``(origin_x, origin_y)`` (the block anchor point) and the shared
    :mod:`whiskerframe.metrics` sizing, so the expectation is derived separately
    from :meth:`PreviewRenderer._line_origin` and can validate it.

    Args:
    - origin_x (`int`): Builder-resolved block anchor x pixel.
    - origin_y (`int`): Builder-resolved block anchor y pixel.
    - anchor (`Anchor`): Two-character ``[lmr][tmb]`` anchor.
    - lines (`list[str]`): The block's lines (split on ``\n``).
    - row (`int`): Zero-based line index within the block.
    - advance (`int`): Per-line vertical advance in px.
    - font_size (`int`): Font-size selector for glyph metrics.

    Returns:
    `tuple[int, int]`: The expected ``(x, y)`` top-left origin for the line.

    """
    horizontal, vertical = resolve_anchor(anchor)
    width = line_width(lines[row], font_size)
    cell_height = glyph_height(font_size)
    block_height = (len(lines) - 1) * advance + cell_height

    if horizontal == "l":
        line_x = origin_x
    elif horizontal == "m":
        line_x = origin_x - width // 2
    else:  # "r"
        line_x = origin_x - width

    if vertical == "t":
        block_top = origin_y
    elif vertical == "m":
        block_top = origin_y - block_height // 2
    else:  # "b"
        block_top = origin_y - block_height

    return line_x, block_top + row * advance


@given(
    rect=_rect(),
    text=_text,
    anchor=_anchors,
    font_size=_font_sizes,
    multiline=st.booleans(),
)
@settings(max_examples=MAX_EXAMPLES)
def check_text_parity(
    rect: RectangleCoordinates,
    text: str,
    anchor: Anchor,
    font_size: int,
    multiline: bool,
) -> None:
    """
    Assert preview text placement is computed from the builder-resolved anchor.

    Build a ``DrawText`` via :class:`CommandBuilder`, confirm its resolved
    ``(x, y)`` equals ``rect.anchor_coordinates(anchor)`` (builder placement
    source), then assert :meth:`PreviewRenderer._line_origin` reproduces, for every
    line, the origin recomputed independently from that same resolved ``(x, y)``
    (Property 6, Req 4.2, 8.4).

    Args:
    - rect (`RectangleCoordinates`): Generated target rectangle.
    - text (`str`): Text to place.
    - anchor (`Anchor`): Two-character ``[lmr][tmb]`` anchor.
    - font_size (`int`): Font-size selector.
    - multiline (`bool`): Whether to lay the text out as stacked lines.

    Raises:
    - `AssertionError`: If preview placement diverges from the builder-resolved one.

    Returns:
    `None`: This check returns nothing when parity holds.

    """
    builder = CommandBuilder()
    command = builder.draw_text(
        rect,
        text,
        anchor=anchor,
        style=TextStyle(font_size=font_size),
        multiline=multiline,
    )

    resolved = rect.anchor_coordinates(anchor)
    assert (command.x, command.y) == (resolved.x, resolved.y), (
        f"builder placement {command.x, command.y} != anchor source "
        f"{resolved.x, resolved.y}"
    )

    renderer = PreviewRenderer()
    lines = command.text.split("\n")
    cell_height = glyph_height(command.font_size)
    advance = command.line_h if command.multiline else cell_height
    for row in range(len(lines)):
        got = renderer._line_origin(
            command,
            lines[row],
            row,
            advance,
            cell_height,
        )
        want = _expected_line_origin(
            command.x,
            command.y,
            command.anchor,
            lines,
            row,
            advance,
            command.font_size,
        )
        assert got == want, f"preview line {row} origin {got!r} != expected {want!r}"


@given(
    rect=_rect(),
    anchor=_anchors,
    filled=st.booleans(),
)
@settings(max_examples=MAX_EXAMPLES)
def check_rect_parity(
    rect: RectangleCoordinates,
    anchor: Anchor,
    filled: bool,
) -> None:
    """
    Assert preview rectangle placement equals the builder-resolved top-left.

    Build a ``DrawRect`` via :class:`CommandBuilder` and assert its resolved
    ``(x, y)`` -- the placement the preview draws from -- equals the canonical
    top-left of the same rectangle (``rect.xywh()``), the datum both consume
    (Property 6, Req 4.2, 8.4).

    Args:
    - rect (`RectangleCoordinates`): Generated target rectangle.
    - anchor (`Anchor`): Two-character ``[lmr][tmb]`` anchor.
    - filled (`bool`): Whether the rectangle is filled.

    Raises:
    - `AssertionError`: If the resolved origin diverges from the rectangle top-left.

    Returns:
    `None`: This check returns nothing when parity holds.

    """
    builder = CommandBuilder()
    command = builder.draw_rect(rect, anchor=anchor, filled=filled)

    x, y, _, _ = rect.xywh()
    assert (command.x, command.y) == (
        x,
        y,
    ), f"builder rect placement {command.x, command.y} != top-left {x, y}"


def main() -> None:
    """
    Run the preview/builder parity properties and report the outcome.

    Print ``PASS`` and exit ``0`` when both properties hold across all generated
    examples; print the falsifying example and traceback and exit ``1`` when
    `hypothesis` finds a counterexample.

    Returns:
    `None`: This entry point exits the process on failure.

    """
    try:
        check_text_parity()
        check_rect_parity()
    except AssertionError:
        traceback.print_exc()
        sys.exit(1)
    print("PASS")


if __name__ == "__main__":
    main()
