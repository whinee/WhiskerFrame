// render.h — CYD Display Link TFT_eSPI renderers for DRAW_TEXT / DRAW_RECT
//
// Header-only rendering helpers for the CYD_Firmware (ESP32 + ILI9341, Arduino
// / TFT_eSPI). Given a validated frame payload produced by the host
// `whiskerframe.protocol` module and decoded by `frame.h`, these functions
// decode the opcode-specific payload layout defined in the design "Payload
// encodings" section and draw onto a `TFT_eSPI` instance.
//
// The caller (main.cpp dispatch, task 15.5) is responsible for having a
// complete, CRC-valid, known-opcode frame from `FrameDecoder`; these functions
// take the payload pointer and length and assume the frame layer already
// accepted the frame. They perform their own payload-level validation on top of
// that (see the bounds/validity skip below).
//
// Wire encodings (little-endian multi-byte integers, RGB565 colors):
//
//   DRAW_TEXT (opcode 0x01):
//     x         : uint16   resolved anchor x (px)
//     y         : uint16   resolved anchor y (px)
//     anchor    : uint8    packed anchor: high nibble h in {0=l,1=m,2=r},
//                          low nibble v in {0=t,1=m,2=b}
//     color     : uint16   RGB565 foreground
//     bg_color  : uint16   RGB565 background (used when inverted)
//     font_size : uint8    text size / font selector
//     flags     : uint8    bit0 inverted, bit1 multiline
//     line_h    : uint16   line height in px (multiline)
//     text_len  : uint16   UTF-8 byte length
//     text      : bytes    UTF-8 text (LF-separated lines when multiline)
//
//   DRAW_RECT (opcode 0x02):
//     x     : uint16   resolved top-left x (px)
//     y     : uint16   resolved top-left y (px)
//     w     : uint16   width (px)
//     h     : uint16   height (px)
//     color : uint16   RGB565
//     flags : uint8    bit0 filled (else outline)
//
// ---------------------------------------------------------------------------
// Bounds / validity skip (Requirement 2.5)
// ---------------------------------------------------------------------------
// For DRAW_TEXT, if the anchor/coordinates would place the text box outside the
// visible display bounds, or the payload is malformed (too short, or the packed
// anchor nibbles are out of range), the command is skipped ENTIRELY — no
// clipping, no placement adjustment. This is distinct from the unparseable
// frame discard path in `frame.h` (the frame is already valid and consumed;
// render_text simply declines to draw). Bounds are checked against the runtime
// display extent (`tft.width()` / `tft.height()`), which already reflects the
// active rotation set in setup(), rather than the compile-time TFT_WIDTH /
// TFT_HEIGHT macros (those describe the panel in its native, unrotated
// orientation and would be wrong after setRotation).
//
// Design refs: Req 2.3, 2.4, 2.5.

#ifndef CYD_DISPLAY_LINK_RENDER_H
#define CYD_DISPLAY_LINK_RENDER_H

#include <TFT_eSPI.h>
#include <stddef.h>
#include <stdint.h>

#include "frame.h"

