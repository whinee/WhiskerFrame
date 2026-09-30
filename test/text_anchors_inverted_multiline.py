"""
Inverted multiline layout test for ``DRAW_TEXT`` (Req 9.3, 3.3, 8.3).

Build an inverted multiline ``DRAW_TEXT`` block and assert the imagesmacker 7.0.0
``inverted`` semantics:

1. The payload line order is reversed relative to the non-inverted block (Req 8.3).
2. Foreground and background colors are swapped relative to the non-inverted
   block (Req 8.3).
3. The command is flagged ``multiline`` and ``inverted`` and round-trips through
   ``serialize`` / ``decode`` to an equal ``DrawText``.

The script is pure (no hardware, no Pillow), runs as
``python test/text_anchors_inverted_multiline.py``, prints ``PASS`` on success,
and exits non-zero on the first failed assertion.
"""

from __future__ import annotations

from whiskerframe import XYXY, CommandBuilder, DrawText, TextStyle
from whiskerframe.protocol import decode, serialize

RECT: XYXY = XYXY(0, 0, 100, 60)
LINES: tuple[str, ...] = ("alpha", "beta", "gamma")
TEXT: str = "\n".join(LINES)
STYLE: TextStyle = TextStyle(color=0xF800, bg_color=0x001F)


def build(*, inverted: bool) -> DrawText:
    """
    Build a multiline text command with the shared style.

    Args:
    - inverted (`bool`): Whether to build the inverted variant.

    Returns:
    `DrawText`: The resolved multiline command.

    """
    builder = CommandBuilder()
    return builder.draw_text(
        RECT,
        TEXT,
        anchor="mm",
        style=STYLE,
        multiline=True,
        inverted=inverted,
    )


def main() -> None:
    """
    Assert reversed line order, swapped colors, and round-trip.

    Raises:
    - `AssertionError`: If any inverted-multiline expectation fails.

    Returns:
    `None`: This entry point returns nothing.

    """
    plain = build(inverted=False)
    inverted = build(inverted=True)

    assert inverted.multiline is True, "expected multiline flag set"
    assert inverted.inverted is True, "expected inverted flag set"

    # Line order reversed in the payload text vs non-inverted.
    expected_text = "\n".join(reversed(LINES))
    assert (
        inverted.text == expected_text
    ), f"line order not reversed: {inverted.text!r} != {expected_text!r}"
    assert inverted.text.split("\n") == list(reversed(LINES)), "reversal incorrect"

    # Foreground / background swapped vs non-inverted.
    assert (
        inverted.color == plain.bg_color
    ), f"fg not swapped: {inverted.color:#06x} != {plain.bg_color:#06x}"
    assert (
        inverted.bg_color == plain.color
    ), f"bg not swapped: {inverted.bg_color:#06x} != {plain.color:#06x}"

    decoded = decode(serialize(inverted))
    assert isinstance(decoded, DrawText), f"decoded {type(decoded).__name__}"
    assert decoded == inverted, f"round-trip {decoded!r} != {inverted!r}"

    print("PASS")


if __name__ == "__main__":
    main()
