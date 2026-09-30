"""
Wire-protocol framing and (de)serialization for the CYD Display Link.

Encode the resolved :class:`whiskerframe.models.DrawText` and
:class:`whiskerframe.models.DrawRect` commands into the length-prefixed serial
frames the CYD firmware decodes, and decode those frames back for round-trip
testing. The frame layout matches the design's "Serial Protocol" section and the
firmware decoder in ``firmware/cyd_display_link/frame.h`` bit-for-bit:

```text
+-------+--------+--------+---------------------+--------+
| SOF   | LEN    | OPCODE | PAYLOAD (LEN-1 B)   | CRC8   |
| 0xA5  | uint16 | uint8  | opcode-specific     | uint8  |
+-------+--------+--------+---------------------+--------+
```

``LEN`` (little-endian ``uint16``) counts ``OPCODE + PAYLOAD``; ``CRC8`` is the
CRC-8/SMBUS checksum over ``OPCODE + PAYLOAD``. Multi-byte integers are
little-endian to match the ESP32, and colors are RGB565 ``uint16`` to match the
ILI9341 native pixel format. The packed ``anchor`` byte stores the horizontal key
(``l``/``m``/``r``) in the high nibble and the vertical key (``t``/``m``/``b``) in
the low nibble.

This module is pure: it imports no Pillow (or any imaging library) and stays
usable on the serial command path (Req 1.1, 1.5).
"""

from __future__ import annotations

import struct

from whiskerframe.anchors import Anchor, resolve_anchor
from whiskerframe.models import DrawRect, DrawText

__all__ = [
    "CRC8_CHECK",
    "OPCODE_CLEAR",
    "OPCODE_DRAW_RECT",
    "OPCODE_DRAW_TEXT",
    "OPCODE_FLUSH",
    "SOF",
    "crc8",
    "decode",
    "frame",
    "serialize",
]

SOF: int = 0xA5
"""Start-of-frame marker byte used by the firmware to resynchronize."""

OPCODE_DRAW_TEXT: int = 0x01
"""Opcode selecting the ``DRAW_TEXT`` command."""

OPCODE_DRAW_RECT: int = 0x02
"""Opcode selecting the ``DRAW_RECT`` command."""

OPCODE_CLEAR: int = 0x10
"""Reserved opcode clearing the display to a fill color (not yet serialized)."""

OPCODE_FLUSH: int = 0x1F
"""Reserved opcode marking a batch boundary (not yet serialized)."""

CRC8_CHECK: int = 0xF4
"""CRC-8/SMBUS check value: ``crc8(b"123456789")``."""

_CRC8_POLY: int = 0x07

_TEXT_FLAG_INVERTED: int = 0x01
_TEXT_FLAG_MULTILINE: int = 0x02
_RECT_FLAG_FILLED: int = 0x01

_HORIZONTAL_NIBBLE: dict[str, int] = {"l": 0, "m": 1, "r": 2}
_VERTICAL_NIBBLE: dict[str, int] = {"t": 0, "m": 1, "b": 2}
_HORIZONTAL_KEY: dict[int, str] = {
    value: key for key, value in _HORIZONTAL_NIBBLE.items()
}
_VERTICAL_KEY: dict[int, str] = {value: key for key, value in _VERTICAL_NIBBLE.items()}

# struct formats for the fixed-length payload headers (little-endian).
# DRAW_TEXT: x, y (u16), anchor, (flags/font_size handled inline), color, bg_color (u16),
# font_size, flags (u8), line_h, text_len (u16).
_DRAW_TEXT_HEADER = struct.Struct("<HHBHHBBHH")
# DRAW_RECT: x, y, w, h, color (u16), flags (u8).
_DRAW_RECT = struct.Struct("<HHHHHB")


