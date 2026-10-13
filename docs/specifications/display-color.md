### §2.3 RGB565 Color Packing, Wire Byte Order & Display Inversion

RGB565 values are a 16-bit packing of an 8-bit `(r, g, b)` triple, keeping the top bits of each channel: `value = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)` (5 bits red, 6 bits green, 5 bits blue). Example: pink `#ffb3e6` -> `0xFD9C`. That `uint16` *value* is identical everywhere; only its **byte order on the wire** differs by opcode.

**Image pixels are big-endian, not pre-inverted.** The `DRAW_IMAGE` (`0x05`) pixel block is packed **big-endian** (high byte first). The firmware blits it with TFT_eSPI `pushImage` while `_swapBytes = false`, so `pushImage` reads the two bytes in that big-endian order directly. The host splash packer (`scripts/convert_splash.py`) therefore emits high-byte-first. Pixels are shipped as their **true** RGB565 values — they are **NOT pre-inverted and NOT XOR-compensated**. (An earlier revision wrongly described a `value ^= 0xFFFF` pre-inversion to compensate a presumed per-image inversion; that was a misdiagnosis of a byte-order bug and has been removed — see `docs/dev/ai-decisions.md` DEC-W5.)

**Inversion is panel-level and uniform.** `tft.invertDisplay(true)` is a *panel* setting that affects **every** pixel the controller emits — text, rects, and images equally. It is not a per-opcode transform and must never be compensated per-opcode in software.

**Theme cell colors.** Theme values (`bg`/`fg`/`cursor`/`accents`/`ansi` consumed by `DRAW_CELLS`/`DRAW_TEXT`/`DRAW_RECT`) are shipped as their true RGB565 values. These opcodes travel the firmware's internally byte-swapped text/graphics path (`tft_Write_16S`), which is why they rendered correctly even while the splash byte order was wrong. Never pre-invert or XOR theme colors.

