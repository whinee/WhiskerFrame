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

// -- Little-endian payload readers ------------------------------------------

// Read a little-endian uint16 from `p` at byte offset `off`.
inline uint16_t read_u16le(const uint8_t* p, uint16_t off) {
  return static_cast<uint16_t>(p[off]) |
         (static_cast<uint16_t>(p[off + 1]) << 8);
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

}  // namespace cyd_display_link

#endif  // CYD_DISPLAY_LINK_RENDER_H