namespace cyd_display_link {

// -- Payload layout constants -----------------------------------------------

// Fixed (pre-text) header length of a DRAW_TEXT payload:
//   x(2) y(2) anchor(1) color(2) bg_color(2) font_size(1) flags(1)
//   line_h(2) text_len(2) = 15 bytes.
static const uint16_t kDrawTextHeaderLen = 15;

// Fixed length of a DRAW_RECT payload:
//   x(2) y(2) w(2) h(2) color(2) flags(1) = 11 bytes.
static const uint16_t kDrawRectLen = 11;

// DRAW_TEXT flag bits.
static const uint8_t kTextFlagInverted = 0x01;   // bit0
static const uint8_t kTextFlagMultiline = 0x02;  // bit1

// DRAW_RECT flag bits.
static const uint8_t kRectFlagFilled = 0x01;  // bit0

// Fixed (pre-text) header length of a DRAW_CELLS payload (host
// protocol.py `_DRAW_CELLS_HEADER = "<HHHHBH"`):
//   col(2) row(2) fg(2) bg(2) font_size(1) len(2) = 11 bytes.
static const uint16_t kDrawCellsHeaderLen = 11;

// Fixed length of a SCROLL payload (host `_SCROLL = "<bHHH"`):
//   rows(1, signed) fill(2) top(2) bottom(2) = 7 bytes.
static const uint16_t kScrollLen = 7;

// Fixed (pre-pixel) header length of a DRAW_IMAGE payload (host
// `_DRAW_IMAGE_HEADER = "<HHHH"`):
//   x(2) y(2) w(2) h(2) = 8 bytes.
static const uint16_t kDrawImageHeaderLen = 8;

// Fixed-cell font geometry base (6x8 at size 1), matching
// whiskerframe/metrics.py FONT_METRICS and the TFT_eSPI 6x8 built-in font that
// setTextSize(N) scales linearly. cell_w = 6*N, cell_h = 8*N.
static const int32_t kCellBaseW = 6;
static const int32_t kCellBaseH = 8;

// Scanline buffer bound for the SCROLL row-band blit (one row of pixels at the
// 320-wide landscape panel). Bounded, stack-free (file-scope static) so SCROLL
// does no dynamic allocation on the constrained ESP32. 320 covers the full
// visible width at rotation 1.
static const uint16_t kScrollMaxWidth = 320;

// -- Little-endian payload readers ------------------------------------------

// Read a little-endian uint16 from `p` at byte offset `off`.
inline uint16_t read_u16le(const uint8_t* p, uint16_t off) {
  return static_cast<uint16_t>(p[off]) |
         (static_cast<uint16_t>(p[off + 1]) << 8);
}

// Read a signed int8 from `p` at byte offset `off`. Used for SCROLL's `rows`
// field, which the host packs as struct "<b" (signed: +up, -down).
inline int8_t read_i8(const uint8_t* p, uint16_t off) {
  return static_cast<int8_t>(p[off]);
}

// -- Active cell height tracking (for SCROLL) -------------------------------
//
// SCROLL carries its row band in CELL units but has no font_size field, so the
// firmware cannot know the pixel height of a cell from the SCROLL payload
// alone. We track the cell height of the most recent DRAW_CELLS command in a
// file-scope static and reuse it to convert SCROLL's cell-unit band to pixels.
// This is self-contained: the host emits DRAW_CELLS at the active terminal
// font before scrolling, so the tracked height matches the band the host
// intends. Default is the size-1 cell height (8 px) until the first DRAW_CELLS.
//
// Trade-off (documented in ai-decisions.md): if a SCROLL ever arrives before
// any DRAW_CELLS, it scrolls assuming an 8 px cell. In the terminal data flow
// the splash/login paint cells first, so this is safe in practice.
inline int32_t& active_cell_height() {
  static int32_t cell_h = kCellBaseH;  // size-1 default (8 px)
  return cell_h;
}

// Cell width/height in pixels for a font_size selector (0 treated as 1),
// matching whiskerframe/metrics.py (cell_w = 6*N, cell_h = 8*N).
inline int32_t cell_width_for(uint8_t font_size) {
  const int32_t n = font_size == 0 ? 1 : static_cast<int32_t>(font_size);
  return kCellBaseW * n;
}
inline int32_t cell_height_for(uint8_t font_size) {
  const int32_t n = font_size == 0 ? 1 : static_cast<int32_t>(font_size);
  return kCellBaseH * n;
}

// -- Anchor byte -> TFT_eSPI text datum -------------------------------------

// Map the packed anchor byte to a TFT_eSPI text datum. The high nibble selects
// horizontal alignment (0=left, 1=middle, 2=right) and the low nibble selects
// vertical alignment (0=top, 1=middle, 2=bottom), preserving the imagesmacker
// [lmr][tmb] semantics on-device.
//
// Returns true and writes *datum on success; returns false if either nibble is
// out of the {0,1,2} range, so the caller can skip an invalid command (Req 2.5).
inline bool anchor_to_datum(uint8_t anchor, uint8_t* datum) {
  const uint8_t h = static_cast<uint8_t>((anchor >> 4) & 0x0F);  // 0=l,1=m,2=r
  const uint8_t v = static_cast<uint8_t>(anchor & 0x0F);         // 0=t,1=m,2=b
  if (h > 2 || v > 2) {
    return false;
  }
  // TFT_eSPI datum grid: columns L/C/R, rows T/C/B.
  //   TL_DATUM=0 TC_DATUM=1 TR_DATUM=2
  //   ML_DATUM=3 MC_DATUM=4 MR_DATUM=5
  //   BL_DATUM=6 BC_DATUM=7 BR_DATUM=8
  static const uint8_t kDatumGrid[3][3] = {
      {TL_DATUM, ML_DATUM, BL_DATUM},  // h = l : left column
      {TC_DATUM, MC_DATUM, BC_DATUM},  // h = m : centre column
      {TR_DATUM, MR_DATUM, BR_DATUM},  // h = r : right column
  };
  *datum = kDatumGrid[h][v];
  return true;
}

// -- Bounds check -----------------------------------------------------------

// True when point (x, y) lies within the visible display, i.e. inside
// [0, width) x [0, height) at the current rotation.
inline bool point_in_bounds(TFT_eSPI& tft, int32_t x, int32_t y) {
  return x >= 0 && y >= 0 && x < tft.width() && y < tft.height();
}

// -- render_text (Req 2.3, 2.5) ---------------------------------------------

// Render a DRAW_TEXT payload on `tft`.
//
// Decodes the payload per the DRAW_TEXT encoding, maps the packed anchor byte
// to a TFT_eSPI text datum, and draws the text at the resolved (x, y). When the
// multiline flag is set, the text is split on LF ('\n') and successive lines
// advance vertically by `line_h`. When the inverted flag is set, foreground and
// background colors are swapped so text is drawn as bg-on-fg.
//
// Requirement 2.5: if the payload is malformed (shorter than the fixed header,
// or shorter than header + text_len), the packed anchor is invalid, or the
// resolved anchor point (or any multiline row's anchor point) falls outside the
// visible display bounds, the command is skipped ENTIRELY — no clipping or
// placement adjustment, and nothing is drawn.
inline void render_text(TFT_eSPI& tft, const uint8_t* payload, uint16_t len) {
  // Malformed: not even the fixed header is present.
  if (payload == nullptr || len < kDrawTextHeaderLen) {
    return;  // skip entirely (Req 2.5)
  }

  const uint16_t x = read_u16le(payload, 0);
  const uint16_t y = read_u16le(payload, 2);
  const uint8_t anchor = payload[4];
  const uint16_t color = read_u16le(payload, 5);
  const uint16_t bg_color = read_u16le(payload, 7);
  const uint8_t font_size = payload[9];
  const uint8_t flags = payload[10];
  const uint16_t line_h = read_u16le(payload, 11);
  const uint16_t text_len = read_u16le(payload, 13);

  // Malformed: declared text length overruns the received payload.
  if (static_cast<uint32_t>(kDrawTextHeaderLen) + text_len > len) {
    return;  // skip entirely (Req 2.5)
  }

  // Invalid packed anchor -> skip entirely (Req 2.5).
  uint8_t datum = TL_DATUM;
  if (!anchor_to_datum(anchor, &datum)) {
    return;
  }

  const bool inverted = (flags & kTextFlagInverted) != 0;
  const bool multiline = (flags & kTextFlagMultiline) != 0;

  const uint8_t* text = payload + kDrawTextHeaderLen;

  // Bounds validity (Req 2.5): the resolved anchor point must be on-screen, and
  // for multiline every line's anchor point must also be on-screen. We check
  // all line anchor points up front and skip the whole command if any is out of
  // bounds — no partial draw. line_advance is 0 for single-line text.
  const int32_t line_advance = multiline ? static_cast<int32_t>(line_h) : 0;

  // Count lines (split on LF) to validate every row before drawing anything.
  uint16_t line_count = 1;
  if (multiline) {
    for (uint16_t i = 0; i < text_len; ++i) {
      if (text[i] == '\n') {
        ++line_count;
      }
    }
  }

  for (uint16_t line = 0; line < line_count; ++line) {
    const int32_t ly = static_cast<int32_t>(y) + line_advance * line;
    if (!point_in_bounds(tft, static_cast<int32_t>(x), ly)) {
      return;  // any out-of-bounds anchor -> skip entirely (Req 2.5)
    }
  }

  // All anchor points valid and on-screen: configure and draw.
  const uint16_t fg = inverted ? bg_color : color;
  const uint16_t bg = inverted ? color : bg_color;

  tft.setTextDatum(datum);
  tft.setTextColor(fg, bg);
  tft.setTextSize(font_size == 0 ? 1 : font_size);

  if (!multiline) {
    // Single line: drawString needs a NUL-terminated C string. Copy into a
    // bounded stack buffer sized to the largest accepted payload text.
    char buf[kMaxFrameLen];
    const uint16_t n = text_len < (kMaxFrameLen - 1) ? text_len
                                                     : (kMaxFrameLen - 1);
    for (uint16_t i = 0; i < n; ++i) {
      buf[i] = static_cast<char>(text[i]);
    }
    buf[n] = '\0';
    tft.drawString(buf, static_cast<int32_t>(x), static_cast<int32_t>(y));
    return;
  }

  // Multiline: draw each LF-separated line at its own anchor row.
  char buf[kMaxFrameLen];
  uint16_t line = 0;
  uint16_t seg_start = 0;
  for (uint16_t i = 0; i <= text_len; ++i) {
    const bool at_end = (i == text_len);
    if (at_end || text[i] == '\n') {
      const uint16_t seg_len = i - seg_start;
      const uint16_t n =
          seg_len < (kMaxFrameLen - 1) ? seg_len : (kMaxFrameLen - 1);
      for (uint16_t j = 0; j < n; ++j) {
        buf[j] = static_cast<char>(text[seg_start + j]);
      }
      buf[n] = '\0';
      const int32_t ly = static_cast<int32_t>(y) + line_advance * line;
      tft.drawString(buf, static_cast<int32_t>(x), ly);
      ++line;
      seg_start = static_cast<uint16_t>(i + 1);
    }
  }
}

// -- render_rect (Req 2.4) --------------------------------------------------

// Render a DRAW_RECT payload on `tft`.
//
// Decodes the payload per the DRAW_RECT encoding and draws either a filled
// (`fillRect`) or an outline (`drawRect`) rectangle at the resolved top-left
// (x, y) with the given width/height and RGB565 color. A malformed payload
// (shorter than the fixed 11-byte layout) is skipped. Unlike DRAW_TEXT, the
// rectangle command carries no anchor bounds contract in Req 2.5; TFT_eSPI
// clips off-screen rectangle pixels natively.
inline void render_rect(TFT_eSPI& tft, const uint8_t* payload, uint16_t len) {
  if (payload == nullptr || len < kDrawRectLen) {
    return;  // malformed -> skip
  }

  const uint16_t x = read_u16le(payload, 0);
  const uint16_t y = read_u16le(payload, 2);
  const uint16_t w = read_u16le(payload, 4);
  const uint16_t h = read_u16le(payload, 6);
  const uint16_t color = read_u16le(payload, 8);
  const uint8_t flags = payload[10];

  const bool filled = (flags & kRectFlagFilled) != 0;

  if (filled) {
    tft.fillRect(x, y, w, h, color);
  } else {
    tft.drawRect(x, y, w, h, color);
  }
}

// -- render_cells (DRAW_CELLS 0x03) -----------------------------------------
//
// Render a DRAW_CELLS payload on `tft`.
//
// Payload layout (little-endian, host protocol.py `_DRAW_CELLS_HEADER
// = "<HHHHBH"`):
//   col(2) row(2) fg(2) bg(2) font_size(1) len(2) then `len` glyph bytes
//   (one char per cell, latin-1).
//
// Each cell occupies a fixed cell_w x cell_h box (cell_w = 6*font_size,
// cell_h = 8*font_size) starting at pixel (col*cell_w, row*cell_h). The whole
// run's background is painted first (one fillRect of len*cell_w x cell_h in
// `bg`) so overwrites are clean, then the glyphs are drawn in `fg` at the
// matching text size with a top-left datum. Cells that would fall outside the
// visible display are skipped individually (clipped at the right/bottom edge) —
// the on-screen prefix still draws. A malformed/short payload (shorter than the
// header, or `len` overrunning the received bytes) is skipped entirely, matching
// the render_text skip contract.
//
// Side effect: updates the module-level active cell height (see
// active_cell_height) so a subsequent SCROLL can convert its cell-unit band to
// pixels using this command's font size.
inline void render_cells(TFT_eSPI& tft, const uint8_t* payload, uint16_t len) {
  if (payload == nullptr || len < kDrawCellsHeaderLen) {
    return;  // malformed -> skip
  }

  const uint16_t col = read_u16le(payload, 0);
  const uint16_t row = read_u16le(payload, 2);
  const uint16_t fg = read_u16le(payload, 4);
  const uint16_t bg = read_u16le(payload, 6);
  const uint8_t font_size = payload[8];
  const uint16_t run_len = read_u16le(payload, 9);

  // Declared run length must not overrun the received payload.
  if (static_cast<uint32_t>(kDrawCellsHeaderLen) + run_len > len) {
    return;  // malformed -> skip
  }

  const int32_t cell_w = cell_width_for(font_size);
  const int32_t cell_h = cell_height_for(font_size);

  // Remember this font's cell height for a following SCROLL (see header note).
  active_cell_height() = cell_h;

  const uint8_t* glyphs = payload + kDrawCellsHeaderLen;
  const int32_t base_x = static_cast<int32_t>(col) * cell_w;
  const int32_t base_y = static_cast<int32_t>(row) * cell_h;

  // Whole run off-screen vertically -> nothing to draw.
  if (base_y < 0 || base_y >= tft.height()) {
    return;
  }

  // Paint only the on-screen portion of the run background in one fillRect, then
  // draw glyphs cell-by-cell, skipping any that start past the right edge.
  const int32_t screen_w = tft.width();
  if (base_x >= screen_w) {
    return;  // run starts off the right edge
  }
  const int32_t run_px = static_cast<int32_t>(run_len) * cell_w;
  int32_t bg_w = run_px;
  if (base_x + bg_w > screen_w) {
    bg_w = screen_w - base_x;  // clip background to the visible width
  }
  if (bg_w > 0) {
    tft.fillRect(base_x, base_y, bg_w, cell_h, bg);
  }

  tft.setTextDatum(TL_DATUM);
  tft.setTextColor(fg, bg);
  tft.setTextSize(font_size == 0 ? 1 : font_size);

  for (uint16_t i = 0; i < run_len; ++i) {
    const int32_t cx = base_x + static_cast<int32_t>(i) * cell_w;
    if (cx >= screen_w) {
      break;  // remaining cells are off the right edge
    }
    char ch[2];
    ch[0] = static_cast<char>(glyphs[i]);
    ch[1] = '\0';
    tft.drawString(ch, cx, base_y);
  }
}

// -- render_scroll (SCROLL 0x04) --------------------------------------------
//
// Render a SCROLL payload on `tft`.
//
// Payload layout (little-endian, host `_SCROLL = "<bHHH"`):
//   rows(1, SIGNED int8: +up, -down) fill(2) top(2) bottom(2)
// top/bottom are the inclusive row band in CELL units.
//
// The firmware converts the cell-unit band to pixels using the cell height of
// the most recent DRAW_CELLS (active_cell_height; default 8 px) — SCROLL itself
// carries no font_size. The pixel band [top*cell_h, (bottom+1)*cell_h) is
// shifted up (rows>0) or down (rows<0) by abs(rows)*cell_h pixels using a
// scanline readRect/pushRect row-band copy, and the vacated rows are filled with
// `fill`. The band is clamped to the visible display; a zero shift, an invalid
// band, or a shift that clears the whole band is handled as a plain fill (or a
// no-op). No dynamic allocation: one file-scope scanline buffer bounds the copy.
inline void render_scroll(TFT_eSPI& tft, const uint8_t* payload, uint16_t len) {
  if (payload == nullptr || len < kScrollLen) {
    return;  // malformed -> skip
  }

  const int8_t rows = read_i8(payload, 0);
  const uint16_t fill = read_u16le(payload, 1);
  const uint16_t top = read_u16le(payload, 3);
  const uint16_t bottom = read_u16le(payload, 5);

  if (bottom < top) {
    return;  // invalid band -> no-op
  }

  const int32_t cell_h = active_cell_height();
  if (cell_h <= 0) {
    return;  // defensive; cell height is always positive
  }

  // Pixel band [band_top, band_bottom) clamped to the screen.
  const int32_t screen_w = tft.width();
  const int32_t screen_h = tft.height();
  int32_t band_top = static_cast<int32_t>(top) * cell_h;
  int32_t band_bottom = (static_cast<int32_t>(bottom) + 1) * cell_h;
  if (band_top < 0) {
    band_top = 0;
  }
  if (band_bottom > screen_h) {
    band_bottom = screen_h;
  }
  const int32_t band_h = band_bottom - band_top;
  if (band_h <= 0 || screen_w <= 0) {
    return;  // band entirely off-screen -> no-op
  }

  // Clip the copy width to the scanline buffer bound.
  int32_t copy_w = screen_w;
  if (copy_w > kScrollMaxWidth) {
    copy_w = kScrollMaxWidth;
  }

  // Shift distance in pixels (unsigned magnitude).
  const int32_t shift =
      (rows >= 0 ? static_cast<int32_t>(rows) : -static_cast<int32_t>(rows)) *
      cell_h;

  if (rows == 0 || shift >= band_h) {
    // No net scroll, or the shift clears the whole band: just fill it.
    tft.fillRect(0, band_top, copy_w, band_h, fill);
    return;
  }

  // One scanline of pixels, reused per row (bounded, no heap).
  static uint16_t line_buf[kScrollMaxWidth];

  if (rows > 0) {
    // Scroll UP: move each source row to `shift` pixels above it. Copy from the
    // top of the band downward so sources are read before being overwritten.
    for (int32_t y = band_top + shift; y < band_bottom; ++y) {
      tft.readRect(0, y, copy_w, 1, line_buf);
      tft.pushRect(0, y - shift, copy_w, 1, line_buf);
    }
    // Fill the vacated rows at the bottom of the band.
    tft.fillRect(0, band_bottom - shift, copy_w, shift, fill);
  } else {
    // Scroll DOWN: move each source row `shift` pixels below it. Copy from the
    // bottom of the band upward so sources are read before being overwritten.
    for (int32_t y = band_bottom - 1 - shift; y >= band_top; --y) {
      tft.readRect(0, y, copy_w, 1, line_buf);
      tft.pushRect(0, y + shift, copy_w, 1, line_buf);
    }
    // Fill the vacated rows at the top of the band.
    tft.fillRect(0, band_top, copy_w, shift, fill);
  }
}

// -- render_image (DRAW_IMAGE 0x05) -----------------------------------------
//
// Render a DRAW_IMAGE payload on `tft`.
//
// Payload layout (little-endian, host `_DRAW_IMAGE_HEADER = "<HHHH"`):
//   x(2) y(2) w(2) h(2) then w*h*2 raw RGB565 bytes.
//
// The pixel bytes are blitted directly from the payload pointer with
// tft.pushImage(x, y, w, h, (const uint16_t*)data) — no copy, no allocation.
// The RGB565 bytes are interpreted as native-endian uint16 (the order TFT_eSPI
// pushImage expects); the splash converter on the host MUST emit
// little-endian/native-endian RGB565 to match (documented in ai-decisions.md).
// The payload length is validated to equal header(8) + w*h*2; a short or
// malformed payload is skipped entirely. TFT_eSPI clips any off-screen pixels
// natively, so no bounds skip is applied here (parallels render_rect).
inline void render_image(TFT_eSPI& tft, const uint8_t* payload, uint16_t len) {
  if (payload == nullptr || len < kDrawImageHeaderLen) {
    return;  // malformed -> skip
  }

  const uint16_t x = read_u16le(payload, 0);
  const uint16_t y = read_u16le(payload, 2);
  const uint16_t w = read_u16le(payload, 4);
  const uint16_t h = read_u16le(payload, 6);

  // Required pixel-data length for a w*h RGB565 block (2 bytes/pixel).
  const uint32_t need =
      static_cast<uint32_t>(kDrawImageHeaderLen) +
      static_cast<uint32_t>(w) * static_cast<uint32_t>(h) * 2u;
  if (need > len) {
    return;  // short payload -> skip (don't blit past the buffer)
  }
  if (w == 0 || h == 0) {
    return;  // nothing to draw
  }

  const uint16_t* pixels =
      reinterpret_cast<const uint16_t*>(payload + kDrawImageHeaderLen);
  tft.pushImage(x, y, w, h, pixels);
}

}  // namespace cyd_display_link

#endif  // CYD_DISPLAY_LINK_RENDER_H
