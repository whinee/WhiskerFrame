r"""
Property test for the frame decoder's recover-and-discard behavior.

**Property 3: Decoder recovers all valid frames and discards the rest**

**Validates: Requirements 1.4**

For any byte stream formed by interleaving valid frames (produced by
:func:`whiskerframe.protocol.serialize`) with arbitrary corrupted or garbage
bytes, the frame decoder emits exactly the valid frames in their original order
and discards everything else.

This module contains a pure-Python port of the C++ ``cyd_display_link::FrameDecoder``
state machine defined in ``firmware/cyd_display_link/frame.h``. It is a *host-side
model* of the firmware decoder: a byte-at-a-time ``HuntSOF -> ReadLen0 -> ReadLen1
-> ReadBody -> ReadCRC`` state machine that discards the in-progress frame and
resynchronizes to the next SOF on a bad CRC, an unknown opcode, or a ``LEN`` of
zero or greater than the ~2 KB cap (:data:`MAX_FRAME_LEN`). The model mirrors the
firmware logic so this test can exercise the recover-and-discard contract without
a C++ toolchain; the firmware header remains the source of truth and this port
must track it.

The generator interleaves ``serialize()`` output for random valid commands with
random garbage byte runs (garbage never introduces a spurious valid frame in
practice; the decoder validates SOF + LEN + CRC + opcode, so unrelated bytes are
discarded). The test asserts the decoder emits exactly the original valid frames'
``(opcode, payload)`` in order. It is pure (no hardware, no Pillow), runs as
``uv run python test/prop_decoder_recovery.py``, prints ``PASS`` on success, and
exits non-zero when `hypothesis` finds a falsifying example.
"""

from __future__ import annotations

import sys
import traceback
from collections.abc import Callable
from enum import Enum, auto
from typing import ClassVar

from hypothesis import given, settings
from hypothesis import strategies as st

from whiskerframe.anchors import Anchor
from whiskerframe.models import UINT8_MAX, UINT16_MAX, DrawRect, DrawText
from whiskerframe.protocol import (
    OPCODE_DRAW_RECT,
    OPCODE_DRAW_TEXT,
    SOF,
    crc8,
    serialize,
)

MAX_EXAMPLES: int = 300
"""Number of generated examples per property check."""

MAX_FRAME_LEN: int = 2048
"""``LEN`` cap mirroring firmware ``cyd_display_link::kMaxFrameLen`` (~2 KB)."""

_KNOWN_OPCODES: frozenset[int] = frozenset(
    {OPCODE_DRAW_TEXT, OPCODE_DRAW_RECT, 0x10, 0x1F},
)
"""Opcodes the firmware dispatches; unknown opcodes cause a frame discard (Req 1.4)."""


class _State(Enum):
    """Decoder states mirroring firmware ``FrameDecoder::State``."""

    HUNT_SOF = auto()
    READ_LEN0 = auto()
    READ_LEN1 = auto()
    READ_BODY = auto()
    READ_CRC = auto()


