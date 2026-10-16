# Domain 03: Terminal & Display Subsystem (REQ-TERM)

**Specification Prefix:** `REQ-TERM`  
**System Layer:** Display Link, Wire Protocol, Terminal Emulation & Typography  
**Primary Implementations:** `whiskerframe/protocol.py`, `whiskerframe/terminal.py`, `pi/terminal/`, `firmware/cyd_display_link/`  
**Acceptance Test Plans:** `ATP-01-TERM-LOGIN`, `ATP-03-TYPO-GEOMETRY`, `ATP-10-DISP-DRAW-IMAGE`, `ATP-11-TERM-WORKSPACES`  
**Target Milestone:** `v0` (Demo Prototype) / `v1` (Field Hardened)  

---

## 1. Scope & Domain Objectives

The Terminal & Display Subsystem is the central user interaction engine of the cyberdeck. It spans pure Python wire protocol serialization on the Raspberry Pi Zero 2W, serial transport over USB-UART (CH340 at 115200 baud), double-buffered VT100 character grid emulation, dynamic multi-geometry font rendering, i3-style multi-PTY virtual workspaces, and low-level C++/TFT_eSPI firmware running on the ESP32 coprocessor.

---

## 2. Formal Requirements & Normative Specifications

### REQ-TERM-01 [v0]: CYD Display Interface
- **Requirement:** The terminal display MUST be driven by an ESP32-2432S028 (CYD) module running an ILI9341 320x240 LCD over USB-Serial (CH340) at 115200 baud runtime, locked exclusively by `terminal.service`.
- **Rationale:** Offloading graphics rendering and LCD driving to a dedicated micro-controller isolates the Pi Zero 2W from SPI bus stalls and GUI frame-buffer overhead.
- **Traceability:** `DEC-W5`, `DEC-W14`.

### REQ-TERM-02 [v0]: 53-Column VT100 Character Grid
- **Requirement:** The host Python bridge (`whiskerframe.terminal`) MUST maintain terminal state via a 53-column by 30-row VT100 grid emulator (6x8 font cells), transmitting incremental cell runs (`DRAW_CELLS`, opcode `0x03`) to minimize UART bandwidth.
- **Rationale:** 115200 baud provides ~11.5 KB/s throughput. Transmitting raw bitmaps would yield <0.1 fps. Cell diffing achieves 60+ updates/s at <500 bytes/s.
- **Traceability:** `DEC-W6`, `DEC-W29`.

### REQ-TERM-03 [v1]: Intermediate Typography & 8x12 Font
- **Requirement:** The firmware MUST support compile-time intermediate font geometries (e.g. 8x12 font yielding 40 columns by 20 rows) using anti-aliased bitmap fonts to improve legibility over raw 6x8 bitmap scaling.
- **Rationale:** 6x8 font can cause eye strain during prolonged coding sessions; 8x12 provides an optimal compromise between readability and column density.
- **Traceability:** `DEC-W30`, `DEC-W32`, `TSK-18`.

### REQ-TERM-04 [v0]: Compact Interactive Prompts
- **Requirement:** Interactive shell prompts in the CYD terminal MUST NOT exceed 3 characters (`n~ ` for neko, `g~ ` for guest, `r# ` for root) via `/etc/profile.d/cyd_prompt.sh`, preventing line-wrap truncation on the 53-column display.
- **Rationale:** Standard verbose prompts (`user@hostname:/long/path$`) consume 40+ columns, leaving virtually no room for commands.
- **Traceability:** `DEC-W30`.

### REQ-TERM-05 [v0]: Lightweight Multi-PTY Workspaces
- **Requirement:** The terminal bridge MUST support multiplexing up to 4 concurrent virtual workspaces (`WS1` through `WS4`) mapped to CardKB chords (`Fn+1`..`4`), maintaining isolated PTY master file descriptors and child shells while consuming <100 KB total RAM.
- **Rationale:** Delivers modern desktop multi-tasking without the heavy memory overhead of full window managers.
- **Traceability:** `DEC-W36`, `TSK-22`.

