### §2.1 The Wire Protocol Contract (`whiskerframe.protocol`)

The link between the host Python library (`whiskerframe/`) and the ESP32 C++ firmware (`firmware/cyd_display_link/`) is a fixed binary framing envelope. No high-level abstractions or bitmapped framebuffers may cross this bus.

#### Frame Layout

```text
+-------+--------+--------+---------------------+--------+
|  SOF  |  LEN   | OPCODE |  PAYLOAD (LEN-1 B)  |  CRC8  |
| 0xA5  | uint16 | uint8  |  Opcode-specific    | uint8  |
+-------+--------+--------+---------------------+--------+

```

* **SOF (Start of Frame):** Fixed byte `0xA5`.
* **LEN:** Little-endian `uint16` representing byte length of `OPCODE + PAYLOAD`.
* **CRC8:** CRC-8/SMBUS polynomial (`0x07`, init `0x00`, check `crc8(b"123456789") == 0xF4`). Calculated over `OPCODE + PAYLOAD`.
* **Byte Order:** Little-endian for framing/header integer fields (`LEN`, and the `u16` coordinate/color fields inside each payload). **Exception:** the raw pixel block carried by `DRAW_IMAGE` is **big-endian RGB565** (high byte first) on the wire — see [§2.3](../display-color.md).

#### Opcode Registry

| Opcode | Identifier | Payload Format | Semantics |
| --- | --- | --- | --- |
| `0x01` | `DRAW_TEXT` | `x:u16, y:u16, fg:u16, bg:u16, font:u8, anchor:u8, text_len:u16, text:str` | Direct text rendering with anchor alignment. |
| `0x02` | `DRAW_RECT` | `x:u16, y:u16, w:u16, h:u16, color:u16, filled:u8` | Background clears and structural panels. |
| `0x03` | `DRAW_CELLS` | `start_col:u8, row:u8, fg:u16, bg:u16, glyph_run:bytes` | VT100 character grid cell updates (terminal core). |
| `0x04` | `SCROLL` | `top_row:u8, bot_row:u8, count:i8, fill_color:u16` | Hardware region scroll (cell height tracked internally). |
| `0x05` | `DRAW_IMAGE` | `x:u16, y:u16, w:u16, h:u16, rgb565_data:bytes` | Splash screens and compressed iconography. Pixel block is **big-endian RGB565** (high byte first), see [§2.3](../display-color.md). |
| `0x06` | `SLEEP` | `none` | Coprocessor display sleep (DISPOFF/SLPIN, backlight off, 80MHz CPU). Wakes on next valid serial frame. |

