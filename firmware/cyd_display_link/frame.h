// frame.h — CYD Display Link serial frame decoder + CRC8
//
// Header-only frame decoder for the CYD_Firmware (ESP32 + ILI9341, Arduino /
// TFT_eSPI). Decodes the length-prefixed command protocol produced by the host
// `whiskerframe.protocol` module and defined in the design "Serial Protocol"
// section.
//
// Wire format (little-endian multi-byte integers):
//
//   +-------+--------+--------+---------------------+--------+
//   | SOF   | LEN    | OPCODE | PAYLOAD (LEN-1 B)   | CRC8   |
//   | 0xA5  | uint16 | uint8  | opcode-specific     | uint8  |
//   +-------+--------+--------+---------------------+--------+
//
//   SOF    : 0xA5 start-of-frame marker (used to resynchronize).
//   LEN    : uint16 LE, number of bytes in OPCODE + PAYLOAD (i.e. 1 + payload).
//   OPCODE : uint8 command selector.
//   PAYLOAD: opcode-specific, LEN-1 bytes.
//   CRC8   : uint8 CRC-8 computed over OPCODE + PAYLOAD.
//
// The decoder is a byte-at-a-time state machine that recovers valid frames from
// an arbitrarily corrupted stream: on a bad CRC, an unknown opcode, or a LEN
// that exceeds the receive buffer, it discards the in-progress frame and
// returns to hunting for the next SOF, so subsequent frames still process
// (Requirement 1.4). Design refs: Req 1.2, 1.4, 2.1.
//
// ---------------------------------------------------------------------------
// CRC8 algorithm (MUST match host `whiskerframe/protocol.py::crc8`, task 6.1)
// ---------------------------------------------------------------------------
//   Name        : CRC-8/SMBUS (a.k.a. "CRC-8", the Maxim/Dallas base variant)
//   Width       : 8 bits
//   Polynomial  : 0x07  (x^8 + x^2 + x + 1)
//   Init        : 0x00
//   RefIn       : false (no input reflection)
//   RefOut      : false (no output reflection)
//   XorOut      : 0x00
//   Check       : 0xF4  (CRC of the ASCII string "123456789")
//
//   Reference Python implementation for protocol.py:
//
//       def crc8(data: bytes) -> int:
//           crc = 0x00
//           for byte in data:
//               crc ^= byte
//               for _ in range(8):
//                   if crc & 0x80:
//                       crc = ((crc << 1) ^ 0x07) & 0xFF
//                   else:
//                       crc = (crc << 1) & 0xFF
//           return crc
//
//   The CRC is computed over OPCODE followed by PAYLOAD bytes (not over SOF or
//   the LEN field).

#ifndef CYD_DISPLAY_LINK_FRAME_H
#define CYD_DISPLAY_LINK_FRAME_H

#include <stdint.h>
#include <stddef.h>

namespace cyd_display_link {

// -- Protocol constants -----------------------------------------------------

// Start-of-frame marker.
static const uint8_t kSOF = 0xA5;

// Known opcodes (see design "Opcodes"). Frames carrying any other opcode are
// discarded during validation (Req 1.4).
static const uint8_t kOpcodeDrawText = 0x01;
static const uint8_t kOpcodeDrawRect = 0x02;
static const uint8_t kOpcodeDrawCells = 0x03;  // run of fixed-cell glyphs
static const uint8_t kOpcodeScroll = 0x04;     // shift a row band up/down
static const uint8_t kOpcodeDrawImage = 0x05;  // raw RGB565 pixel block
static const uint8_t kOpcodeClear = 0x10;
static const uint8_t kOpcodeFlush = 0x1F;

// LEN cap that bounds buffer use and rejects runaway frames. LEN counts
// OPCODE + PAYLOAD, so the maximum payload is (kMaxFrameLen - 1) bytes.
static const uint16_t kMaxFrameLen = 2048;  // ~2 KB

// Compute CRC-8/SMBUS over `len` bytes of `data`. See the header comment for
// the exact parameters; this MUST stay bit-identical to the host crc8().
inline uint8_t crc8(const uint8_t* data, size_t len) {
  uint8_t crc = 0x00;
  for (size_t i = 0; i < len; ++i) {
    crc ^= data[i];
    for (uint8_t bit = 0; bit < 8; ++bit) {
      if (crc & 0x80) {
        crc = static_cast<uint8_t>((crc << 1) ^ 0x07);
      } else {
        crc = static_cast<uint8_t>(crc << 1);
      }
    }
  }
  return crc;
}

// Return true for opcodes the firmware knows how to dispatch. Unknown opcodes
// cause the frame to be discarded (Req 1.4).
inline bool is_known_opcode(uint8_t opcode) {
  return opcode == kOpcodeDrawText || opcode == kOpcodeDrawRect ||
         opcode == kOpcodeDrawCells || opcode == kOpcodeScroll ||
         opcode == kOpcodeDrawImage || opcode == kOpcodeClear ||
         opcode == kOpcodeFlush;
}

// -- Frame decoder ----------------------------------------------------------
//
// Feed one received byte at a time via feed(). When feed() returns true, a
// complete, CRC-valid, known-opcode frame is available and its OPCODE / PAYLOAD
// can be read with opcode() / payload() / payload_len() until the next feed().
class FrameDecoder {
 public:
  FrameDecoder() { reset(); }

