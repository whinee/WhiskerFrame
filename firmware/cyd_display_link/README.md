# CYD Display Link — Firmware

Custom firmware for the Cheap Yellow Display (CYD): an ESP32 board with an
ILI9341 TFT. Built with the Arduino framework and TFT_eSPI. The firmware reads a
length-prefixed command protocol over USB-serial and renders high-level drawing
commands (draw text, draw rectangle) locally — it never receives a framebuffer.

## Layout (PlatformIO / Arduino sketch)

| File             | Task | Purpose                                                     |
| ---------------- | ---- | ----------------------------------------------------------- |
| `frame.h`        | 15.1 | Frame decoder state machine + CRC8 (header-only).           |
| `render.h`       | 15.3 / 15.4 | `render_text()` / `render_rect()` over TFT_eSPI.     |
| `main.cpp`       | 15.5 | `setup()` / `loop()`: init display, feed decoder, dispatch. |
| `platformio.ini` | —    | ESP32 + Arduino + TFT_eSPI build config for the CYD.        |

## Serial protocol

Frame layout (little-endian):

```text
[SOF 0xA5][LEN uint16 LE][OPCODE uint8][PAYLOAD (LEN-1 B)][CRC8]
```

- `LEN` counts `OPCODE + PAYLOAD` (`1 + len(payload)`).
- `CRC8` covers `OPCODE + PAYLOAD` only.

### CRC8

The decoder uses **CRC-8/SMBUS**: polynomial `0x07`, init `0x00`, no input or
output reflection, no final XOR (check value `0xF4` over `"123456789"`). The
host `whiskerframe/protocol.py` (task 6.1) must implement the identical
algorithm so frames validate on-device. The exact parameters and a reference
Python implementation live in the header comment of `frame.h`.

### Discard-on-unparseable (Req 1.4)

`FrameDecoder` hunts for `SOF`, reads `LEN`, accumulates the body, then
validates the trailing CRC. On a bad CRC, an unknown opcode, or a `LEN` larger
than the ~2 KB buffer cap, it discards the in-progress frame and resynchronizes
to the next `SOF`, so later frames still process.

## Building

```sh
pio run                 # build
pio run -t upload       # flash (see the project flash-safety gate first)
pio device monitor      # serial monitor at 115200 baud
```

> Flashing the CYD overwrites factory firmware and is irreversible. Follow the
> project flash-safety gate (full backup + validation + explicit confirmation)
> before any write.
