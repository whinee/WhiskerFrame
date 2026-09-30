r"""
Property test for multiline text stacking and inversion.

**Property 5: Multiline layout stacks lines by line height under the block anchor**

*For any* multiline text (lines joined by ``\n``), *any* of the nine
``[lmr][tmb]`` anchors, and *any* positive line height, ``CommandBuilder.draw_text``
built with ``multiline=True`` satisfies:

- ``line_h`` equals the supplied ``line_height`` when given, or the font's default
  :func:`whiskerframe.metrics.line_advance` when ``line_height`` is ``None``.
- Without inversion the payload preserves the original line order.
- With ``inverted=True`` the payload reverses the line order *and* swaps the
  foreground and background colors, matching the imagesmacker 7.0.0 ``inverted``
  semantics.

The rectangle spans the full ``uint16`` range so every anchor resolves in bounds.
The script is pure (no hardware, no Pillow), runs as
``uv run python test/prop_multiline_stacking.py``, prints ``PASS`` on success, and
exits non-zero on the first falsifying example.

**Validates: Requirements 3.3, 8.3**
"""

from __future__ import annotations

import sys

from hypothesis import given, settings
from hypothesis import strategies as st

from whiskerframe import XYXY, CommandBuilder
from whiskerframe.anchors import Anchor
from whiskerframe.metrics import line_advance
from whiskerframe.models import TextStyle

UINT16_MAX: int = 0xFFFF
FG: int = 0xF800  # RGB565 red
BG: int = 0x001F  # RGB565 blue

ANCHORS: tuple[Anchor, ...] = (
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

# Short single-line fragments (no embedded newlines) joined into a block.
_line = st.text(
    alphabet=st.characters(blacklist_characters="\n"),
    min_size=0,
    max_size=8,
)
_lines = st.lists(_line, min_size=1, max_size=6)


@settings(max_examples=400)
@given(
    lines=_lines,
    anchor=st.sampled_from(ANCHORS),
    line_height=st.one_of(st.none(), st.integers(min_value=1, max_value=UINT16_MAX)),
    inverted=st.booleans(),
)
def test_multiline_stacking(
    lines: list[str],
    anchor: Anchor,
    line_height: int | None,
    *,
    inverted: bool,
) -> None:
    r"""
    Assert line-height resolution and inversion semantics for a multiline block.

    Args:
    - lines (`list[str]`): Non-empty list of newline-free line fragments.
    - anchor (`Anchor`): Two-character ``[lmr][tmb]`` anchor under test.
    - line_height (`int | None`): Explicit per-line advance, or ``None`` for default.
    - inverted (`bool`): Whether to reverse line order and swap fg/bg.

    Raises:
    - `AssertionError`: If line height, line order, or color swap is wrong.

    Returns:
    `None`: This property returns nothing when it holds.

    """
    text = "\n".join(lines)
    style = TextStyle(color=FG, bg_color=BG)
    builder = CommandBuilder()
    rect = XYXY(0, 0, UINT16_MAX, UINT16_MAX)

    command = builder.draw_text(
        rect,
        text,
        anchor=anchor,
        style=style,
        multiline=True,
        line_height=line_height,
        inverted=inverted,
    )

    expected_advance = (
        line_advance(style.font_size) if line_height is None else line_height
    )
    assert (
        command.line_h == expected_advance
    ), f"line_h {command.line_h} != {expected_advance}"
    assert command.multiline is True, "multiline flag not set"

    payload_lines = command.text.split("\n")
    if inverted:
        reversed_lines = list(reversed(lines))
        assert (
            payload_lines == reversed_lines
        ), f"inverted order {payload_lines} != {reversed_lines}"
        assert command.color == BG, f"inverted fg {command.color:#06x} != {BG:#06x}"
        assert (
            command.bg_color == FG
        ), f"inverted bg {command.bg_color:#06x} != {FG:#06x}"
        assert command.inverted is True, "inverted flag not set"
    else:
        assert payload_lines == lines, f"order {payload_lines} != {lines}"
        assert command.color == FG, f"fg {command.color:#06x} != {FG:#06x}"
        assert command.bg_color == BG, f"bg {command.bg_color:#06x} != {BG:#06x}"


def main() -> None:
    """
    Run the multiline-stacking property and report success.

    Returns:
    `None`: This entry point returns nothing.

    """
    test_multiline_stacking()
    print("PASS")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as exc:
        print(f"FAIL: {exc}")
        sys.exit(1)