### REQ-TERM-06 [v0]: Low-Flicker Telemetry Status Line
- **Requirement:** The terminal interface MUST provide a dedicated telemetry status line on row 0/29 updated at a throttled 2.0s cadence using cell-differential rendering (`grid.diff`) consuming <10 bytes per normal tick, reading asynchronously from cached telemetry files without direct I2C bus stalls.
- **Rationale:** Operators require real-time battery and thermal awareness without screen flickering or terminal lag.
- **Traceability:** `DEC-W37`, `TSK-23`.

### REQ-TERM-07 [v0]: Coprocessor Binary Image Blitting
- **Requirement:** The display subsystem MUST support blitting raw binary RGB565 images (`0x05 DRAW_IMAGE`) using bounded scanline chunk streaming (2 rows, 1,280 bytes) and safe post-render grid repainting, preventing coprocessor FIFO overrun and character corruption.
- **Rationale:** Enables full-color illustrations, diagrams, and boot splashes while keeping memory consumption bounded.
- **Traceability:** `DEC-W35`, `TSK-21`.

### REQ-TERM-08 [v0]: Standardized xterm Emulation & Clean Clear
- **Requirement:** The terminal emulator MUST standardize on `TERM=xterm`, support 16-color ANSI rendering, and execute full blank-wash refreshes on `clear` (`\x1b[2J`) without dirty cell persistence.
- **Rationale:** Ensures standard command-line tools (`htop`, `vim`, `less`) render accurately.
- **Traceability:** `DEC-W31`, `TSK-17`.

---

## 3. Wire Protocol & Serialization Architecture

### Frame Specification
Framing is implemented in `whiskerframe/protocol.py` (host) and `firmware/cyd_display_link/frame.h` (coprocessor):
```text
Byte Offset:   0       1       2       3       4 ... LEN+2     LEN+3
Field:       [ SOF ] [ LEN_L ] [ LEN_H ] [ OP ] [ PAYLOAD... ] [ CRC8 ]
Value:        0xA5     (uint16 LE)       uint8     (bytes)      uint8
```

### Opcodes:
- `0x01 DRAW_TEXT`: Render text string at pixel coordinate with anchor.
- `0x02 DRAW_RECT`: Draw filled or outline rectangle.
- `0x03 DRAW_CELLS`: Draw contiguous cell run `(col, row, fg, bg, font_size, len, text)`.
- `0x04 SCROLL`: Hardware scroll band `(rows, fill_color, top_row, bottom_row)`.
- `0x05 DRAW_IMAGE`: Stream RGB565 binary chunk `(x, y, w, h, data)`.
- `0x06 SLEEP`: Display poweroff, backlight PWM 0%, CPU 80 MHz.

---

## 4. Multi-Geometry Typography Engine

The system supports 4 runtime geometries switched via `Fn + Backspace`:
1. **Font 1 (6x8 px):** 53 cols x 30 rows (Default density, 1,590 cells).
2. **Font 5 (8x12 px):** 40 cols x 20 rows (Intermediate high-legibility, 800 cells).
3. **Font 2 (12x16 px):** 26 cols x 15 rows (Large text, 390 cells).
4. **Font 3 (18x24 px):** 17 cols x 10 rows (Presentation mode, 170 cells).

Changing font size dynamically recalculates `TerminalGeometry`, executes `ioctl(pty_fd, TIOCSWINSZ, &ws)`, sends `SIGWINCH` to child shells, clears screen grids, and repaints with zero artifacts.

---

## 5. Verification & Acceptance Criteria

- **`ATP-01-TERM-LOGIN`:** PAM authentication, password masking, circular user selection.
- **`ATP-03-TYPO-GEOMETRY`:** Font cycling via `0x8B`, 8x12 typography correctness.
- **`ATP-10-DISP-DRAW-IMAGE`:** Chunked image blitting (2 rows, 1,280B), clean terminal restoration.
- **`ATP-11-TERM-WORKSPACES`:** Multi-PTY spawning, chord switching (`0x81`..`0x84`), memory ceiling <100 KB.
