# Domain 04: Input Subsystem & CardKB Ergonomics (REQ-INP)

**Specification Prefix:** `REQ-INP`  
**System Layer:** Hardware Matrix Input, Debouncing, Modifier Latches & Alert Arbitration  
**Primary Implementations:** `pi/cardkb/reader.py`, `pi/terminal/bridge.py`, `whiskerframe/alerts.py`, `pi/bin/keys`  
**Acceptance Test Plans:** `ATP-02-INP-CTRL-LATCH`, `ATP-13-PWR-SENSORY-PROFILES`  
**Target Milestone:** `v0` (Demo Prototype) / `v1` (Field Hardened)  

---

## 1. Scope & Domain Objectives

The Input Subsystem governs physical user entry, hardware matrix scanning, I2C bus error recovery, software debouncing, sequential modifier latching, visual LED feedback, and multi-modal sensory alert arbitration. The primary input hardware is the 50-key M5Stack CardKB v1.1. Because the hardware lacks physical `Ctrl`, `Alt`, and function keys, the subsystem provides advanced software state machines to deliver full VT100 control codes without hardware modifications.

---

## 2. Formal Requirements & Normative Specifications

### REQ-INP-01 [v0]: CardKB Hardware Interface & Debounce
- **Requirement:** The input subsystem MUST read the M5Stack CardKB 50-key matrix via I2C-0 (`0x5F`) using `/dev/i2c-0` (Pins 27/28), filtered by a 30 ms identical-byte debounce window and a C0/ASCII/Fn-layer whitelist to eliminate power-rail ripple artifacts.
- **Rationale:** Breadboard and portable jumper connections suffer power rail ripple from cellular modems and CPU spikes, causing spurious phantom keypresses without filtering.
- **Traceability:** `DEC-W6`, `TSK-01`.

### REQ-INP-02 [v0]: Key-to-Glyph Interactive Latency
- **Requirement:** End-to-end latency from physical CardKB keypress to display glyph illumination MUST NOT exceed 50 ms under nominal typing loads.
- **Rationale:** Interactive typing responsiveness is critical; latencies above 50 ms feel sluggish and degrade typing rhythm.
- **Traceability:** Section 4.13.

### REQ-INP-03 [v0]: Sequential Sticky Ctrl Latch
- **Requirement:** To resolve the physical absence of a Control key on CardKB, the input bridge MUST implement a sequential sticky Ctrl state machine triggered by `Fn+Tab` (`0x8C` or `Fn+Backspace` `0x8B`), masking the next alphanumeric key with `& 0x1F` to emit standard C0 control codes (`Ctrl+C` = `0x03`, `Ctrl+D` = `0x04`). The armed state MUST automatically expire after 3.0 seconds, on toggle press, or on invalid key entry.
- **Rationale:** Enables standard Unix terminal signals (`Ctrl-C`, `Ctrl-D`, `Ctrl-Z`, `Ctrl-L`) on a 50-key physical layout.
- **Traceability:** `WS-2`, `DEC-W29`, `ATP-02-INP-CTRL-LATCH`.

### REQ-INP-04 [v0]: Visual & NeoPixel Latch Feedback
- **Requirement:** The armed Ctrl latch state MUST be visually indicated simultaneously by recoloring the terminal cursor cell to bright yellow (`theme.ansi[11]`) and illuminating the CardKB onboard SK6812 NeoPixel LED yellow (`RGB 255, 200, 0` via I2C opcode `0x13`), clearing immediately upon latch release.
- **Rationale:** Dual feedback guarantees that the operator always knows the modifier state before striking a key, preventing accidental command abortion.
- **Traceability:** `DEC-W29`, `DEC-W30`, `TSK-16`.

### REQ-INP-05 [v0]: 53-Column Key Cheatsheet
- **Requirement:** The system MUST provide an on-demand, 53-column CLI reference tool (`keys`) displaying all CardKB keybindings, modifier combinations, and symbol chords without requiring external documentation.
- **Rationale:** Operators need immediate in-terminal access to obscure chords (such as curly braces, pipes, and tildes).
- **Traceability:** `DEC-W29`, `TSK-12`.