def crc8(data: bytes) -> int:
    """
    Compute the CRC-8/SMBUS checksum over ``data``.

    Run the CRC-8/SMBUS algorithm (polynomial ``0x07``, init ``0x00``, no input
    or output reflection, no final XOR) over the given bytes. This MUST stay
    bit-identical to the firmware ``cyd_display_link::crc8`` in
    ``firmware/cyd_display_link/frame.h``; ``crc8(b"123456789")`` is ``0xF4``.

    Args:
    - data (`bytes`): Bytes to checksum (the frame's ``OPCODE + PAYLOAD``).

    Returns:
    `int`: The 8-bit CRC value in ``[0, 255]``.

    """
    crc = 0x00
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x80:
                crc = ((crc << 1) ^ _CRC8_POLY) & 0xFF
            else:
                crc = (crc << 1) & 0xFF
    return crc


def _pack_anchor(anchor: Anchor) -> int:
    """
    Pack a two-character anchor into the wire anchor byte.

    Resolve the anchor into its horizontal and vertical keys and encode them as
    the high and low nibbles respectively: high nibble ``h`` in ``{l=0, m=1,
    r=2}`` and low nibble ``v`` in ``{t=0, m=1, b=2}``.

    Args:
    - anchor (`Anchor`): Two-character ``[lmr][tmb]`` anchor.

    Returns:
    `int`: The packed anchor byte in ``[0, 255]``.

    """
    horizontal, vertical = resolve_anchor(anchor)
    return (_HORIZONTAL_NIBBLE[horizontal] << 4) | _VERTICAL_NIBBLE[vertical]


def _unpack_anchor(anchor_byte: int) -> Anchor:
    """
    Unpack a wire anchor byte into a two-character anchor.

    Split the byte into its high nibble (horizontal key) and low nibble
    (vertical key), inverting :func:`_pack_anchor`.

    Args:
    - anchor_byte (`int`): Packed anchor byte in ``[0, 255]``.

    Raises:
    - `ValueError`: If either nibble is outside the valid key range.

    Returns:
    `Anchor`: The reconstructed two-character anchor.

    """
    horizontal_nibble = (anchor_byte >> 4) & 0x0F
    vertical_nibble = anchor_byte & 0x0F
    if horizontal_nibble not in _HORIZONTAL_KEY or vertical_nibble not in _VERTICAL_KEY:
        msg = f"Invalid packed anchor byte {anchor_byte:#04x}."
        raise ValueError(msg)
    return f"{_HORIZONTAL_KEY[horizontal_nibble]}{_VERTICAL_KEY[vertical_nibble]}"  # type: ignore[return-value]


def frame(opcode: int, payload: bytes) -> bytes:
    """
    Wrap an opcode and payload into a complete framed byte sequence.

    Build the ``[SOF][LEN][OPCODE][PAYLOAD][CRC8]`` frame: ``LEN`` is the
    little-endian ``uint16`` count of ``OPCODE + PAYLOAD`` and ``CRC8`` is the
    CRC-8/SMBUS checksum over ``OPCODE + PAYLOAD``.

    Args:
    - opcode (`int`): Command opcode selector in ``[0, 255]``.
    - payload (`bytes`): Opcode-specific payload bytes.

    Returns:
    `bytes`: The complete framed byte sequence ready for transmission.

    """
    body = bytes([opcode]) + payload
    length = len(body)
    header = struct.pack("<BH", SOF, length)
    return header + body + bytes([crc8(body)])


def _encode_draw_text(command: DrawText) -> bytes:
    """
    Encode a ``DrawText`` command into its ``DRAW_TEXT`` payload bytes.

    Pack the resolved coordinates, anchor byte, colors, font size, flag bits, line
    height, and UTF-8 text length header, followed by the UTF-8 text bytes, all
    little-endian per the design's ``DRAW_TEXT`` payload layout.

    Args:
    - command (`DrawText`): Resolved text command to encode.

    Returns:
    `bytes`: The ``DRAW_TEXT`` payload (excluding opcode and framing).

    """
    flags = 0
    if command.inverted:
        flags |= _TEXT_FLAG_INVERTED
    if command.multiline:
        flags |= _TEXT_FLAG_MULTILINE
    text_bytes = command.text.encode("utf-8")
    header = _DRAW_TEXT_HEADER.pack(
        command.x,
        command.y,
        _pack_anchor(command.anchor),
        command.color,
        command.bg_color,
        command.font_size,
        flags,
        command.line_h,
        len(text_bytes),
    )
    return header + text_bytes


