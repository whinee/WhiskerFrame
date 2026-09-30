// main.cpp — CYD Display Link firmware entry point (setup/loop)
//
// Arduino sketch for the Cheap Yellow Display (CYD): an ESP32 dev board driving
// an ILI9341 TFT over SPI via the TFT_eSPI library (Req 2.1). It receives the
// length-prefixed drawing-command protocol produced by the host
// `whiskerframe.protocol` module, decodes complete frames with
// `cyd_display_link::FrameDecoder` (frame.h), and renders the DRAW_TEXT /
// DRAW_RECT commands with the helpers in render.h.
//
// Boot (setup):   initialize the display and open the serial link (Req 2.2).
// Steady state (loop): drain the serial RX buffer one byte at a time through
//                      the frame decoder and dispatch each complete, valid,
//                      known-opcode frame to the matching renderer (Req 1.2,
//                      2.1). Frames that fail CRC / carry an unknown opcode /
//                      overrun the buffer are discarded inside FrameDecoder,
//                      which resynchronizes to the next SOF so subsequent
//                      commands still process (Req 1.4).
//
// Design refs: "CYD Firmware", "Module sketch". Requirements: 2.1, 2.2, 1.2.

#include <Arduino.h>
#include <TFT_eSPI.h>

#include "frame.h"
#include "render.h"

// -- Configuration ----------------------------------------------------------

// Serial baud rate. MUST match `monitor_speed` in platformio.ini and the host
// transport (Req 2.2).
static const unsigned long kSerialBaud = 115200;

// Display rotation. The CYD panel is natively 240x320 portrait (TFT_WIDTH /
// TFT_HEIGHT in platformio.ini); rotation 1 selects landscape (320x240), the
// usual CYD viewing orientation. render.h checks bounds against the runtime
// tft.width()/tft.height(), which already reflect this rotation, so the Req 2.5
// bounds contract stays correct here.
static const uint8_t kDisplayRotation = 1;

// -- Globals -----------------------------------------------------------------

// The single TFT_eSPI display driver instance. Pins/driver are configured via
// the build flags in platformio.ini (ILI9341, CYD pinout).
static TFT_eSPI tft = TFT_eSPI();

// Byte-at-a-time frame decoder for the serial command stream.
static cyd_display_link::FrameDecoder decoder;

// -- Dispatch ----------------------------------------------------------------

// Route one complete, validated frame from `decoder` to the matching renderer.
// Called only after decoder.feed() returns true, so the opcode is known and the
// payload/payload_len are valid until the next feed() (Req 1.2, 2.1).
static void dispatch(cyd_display_link::FrameDecoder& dec) {
  switch (dec.opcode()) {
    case cyd_display_link::kOpcodeDrawText:
      cyd_display_link::render_text(tft, dec.payload(), dec.payload_len());
      break;
    case cyd_display_link::kOpcodeDrawRect:
      cyd_display_link::render_rect(tft, dec.payload(), dec.payload_len());
      break;
    // kOpcodeClear / kOpcodeFlush are reserved (see design "Opcodes"); the
    // frame layer accepts them, but the required render surface is DRAW_TEXT +
    // DRAW_RECT (Req 1.3), so any other known opcode is intentionally a no-op.
    default:
      break;
  }
}

// -- Arduino entry points ----------------------------------------------------

// Boot: initialize the ILI9341 display and open the serial interface (Req 2.2).
void setup() {
  tft.init();
  tft.setRotation(kDisplayRotation);
  tft.fillScreen(TFT_BLACK);
  Serial.begin(kSerialBaud);
}

// Steady state: drain every byte currently available from the serial link
// through the frame decoder, dispatching each frame it completes. Draining the
// whole RX buffer per loop keeps latency low without blocking on bytes that
// have not arrived yet (Req 1.2, 2.1).
void loop() {
  while (Serial.available() > 0) {
    const int b = Serial.read();
    if (b < 0) {
      break;  // nothing actually available; guard against a spurious -1
    }
    if (decoder.feed(static_cast<uint8_t>(b))) {
      dispatch(decoder);
    }
  }
}