### REQ-INP-06 [v1]: Modal Rotary Encoder
- **Requirement:** The input subsystem SHOULD support a hardware rotary encoder wired to the ESP32 coprocessor with a push-button cycle for terminal volume, backlight brightness, and font size adjustment.
- **Rationale:** Tactile rotary controls provide fast adjustments without occupying screen space.
- **Traceability:** Section 4.07, `DEC-W17`.

### REQ-INP-07 [v1]: Tactile Haptic & Piezo Alerts
- **Requirement:** The deck SHALL support a vibration motor and piezo buzzer for critical system state warnings (battery <5%, earlyoom kills, emergency thermal shutdown) governed by configurable audio profiles.
- **Rationale:** Audio/haptic warnings notify the operator of urgent battery depletion even when not looking at the screen.
- **Traceability:** Section 4.09, `REQ-ENV-04`, `whiskerframe/alerts.py`.

### REQ-INP-08 [v1]: Cognitive Sensory Overload Toggle
- **Requirement:** The UI and alert system MUST provide a single-action chord/switch to instantly silence all auxiliary displays, tickers, and audible buzzers, restricting output to the primary terminal prompt.
- **Rationale:** Prevents sensory overload during high-stress troubleshooting or neurodivergent overwhelm.
- **Traceability:** Section 4.12, `pi/bin/profile`.

---

## 3. Actual Implementation Architecture

### 3.1 CardKB Driver (`pi/cardkb/reader.py`)
- Communicates directly over `/dev/i2c-0` using Python `os.open`, `os.read`, `os.write`.
- **Bus Self-Healing:** Catches `OSError` (e.g. `EBUSY`, `ENODEV`, `EIO`), backs off for 100ms, and reopens `/dev/i2c-0` without terminating calling processes.
- **Debounce Window:** Enforces a 30ms window where identical consecutive non-zero bytes are suppressed.

### 3.2 Sticky Ctrl Latch State Machine (`pi/terminal/bridge.py`)
```python
# Latch arming
if key == 0x8C: # Fn+Tab
    if not self._ctrl_latched:
        self._ctrl_latched = True
        self._ctrl_latched_at = time.monotonic()
        self._set_cursor_color(theme.ansi[11]) # Yellow
        self._set_cardkb_neopixel(255, 200, 0) # Yellow LED
    else:
        self._disarm_ctrl_latch()
    return

# Latch evaluation
if self._ctrl_latched:
    if time.monotonic() - self._ctrl_latched_at > 3.0:
        self._disarm_ctrl_latch()
    elif key in _CTRL_VALID_CHARS:
        ctrl_code = key & 0x1F
        self._disarm_ctrl_latch()
        self._write_to_pty(bytes([ctrl_code]))
        return
    else:
        self._disarm_ctrl_latch()
```

### 3.3 Sensory Alert Arbitration (`whiskerframe/alerts.py`)
Alerts evaluated by `evaluate_alerts(metrics)` pass through sensory profile arbitration:
- If `profile == "classroom"`, `audible` is forced `False`.
- If `profile == "office"`, buzzer pulses are clamped to 25% volume.
- If `profile == "commute"`, buzzer pulses use 100% volume.
- If `overload == True`, all audible and haptic signals are suppressed (`audible = False`, `haptic = False`), routing warnings strictly to the terminal status bar.

---

## 4. Verification & Acceptance Criteria

- **`ATP-02-INP-CTRL-LATCH`:** Validates key filtering, debounce timing, 3.0s timeout auto-cancel, double-tap toggle cancel, and NeoPixel I2C payload `[0x13, 255, 200, 0]`.
- **`ATP-13-PWR-SENSORY-PROFILES`:** Validates sensory arbitration, classroom silence, and overload clamp suppression.
