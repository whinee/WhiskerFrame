Module whiskerframe.protocol
============================
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

Variables
---------

`CRC8_CHECK: int`
:   CRC-8/SMBUS check value: ``crc8(b"123456789")``.

`OPCODE_CLEAR: int`
:   Reserved opcode clearing the display to a fill color (not yet serialized).

`OPCODE_DRAW_RECT: int`
:   Opcode selecting the ``DRAW_RECT`` command.

`OPCODE_DRAW_TEXT: int`
:   Opcode selecting the ``DRAW_TEXT`` command.

`OPCODE_FLUSH: int`
:   Reserved opcode marking a batch boundary (not yet serialized).

`SOF: int`
:   Start-of-frame marker byte used by the firmware to resynchronize.

Functions
---------

`crc8(data: bytes) ‑> int`
:   Compute the CRC-8/SMBUS checksum over ``data``.
    
    Run the CRC-8/SMBUS algorithm (polynomial ``0x07``, init ``0x00``, no input
    or output reflection, no final XOR) over the given bytes. This MUST stay
    bit-identical to the firmware ``cyd_display_link::crc8`` in
    ``firmware/cyd_display_link/frame.h``; ``crc8(b"123456789")`` is ``0xF4``.
    
    Args:
    - data (`bytes`): Bytes to checksum (the frame's ``OPCODE + PAYLOAD``).
    
    Returns:
    `int`: The 8-bit CRC value in ``[0, 255]``.

`decode(frame_bytes: bytes) ‑> whiskerframe.models.DrawText | whiskerframe.models.DrawRect`
:   Decode a complete framed byte sequence back into a drawing command.
    
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

`frame(opcode: int, payload: bytes) ‑> bytes`
:   Wrap an opcode and payload into a complete framed byte sequence.
    
    Build the ``[SOF][LEN][OPCODE][PAYLOAD][CRC8]`` frame: ``LEN`` is the
    little-endian ``uint16`` count of ``OPCODE + PAYLOAD`` and ``CRC8`` is the
    CRC-8/SMBUS checksum over ``OPCODE + PAYLOAD``.
    
    Args:
    - opcode (`int`): Command opcode selector in ``[0, 255]``.
    - payload (`bytes`): Opcode-specific payload bytes.
    
    Returns:
    `bytes`: The complete framed byte sequence ready for transmission.

`serialize(command: DrawText | DrawRect) ‑> bytes`
:   Serialize a resolved drawing command into complete framed bytes.
    
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