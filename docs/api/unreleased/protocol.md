<h1 id=""><a href="#">Module whiskerframe.protocol</a></h1>

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

[← Go back to `whiskerframe`](./index.md)

<h2 id="variables"><a href="#variables">Variables</a></h2>

<h3 id="variables-crc8_check"><a href="#variables-crc8_check"><pre>CRC8_CHECK</pre></a></h3>

CRC-8/SMBUS check value: ``crc8(b"123456789")``.

<h3 id="variables-opcode_clear"><a href="#variables-opcode_clear"><pre>OPCODE_CLEAR</pre></a></h3>

Reserved opcode clearing the display to a fill color (not yet serialized).

<h3 id="variables-opcode_draw_cells"><a href="#variables-opcode_draw_cells"><pre>OPCODE_DRAW_CELLS</pre></a></h3>

Opcode selecting the ``DRAW_CELLS`` command (a run of fixed-cell glyphs).

<h3 id="variables-opcode_draw_image"><a href="#variables-opcode_draw_image"><pre>OPCODE_DRAW_IMAGE</pre></a></h3>

Opcode selecting the ``DRAW_IMAGE`` command (a raw RGB565 pixel block).

<h3 id="variables-opcode_draw_rect"><a href="#variables-opcode_draw_rect"><pre>OPCODE_DRAW_RECT</pre></a></h3>

Opcode selecting the ``DRAW_RECT`` command.

<h3 id="variables-opcode_draw_text"><a href="#variables-opcode_draw_text"><pre>OPCODE_DRAW_TEXT</pre></a></h3>

Opcode selecting the ``DRAW_TEXT`` command.

<h3 id="variables-opcode_flush"><a href="#variables-opcode_flush"><pre>OPCODE_FLUSH</pre></a></h3>

Reserved opcode marking a batch boundary (not yet serialized).

<h3 id="variables-opcode_scroll"><a href="#variables-opcode_scroll"><pre>OPCODE_SCROLL</pre></a></h3>

Opcode selecting the ``SCROLL`` command (shift a row band up or down).

<h3 id="variables-sof"><a href="#variables-sof"><pre>SOF</pre></a></h3>

Start-of-frame marker byte used by the firmware to resynchronize.

<h2 id="functions"><a href="#functions">Functions</a></h2>

<h3 id="functions-crc8"><a href="#functions-crc8"><pre>crc8</pre></a></h3>

```python
(data: bytes) → int
```

Compute the CRC-8/SMBUS checksum over ``data``.

Run the CRC-8/SMBUS algorithm (polynomial ``0x07``, init ``0x00``, no input
or output reflection, no final XOR) over the given bytes. This MUST stay
bit-identical to the firmware ``cyd_display_link::crc8`` in
``firmware/cyd_display_link/frame.h``; ``crc8(b"123456789")`` is ``0xF4``.

Args:
- data (`bytes`): Bytes to checksum (the frame's ``OPCODE + PAYLOAD``).

Returns:
`int`: The 8-bit CRC value in ``[0, 255]``.

<h3 id="functions-decode"><a href="#functions-decode"><pre>decode</pre></a></h3>

```python
(frame_bytes: bytes) → whiskerframe.models.DrawText | whiskerframe.models.DrawRect | whiskerframe.terminal.DrawCells | whiskerframe.terminal.Scroll | whiskerframe.terminal.DrawImage
```

Decode a complete framed byte sequence back into a drawing command.

Validate the frame via :func:`_unframe`, then dispatch on the opcode to
reconstruct the original command. This is the inverse of :func:`serialize`
and supports the serialization round-trip property.

Args:
- frame_bytes (`bytes`): Complete ``[SOF][LEN][OPCODE][PAYLOAD][CRC8]`` frame.

Raises:
- `ValueError`: If the frame fails validation or the opcode is unknown.

Returns:
`DrawText | DrawRect | DrawCells | Scroll | DrawImage`: The reconstructed
command.

<h3 id="functions-frame"><a href="#functions-frame"><pre>frame</pre></a></h3>

```python
(opcode: int, payload: bytes) → bytes
```

Wrap an opcode and payload into a complete framed byte sequence.

Build the ``[SOF][LEN][OPCODE][PAYLOAD][CRC8]`` frame: ``LEN`` is the
little-endian ``uint16`` count of ``OPCODE + PAYLOAD`` and ``CRC8`` is the
CRC-8/SMBUS checksum over ``OPCODE + PAYLOAD``.

Args:
- opcode (`int`): Command opcode selector in ``[0, 255]``.
- payload (`bytes`): Opcode-specific payload bytes.

Returns:
`bytes`: The complete framed byte sequence ready for transmission.

<h3 id="functions-serialize"><a href="#functions-serialize"><pre>serialize</pre></a></h3>

```python
(command: DrawText | DrawRect | DrawCells | Scroll | DrawImage) → bytes
```

Serialize a resolved drawing command into complete framed bytes.

Encode the command's opcode-specific payload and wrap it in the
``[SOF][LEN][OPCODE][PAYLOAD][CRC8]`` frame via :func:`frame`. The result is
ready for transmission over the USB-serial link (Req 1.1) and carries no
framebuffer or full-display bitmap (Req 1.5).

Args:
- command (`DrawText | DrawRect | DrawCells | Scroll | DrawImage`): Resolved
  command to serialize.

Raises:
- `TypeError`: If ``command`` is not a recognized command type.

Returns:
`bytes`: The complete framed byte sequence.

---

[← Go back to `whiskerframe`](./index.md)