class FrameDecoderModel:
    """
    Pure-Python port of the C++ ``cyd_display_link::FrameDecoder`` state machine.

    Feed received bytes one at a time via :meth:`feed`; each call returns the
    completed ``(opcode, payload)`` tuple exactly once per valid frame, or `None`
    otherwise. On a bad CRC, an unknown opcode, or a ``LEN`` of zero or exceeding
    :data:`MAX_FRAME_LEN`, the in-progress frame is discarded and the decoder
    resynchronizes to :data:`_State.HUNT_SOF` (Req 1.4). This is a host-side model
    of the firmware header ``firmware/cyd_display_link/frame.h``, not the firmware
    itself; the header remains the source of truth.
    """

    def __init__(self) -> None:
        """
        Initialize the decoder in the ``HUNT_SOF`` state.

        Returns:
        `None`: This initializer does not return a value.

        """
        self._state: _State = _State.HUNT_SOF
        self._len: int = 0
        self._body: bytearray = bytearray()

    def _reset(self) -> None:
        """
        Return to hunting for the next SOF, discarding any in-progress frame.

        Returns:
        `None`: This method resets internal state and returns nothing.

        """
        self._state = _State.HUNT_SOF
        self._len = 0
        self._body = bytearray()

    def feed(self, byte: int) -> tuple[int, bytes] | None:
        """
        Feed a single received byte into the state machine.

        Mirror the firmware ``feed()``: skip non-SOF bytes while hunting, assemble
        the little-endian ``LEN``, accumulate ``LEN`` body bytes, then validate the
        trailing CRC8 and opcode. Return the completed ``(opcode, payload)`` once
        per valid frame; discard and resync (returning `None`) on a bad CRC, an
        unknown opcode, or an out-of-range ``LEN`` (Req 1.4).

        Args:
        - byte (`int`): One received byte in ``[0, 255]``.

        Returns:
        `tuple[int, bytes] | None`: The completed ``(opcode, payload)`` when a
        valid frame finishes on this byte, else `None`.

        """
        handler = self._HANDLERS[self._state]
        return handler(self, byte)

    def _feed_hunt_sof(self, byte: int) -> tuple[int, bytes] | None:
        """
        Handle a byte while hunting for the SOF marker; skip anything else.

        Args:
        - byte (`int`): One received byte in ``[0, 255]``.

        Returns:
        `tuple[int, bytes] | None`: Always `None`; hunting completes no frame.

        """
        if byte == SOF:
            self._state = _State.READ_LEN0
        return None

    def _feed_len0(self, byte: int) -> tuple[int, bytes] | None:
        """
        Store the ``LEN`` low byte and advance to reading the high byte.

        Args:
        - byte (`int`): The ``LEN`` low byte.

        Returns:
        `tuple[int, bytes] | None`: Always `None`; reading ``LEN`` completes no frame.

        """
        self._len = byte
        self._state = _State.READ_LEN1
        return None

    def _feed_len1(self, byte: int) -> tuple[int, bytes] | None:
        """
        Complete the little-endian ``LEN`` and validate it against the cap.

        Discard and resync on a ``LEN`` of zero or greater than
        :data:`MAX_FRAME_LEN`; otherwise begin body accumulation (Req 1.4).

        Args:
        - byte (`int`): The ``LEN`` high byte.

        Returns:
        `tuple[int, bytes] | None`: Always `None`; reading ``LEN`` completes no frame.

        """
        self._len |= byte << 8
        if self._len == 0 or self._len > MAX_FRAME_LEN:
            self._reset()
        else:
            self._body = bytearray()
            self._state = _State.READ_BODY
        return None

    def _feed_body(self, byte: int) -> tuple[int, bytes] | None:
        """
        Accumulate an ``OPCODE + PAYLOAD`` byte until ``LEN`` bytes are present.

        Args:
        - byte (`int`): One body byte.

        Returns:
        `tuple[int, bytes] | None`: Always `None`; the CRC phase completes the frame.

        """
        self._body.append(byte)
        if len(self._body) >= self._len:
            self._state = _State.READ_CRC
        return None

    def _feed_crc(self, byte: int) -> tuple[int, bytes] | None:
        """
        Validate the trailing CRC8 and opcode, emitting a frame or discarding.

        Emit ``(opcode, payload)`` when the CRC matches and the opcode is known;
        otherwise discard the frame and resync to ``HUNT_SOF`` (Req 1.4). Either
        way the decoder returns to hunting for the next SOF.

        Args:
        - byte (`int`): The received trailing CRC8 byte.

        Returns:
        `tuple[int, bytes] | None`: The completed frame, or `None` on discard.

        """
        crc_ok = crc8(bytes(self._body)) == byte
        opcode_ok = self._body[0] in _KNOWN_OPCODES
        result = (
            (self._body[0], bytes(self._body[1:])) if (crc_ok and opcode_ok) else None
        )
        self._reset()
        return result

    _HANDLERS: ClassVar[
        dict[_State, Callable[[FrameDecoderModel, int], tuple[int, bytes] | None]]
    ] = {
        _State.HUNT_SOF: _feed_hunt_sof,
        _State.READ_LEN0: _feed_len0,
        _State.READ_LEN1: _feed_len1,
        _State.READ_BODY: _feed_body,
        _State.READ_CRC: _feed_crc,
    }
    """Per-state byte handler dispatch table mirroring the firmware ``switch``."""

    def feed_all(self, stream: bytes) -> list[tuple[int, bytes]]:
        """
        Feed an entire byte stream and collect every emitted valid frame.

        Args:
        - stream (`bytes`): Arbitrary received byte stream (frames + garbage).

        Returns:
        `list[tuple[int, bytes]]`: The ``(opcode, payload)`` tuples emitted, in
        the order the decoder completed them.

        """
        out: list[tuple[int, bytes]] = []
        for byte in stream:
            emitted = self.feed(byte)
            if emitted is not None:
                out.append(emitted)
        return out


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
# ``codec="utf-8"`` excludes surrogate code points (invalid UTF-8), so encoded
# text stays within the wire's UTF-8 payload contract.
_text = st.text(
    alphabet=st.characters(codec="utf-8"),
    min_size=0,
    max_size=32,
)