def _encode_draw_rect(command: DrawRect) -> bytes:
    """
    Encode a ``DrawRect`` command into its ``DRAW_RECT`` payload bytes.

    Pack the resolved top-left coordinates, dimensions, RGB565 color, and the
    filled flag bit, all little-endian per the design's ``DRAW_RECT`` payload
    layout.

    Args:
    - command (`DrawRect`): Resolved rectangle command to encode.

    Returns:
    `bytes`: The ``DRAW_RECT`` payload (excluding opcode and framing).

    """
    flags = _RECT_FLAG_FILLED if command.filled else 0
    return _DRAW_RECT.pack(
        command.x,
        command.y,
        command.w,
        command.h,
        command.color,
        flags,
    )


def serialize(command: DrawText | DrawRect) -> bytes:
    """
    Serialize a resolved drawing command into complete framed bytes.

    Encode the command's opcode-specific payload and wrap it in the
    ``[SOF][LEN][OPCODE][PAYLOAD][CRC8]`` frame via :func:`frame`. The result is
    ready for transmission over the USB-serial link (Req 1.1) and carries no
    framebuffer or full-display bitmap (Req 1.5).

    Args:
    - command (`DrawText | DrawRect`): Resolved command to serialize.

    Raises:
    - `TypeError`: If ``command`` is neither a `DrawText` nor a `DrawRect`.

    Returns:
    `bytes`: The complete framed byte sequence.

    """
    if isinstance(command, DrawText):
        return frame(OPCODE_DRAW_TEXT, _encode_draw_text(command))
    if isinstance(command, DrawRect):
        return frame(OPCODE_DRAW_RECT, _encode_draw_rect(command))
    msg = f"Cannot serialize object of type {type(command).__name__!r}."
    raise TypeError(msg)


def _decode_draw_text(payload: bytes) -> DrawText:
    """
    Decode a ``DRAW_TEXT`` payload into a ``DrawText`` command.

    Unpack the fixed-length header, reconstruct the anchor from its packed byte
    and the flag bits, and decode the trailing UTF-8 text, inverting
    :func:`_encode_draw_text`.

    Args:
    - payload (`bytes`): ``DRAW_TEXT`` payload bytes (excluding opcode).

    Raises:
    - `ValueError`: If the payload is truncated or the text length is inconsistent.

    Returns:
    `DrawText`: The reconstructed text command.

    """
    header_size = _DRAW_TEXT_HEADER.size
    if len(payload) < header_size:
        msg = f"DRAW_TEXT payload too short: {len(payload)} < {header_size} bytes."
        raise ValueError(msg)
    (
        x,
        y,
        anchor_byte,
        color,
        bg_color,
        font_size,
        flags,
        line_h,
        text_len,
    ) = _DRAW_TEXT_HEADER.unpack(payload[:header_size])
    text_bytes = payload[header_size:]
    if len(text_bytes) != text_len:
        msg = f"DRAW_TEXT text length mismatch: header {text_len} != {len(text_bytes)} bytes."
        raise ValueError(msg)
    return DrawText(
        x=x,
        y=y,
        anchor=_unpack_anchor(anchor_byte),
        color=color,
        bg_color=bg_color,
        font_size=font_size,
        inverted=bool(flags & _TEXT_FLAG_INVERTED),
        multiline=bool(flags & _TEXT_FLAG_MULTILINE),
        line_h=line_h,
        text=text_bytes.decode("utf-8"),
    )


