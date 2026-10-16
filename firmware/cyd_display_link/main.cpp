// main.cpp — CYD Display Link firmware entry point (setup/loop)
//
// Arduino sketch for the Cheap Yellow Display (CYD): an ESP32 dev board driving
// an ILI9341 TFT over SPI via the TFT_eSPI library (Req 2.1). It receives the
// length-prefixed drawing-command protocol produced by the host
// `whiskerframe.protocol` module, decodes complete frames with
// `cyd_display_link::FrameDecoder` (frame.h), and renders the DRAW_TEXT /
// DRAW_RECT / DRAW_CELLS / SCROLL / DRAW_IMAGE commands with the helpers in
// render.h.
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

// Rear RGB LED pins (CYD ESP32-2432S028). Active-LOW (common anode to 3.3V).
// Driven HIGH at boot to turn OFF and prevent permanent red LED glow.
static const uint8_t kPinRgbRed = 4;
static const uint8_t kPinRgbGreen = 16;
static const uint8_t kPinRgbBlue = 17;

// -- Globals -----------------------------------------------------------------

// The single TFT_eSPI display driver instance. Pins/driver are configured via
// the build flags in platformio.ini (ILI9341, CYD pinout).
static TFT_eSPI tft = TFT_eSPI();

// Byte-at-a-time frame decoder for the serial command stream.
static cyd_display_link::FrameDecoder decoder;

// Low-power display sleep state tracking.
static bool is_sleeping = false;

// Host supervisory watchdog tracking (REQ-HW-07, DEC-W18).
// Supervise host activity over UART; if link freezes >60s, render crash warning.
static const unsigned long kHostWatchdogTimeoutMs = 60000;
static unsigned long last_packet_time = 0;
static bool host_ever_seen = false;
static bool watchdog_warning_active = false;

// -- Dispatch ----------------------------------------------------------------

// Route one complete, validated frame from `decoder` to the matching renderer.
// Called only after decoder.feed() returns true, so the opcode is known and the
// payload/payload_len are valid until the next feed() (Req 1.2, 2.1).
static void dispatch(cyd_display_link::FrameDecoder& dec) {
  last_packet_time = millis();
  host_ever_seen = true;
  if (watchdog_warning_active) {
    watchdog_warning_active = false;
  }

  if (is_sleeping && dec.opcode() != cyd_display_link::kOpcodeSleep) {
    tft.writecommand(ILI9341_SLPOUT);
    delay(120);
    tft.writecommand(ILI9341_DISPON);
    pinMode(TFT_BL, OUTPUT);
    digitalWrite(TFT_BL, HIGH);
    is_sleeping = false;
  }

  switch (dec.opcode()) {
    case cyd_display_link::kOpcodeDrawText:
      cyd_display_link::render_text(tft, dec.payload(), dec.payload_len());
      break;
    case cyd_display_link::kOpcodeDrawRect:
      cyd_display_link::render_rect(tft, dec.payload(), dec.payload_len());
      break;
    case cyd_display_link::kOpcodeDrawCells:
      cyd_display_link::render_cells(tft, dec.payload(), dec.payload_len());
      break;
    case cyd_display_link::kOpcodeScroll:
      cyd_display_link::render_scroll(tft, dec.payload(), dec.payload_len());
      break;
    case cyd_display_link::kOpcodeDrawImage:
      cyd_display_link::render_image(tft, dec.payload(), dec.payload_len());
      break;
    case cyd_display_link::kOpcodeSleep:
      cyd_display_link::render_sleep(tft, dec.payload(), dec.payload_len());
      is_sleeping = true;
      break;
    // kOpcodeClear / kOpcodeFlush are reserved (see design "Opcodes"); the
    // frame layer accepts them, but they are outside the current render surface,
    // so any other known opcode is intentionally a no-op.
    default:
      break;
  }
}

// -- Arduino entry points ----------------------------------------------------

// Boot: initialize the ILI9341 display and open the serial interface (Req 2.2).
void setup() {
  // Turn off rear RGB LED (active-LOW) on boot to avoid permanent red glow.
  digitalWrite(kPinRgbRed, HIGH);
  digitalWrite(kPinRgbGreen, HIGH);
  digitalWrite(kPinRgbBlue, HIGH);
  pinMode(kPinRgbRed, OUTPUT);
  pinMode(kPinRgbGreen, OUTPUT);
  pinMode(kPinRgbBlue, OUTPUT);

  tft.init();
  tft.setRotation(kDisplayRotation);
  // This CYD panel reports colours inverted (red<->cyan, white<->black, etc.)
  // under the default TFT_eSPI setup, so flip the panel inversion. Empirically
  // determined on-device: pure RGB565 primaries showed as their complements
  // until invertDisplay(true) was applied.
  tft.invertDisplay(true);
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

  // Supervisory host watchdog check (REQ-HW-07, DEC-W18)
  // If host stops communicating for >60s while active, display recovery warning.
  if (host_ever_seen && !is_sleeping) {
    const unsigned long now = millis();
    if (!watchdog_warning_active && (now - last_packet_time > kHostWatchdogTimeoutMs)) {
      watchdog_warning_active = true;
      tft.fillRect(0, 0, 320, 16, TFT_RED);
      tft.setTextColor(TFT_WHITE, TFT_RED);
      tft.setTextSize(1);
      tft.drawString("! HOST LINK LOST (>60s) - RECOVERY", 4, 4);
    }
  }
}