  // Feed a single received byte into the state machine.
  //
  // Returns true exactly once per complete, valid frame — when the trailing
  // CRC byte has been consumed and validated. On a bad CRC, an unknown opcode,
  // or an oversized LEN, the in-progress frame is discarded and the decoder
  // resynchronizes to HuntSOF (Req 1.4); such bytes never yield true.
  bool feed(uint8_t b) {
    switch (state_) {
      case State::HuntSOF:
        if (b == kSOF) {
          state_ = State::ReadLen0;
        }
        // Any non-SOF byte is skipped while hunting.
        return false;

      case State::ReadLen0:
        len_ = b;  // low byte
        state_ = State::ReadLen1;
        return false;

      case State::ReadLen1:
        len_ |= static_cast<uint16_t>(b) << 8;  // high byte (LE)
        // Reject empty frames (need at least an opcode) and oversized frames.
        if (len_ == 0 || len_ > kMaxFrameLen) {
          reset();  // discard + resync
          return false;
        }
        body_needed_ = len_;
        body_have_ = 0;
        state_ = State::ReadBody;
        return false;

      case State::ReadBody:
        body_[body_have_++] = b;
        if (body_have_ < body_needed_) {
          return false;
        }
        state_ = State::ReadCRC;
        return false;

      case State::ReadCRC: {
        const uint8_t expected = crc8(body_, body_needed_);
        const bool crc_ok = (expected == b);
        const bool opcode_ok = is_known_opcode(body_[0]);
        if (crc_ok && opcode_ok) {
          // Frame accepted: expose opcode + payload, then arm for the next SOF.
          frame_len_ = body_needed_;
          state_ = State::HuntSOF;
          return true;
        }
        // Bad CRC or unknown opcode: discard and resync (Req 1.4).
        reset();
        return false;
      }
    }
    // Unreachable; defensive resync.
    reset();
    return false;
  }

  // Opcode of the most recently completed valid frame.
  uint8_t opcode() const { return body_[0]; }

  // Pointer to the payload of the most recently completed valid frame.
  // Valid until the next feed() call. Length is payload_len().
  const uint8_t* payload() const { return body_ + 1; }

  // Payload length (bytes) of the most recently completed valid frame,
  // i.e. LEN - 1 (LEN counts OPCODE + PAYLOAD).
  uint16_t payload_len() const {
    return frame_len_ > 0 ? static_cast<uint16_t>(frame_len_ - 1) : 0;
  }

 private:
  enum class State : uint8_t {
    HuntSOF,   // waiting for SOF (0xA5)
    ReadLen0,  // reading LEN low byte
    ReadLen1,  // reading LEN high byte
    ReadBody,  // reading OPCODE + PAYLOAD (LEN bytes)
    ReadCRC,   // reading + validating trailing CRC8
  };

  // Return to hunting for the next SOF, discarding any in-progress frame.
  void reset() {
    state_ = State::HuntSOF;
    len_ = 0;
    body_needed_ = 0;
    body_have_ = 0;
  }

  State state_;
  uint16_t len_;          // LEN field being assembled (OPCODE + PAYLOAD count)
  uint16_t body_needed_;  // bytes expected in body_ for the current frame
  uint16_t body_have_;    // bytes accumulated so far in body_
  uint16_t frame_len_;    // LEN of the last completed valid frame
  uint8_t body_[kMaxFrameLen];  // OPCODE + PAYLOAD accumulator
};

}  // namespace cyd_display_link

#endif  // CYD_DISPLAY_LINK_FRAME_H
