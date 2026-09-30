"""
Multiline layout and round-trip test for ``DRAW_TEXT`` (Req 9.2).

Build a multiline ``DRAW_TEXT`` block over a known rectangle and assert:

1. The command is flagged ``multiline`` and its ``line_h`` equals the expected
   per-line advance from the font metrics table (Req 3.3).
2. The (non-inverted) line ordering is preserved in the payload text.
3. ``serialize`` followed by ``decode`` round-trips to an equal ``DrawText``.

The script is pure (no hardware, no Pillow), runs as
``python test/text_anchors_multiline.py``, prints ``PASS`` on success, and exits
non-zero on the first failed assertion.
"""

from __future__ import annotations

from whiskerframe import XYXY, CommandBuilder, DrawText
from whiskerframe.metrics import DEFAULT_FONT_SIZE, line_advance
from whiskerframe.protocol import decode, serialize

RECT: XYXY = XYXY(0, 0, 100, 60)
LINES: tuple[str, ...] = ("alpha", "beta", "gamma")
TEXT: str = "\n".join(LINES)


def build() -> DrawText:
    """
    Build the non-inverted multiline text command under test.

    Returns:
    `DrawText`: The resolved multiline command.

    """
    builder = CommandBuilder()
    return builder.draw_text(RECT, TEXT, anchor="mm", multiline=True)


def main() -> None:
    """
    Assert multiline flag, line height, ordering, and round-trip.

    Raises:
    - `AssertionError`: If any multiline expectation fails.

    Returns:
    `None`: This entry point returns nothing.

    """
    command = build()

    assert command.multiline is True, "expected multiline flag set"

    expected_advance = line_advance(DEFAULT_FONT_SIZE)
    assert (
        command.line_h == expected_advance
    ), f"line_h {command.line_h} != {expected_advance}"

    # Non-inverted: line order preserved.
    assert command.text == TEXT, f"line order changed: {command.text!r} != {TEXT!r}"
    assert command.text.split("\n") == list(LINES), "line ordering not preserved"
    assert command.inverted is False, "expected non-inverted command"

    decoded = decode(serialize(command))
    assert isinstance(decoded, DrawText), f"decoded {type(decoded).__name__}"
    assert decoded == command, f"round-trip {decoded!r} != {command!r}"

    print("PASS")


if __name__ == "__main__":
    main()