@st.composite
def _draw_text(draw: st.DrawFn) -> DrawText:
    """
    Generate a valid `DrawText` command respecting every wire field bound.

    Args:
    - draw (`st.DrawFn`): `hypothesis` draw callable supplied by ``@composite``.

    Returns:
    `DrawText`: A `DrawText` within its ``uint16`` / ``uint8`` field ranges.

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
    `DrawRect`: A `DrawRect` within its ``uint16`` field ranges.

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
# Garbage is arbitrary bytes that exclude the SOF marker (0xA5), so a garbage run
# can never *initiate* frame parsing and thus cannot masquerade as a valid frame
# (which would legitimately be emitted and break the expected sequence). This
# isolates the property under test -- recover-and-discard across interleaved
# noise -- from the vanishingly unlikely case of random bytes forming a
# CRC-valid, known-opcode frame. Any non-SOF byte is skipped while hunting and
# discarded mid-frame on the SOF-triggered resync, exactly as the firmware does.
_non_sof_byte = st.integers(min_value=0, max_value=UINT8_MAX).filter(lambda b: b != SOF)
_garbage = st.builds(bytes, st.lists(_non_sof_byte, min_size=0, max_size=24))


def _expected(command: DrawText | DrawRect) -> tuple[int, bytes]:
    """
    Return the ``(opcode, payload)`` a valid frame for ``command`` should emit.

    Recompute the opcode/payload from the framed bytes of ``serialize(command)``
    so the expectation is derived independently of the decoder model.

    Args:
    - command (`DrawText | DrawRect`): The command whose frame is expected.

    Returns:
    `tuple[int, bytes]`: The ``(opcode, payload)`` the decoder should emit.

    """
    frame = serialize(command)
    (length,) = (frame[1] | (frame[2] << 8),)
    body = frame[3 : 3 + length]
    return body[0], bytes(body[1:])


@given(
    commands=st.lists(_commands, min_size=0, max_size=6),
    lead=_garbage,
    gaps=st.lists(_garbage, min_size=0, max_size=7),
)
@settings(max_examples=MAX_EXAMPLES)
def check_recover_and_discard(
    commands: list[DrawText | DrawRect],
    lead: bytes,
    gaps: list[bytes],
) -> None:
    """
    Assert the decoder emits exactly the valid frames, in order, discarding rest.

    Build a stream by interleaving garbage runs with the serialized valid frames
    (``lead`` before the first frame, then a garbage gap after each frame), feed it
    through the :class:`FrameDecoderModel`, and assert the emitted
    ``(opcode, payload)`` sequence equals the frames' expected sequence (Req 1.4).

    Args:
    - commands (`list[DrawText | DrawRect]`): Valid commands to serialize into frames.
    - lead (`bytes`): Garbage prepended before the first frame.
    - gaps (`list[bytes]`): Garbage runs inserted after each frame.

    Raises:
    - `AssertionError`: If the emitted frame sequence differs from the expected one.

    Returns:
    `None`: This check returns nothing when the property holds.

    """
    stream = bytearray(lead)
    expected: list[tuple[int, bytes]] = []
    for index, command in enumerate(commands):
        stream += serialize(command)
        expected.append(_expected(command))
        if index < len(gaps):
            stream += gaps[index]

    emitted = FrameDecoderModel().feed_all(bytes(stream))
    assert emitted == expected, f"decoder mismatch: {emitted!r} != {expected!r}"


def main() -> None:
    """
    Run the recover-and-discard property and report the outcome.

    Print ``PASS`` and exit ``0`` when the property holds across all generated
    examples; print the falsifying example and traceback and exit ``1`` when
    `hypothesis` finds a counterexample.

    Returns:
    `None`: This entry point exits the process on failure.

    """
    try:
        check_recover_and_discard()
    except AssertionError:
        traceback.print_exc()
        sys.exit(1)
    print("PASS")


if __name__ == "__main__":
    main()