def _decode_draw_rect(payload: bytes) -> DrawRect:
    """
    Decode a ``DRAW_RECT`` payload into a ``DrawRect`` command.

    Unpack the fixed-length payload and reconstruct the filled flag, inverting
    :func:`_encode_draw_rect`.

    Args:
    - payload (`bytes`): ``DRAW_RECT`` payload bytes (excluding opcode).

    Raises:
    - `ValueError`: If the payload length does not match the ``DRAW_RECT`` layout.

    Returns:
    `DrawRect`: The reconstructed rectangle command.

    """
    if len(payload) != _DRAW_RECT.size:
        msg = f"DRAW_RECT payload length mismatch: {len(payload)} != {_DRAW_RECT.size} bytes."
        raise ValueError(msg)
    x, y, w, h, color, flags = _DRAW_RECT.unpack(payload)
    return DrawRect(
        x=x,
        y=y,
        w=w,
        h=h,
        color=color,
        filled=bool(flags & _RECT_FLAG_FILLED),
    )


_FRAME_OVERHEAD = 4
"""Non-body frame bytes: SOF (1) + LEN (2) + CRC8 (1)."""


def _unframe(frame_bytes: bytes) -> bytes:
    """
    Validate a framed byte sequence and return its ``OPCODE + PAYLOAD`` body.

    Check the ``SOF`` marker, the ``LEN`` field consistency, and the trailing
    ``CRC8`` over ``OPCODE + PAYLOAD``, then return the validated body bytes.

    Args:
    - frame_bytes (`bytes`): Complete ``[SOF][LEN][OPCODE][PAYLOAD][CRC8]`` frame.

    Raises:
    - `ValueError`: If the frame is truncated, the ``SOF`` marker is wrong, the
      ``LEN`` field is inconsistent, or the ``CRC8`` mismatches.

    Returns:
    `bytes`: The validated ``OPCODE + PAYLOAD`` body.

    """
    if len(frame_bytes) < _FRAME_OVERHEAD + 1:
        msg = f"Frame too short: {len(frame_bytes)} bytes."
        raise ValueError(msg)
    if frame_bytes[0] != SOF:
        msg = f"Bad SOF marker: {frame_bytes[0]:#04x} != {SOF:#04x}."
        raise ValueError(msg)
    (length,) = struct.unpack("<H", frame_bytes[1:3])
    expected_total = 3 + length + 1
    if len(frame_bytes) != expected_total:
        msg = f"Frame length mismatch: LEN={length} implies {expected_total} bytes, got {len(frame_bytes)}."
        raise ValueError(msg)
    body = frame_bytes[3 : 3 + length]
    received_crc = frame_bytes[3 + length]
    expected_crc = crc8(body)
    if received_crc != expected_crc:
        msg = f"CRC mismatch: got {received_crc:#04x}, expected {expected_crc:#04x}."
        raise ValueError(msg)
    return body


def decode(frame_bytes: bytes) -> DrawText | DrawRect:
    """
    Decode a complete framed byte sequence back into a drawing command.

    Validate the frame via :func:`_unframe`, then dispatch on the opcode to
    reconstruct the original :class:`DrawText` or :class:`DrawRect`. This is the
    inverse of :func:`serialize` and supports the serialization round-trip
    property.

    Args:
    - frame_bytes (`bytes`): Complete ``[SOF][LEN][OPCODE][PAYLOAD][CRC8]`` frame.

    Raises:
    - `ValueError`: If the frame fails validation or the opcode is unknown.

    Returns:
    `DrawText | DrawRect`: The reconstructed command.

    """
    body = _unframe(frame_bytes)
    opcode = body[0]
    payload = body[1:]
    if opcode == OPCODE_DRAW_TEXT:
        return _decode_draw_text(payload)
    if opcode == OPCODE_DRAW_RECT:
        return _decode_draw_rect(payload)
    msg = f"Unknown opcode: {opcode:#04x}."
    raise ValueError(msg)
