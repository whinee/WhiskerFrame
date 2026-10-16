# Domain 02: Hardware UX, Ergonomics & Aesthetics (REQ-UX)

**Specification Prefix:** `REQ-UX`  
**System Layer:** Physical Interaction, Visual Identity & Aesthetics  
**Primary Implementations:** `pi/terminal/theme.py`, `pi/terminal/splash.py`, `pi/bin/goodbye_hook`, `assets/themes/`  
**Acceptance Test Plan:** `ATP-05-LIFE-GOODBYE`, `ATP-10-DISP-DRAW-IMAGE`  
**Target Milestone:** `v0` (Demo Prototype) / `v1` (Field Hardened)  

---

## 1. Scope & Domain Objectives

The Hardware UX & Ergonomics domain defines the physical form factor, tactile input feedback, sensory load management, visual design language, and boot/shutdown presentation of the WhiskerFrame Cyberdeck. The interface blends a distinct cyberpunk cat-themed visual identity ("piiiiink" aesthetic) with rigorous WCAG 2.1 AA accessibility contrast standards, ensuring maximum usability during mobile transit.

---

## 2. Formal Requirements & Normative Specifications

### REQ-UX-01 [v0]: Physical Envelope
- **Requirement:** The assembled cyberdeck MUST fit within an A5 perimeter (148 x 210 mm) and SHOULD NOT exceed 70 mm in thickness (inclusive of rubber drop bumpers and SSD shock mounts).
- **Rationale:** Ensures handheld one-handed or two-handed portability and compatibility with standard messenger bags without specialized cases.
- **Traceability:** `10.01`, `F10.01`, `DEC-W17`, `DEC-W22`.

### REQ-UX-02 [v0]: Tactile Hardware Input
- **Requirement:** The deck MUST feature physical switches with positive tactile feedback (not capacitive glass) to support thumb-typing during mobile transit.
- **Rationale:** Capacitive glass keyboards require visual focus and fail under rain or sweat; tactile click switches permit blind thumb-typing.
- **Traceability:** `1.07`, `3.02`.

### REQ-UX-03 [v0]: Anti-Distraction Environment
- **Requirement:** The operating system MUST NOT install or run notification daemons, push services, or advertising engines that interrupt the fullscreen terminal workflow.
- **Rationale:** Focus and cognitive endurance are paramount; the cyberdeck is a dedicated operational tool, not a consumer distraction platform.
- **Traceability:** `1.04`.

### REQ-UX-04 [v0]: Declarative UI Customization
- **Requirement:** The terminal subsystem MUST support user-configurable color themes, typography, status-line fields, and screen geometry via `.whiskerframe.yaml` and on-device configuration files.
- **Rationale:** Allows tailoring contrast, colors, and layout for varying operational lighting.
- **Traceability:** `A.02`, `5.01`, `DEC-W19`.

### REQ-UX-05 [v0]: Boot Splash Display
- **Requirement:** The device MUST display a boot splash screen composited with the WhiskerFrame visual identity, rendered within 1–2 seconds of terminal initialization, holding for 3.0 seconds before presenting the login interface.
- **Rationale:** Provides instant hardware confirmation of functional display pipeline during cold boot.
- **Traceability:** `5.09`, `DEC-W19`, `DEC-W30`.

### REQ-UX-06 [v1]: Physical Control Switches
- **Requirement:** The system MUST provide dedicated physical toggle switches for hardware radio kill (Wi-Fi/Bluetooth), master audio mute, and buzzer silence to enforce silent operation in sensitive settings.
- **Rationale:** Physical switches guarantee uncompromised state verification even if software is compromised.
- **Traceability:** `3.08`, `4.07`, `4.11`.

### REQ-UX-07 [v2+]: LED Matrix Deferral
- **Requirement:** Mounting of an auxiliary MAX7219 8x8 LED matrix is formally deferred to `v2+` to preserve chassis thinness and prevent RF/EMI interference inside the enclosure.
- **Rationale:** Space and thermal budgets take precedence over decorative displays.
- **Traceability:** `F-05.02`, `DEC-W19`.

### REQ-UX-08 [v0]: Resource-Efficient Glyph Caching
- **Requirement:** The CYD coprocessor font subsystem MUST restrict SPI RAM glyph caching to essential 7-bit ASCII, punctuation, and standard VT100 box-drawing characters, rejecting full Unicode/emoji glyph sets to prevent coprocessor heap exhaustion.
- **Rationale:** The ESP32 heap must be protected; full CJK/Unicode sets would exhaust memory and cause crashloops.
- **Traceability:** `F-05.03`, `DEC-W19`.

### REQ-UX-09 [v0]: Orderly Goodbye & Reboot Splash
- **Requirement:** The system MUST execute an orderly goodbye sequence on systemd shutdown/reboot targets (`cyberdeck-goodbye-shutdown.service` rendering `"bai baiii!"`, `cyberdeck-goodbye-reboot.service` rendering `"brb :3"`), blitting a centered 128x128 doodle within a hard 8.0-second execution window before blanking the display.
- **Rationale:** Gives clear visual notification that filesystems are unmounted and power may be physically toggled off.
- **Traceability:** `WS-3`, `DEC-W29`, `DEC-W30`.

---

## 3. Actual Implementation Architecture

### 3.1 The "piiiiink" A11y Theme
Located at `assets/themes/piiiiink-a11y.json` and loaded via `pi/terminal/theme.py`:
- **Background Color:** Blurple `#191A28` (RGB565: `0x18C5`).
- **Foreground Color:** Lavender `#AE89FF` (RGB565: `0xAE7F`).
- **Accent Pink:** `#FD7DA6` (RGB565: `0xFBEE`).
- **Contrast Rationale:** Audited against WCAG 2.1 AA. Normal text achieves $\ge 4.5:1$ contrast ratio; headers and status indicators achieve $\ge 7:1$.
- **High-Contrast Sunlight Theme:** `assets/themes/mono-high-contrast.json` provides an inverted monochrome palette (`#000000` on `#FFFFFF`, achieving 21.0:1 contrast) for direct sunlight readability.

### 3.2 Boot Splash Pipeline (`pi/terminal/splash.py`)
1. Pre-converted 320x240 RGB565 binary image (`assets/images/cess/Lyra and Dreanne Christmas Night Market.rgb565`, 153,600 bytes).
2. Transmitted via `whiskerframe.transport.SerialTransport` using opcode `0x05 DRAW_IMAGE` in 1,280-byte scanline chunks (2 rows per chunk).
3. Holds for 3.0 seconds via `time.sleep(3.0)`.
4. Fully wiped using a whole-panel `DRAW_RECT` (`0x02`) in blurple before rendering the login view (`pi/terminal/login_view.py`), eliminating visual artifacts.

### 3.3 Goodbye Hooks & Systemd Integration (`pi/bin/goodbye_hook`)
- Systemd units:
  - `/etc/systemd/system/cyberdeck-goodbye-shutdown.service`
  - `/etc/systemd/system/cyberdeck-goodbye-reboot.service`
- Hook implementation (`pi/bin/goodbye_hook`):
  - Resolves active serial port (`/dev/ttyUSB0`).
  - Reads pre-rendered 128x128 RGB565 cat doodle (`doodle.rgb565`).
  - Blits centered at $(96, 40)$ with the text caption `"bai baiii!"` (shutdown) or `"brb :3"` (reboot).
  - Emits opcode `0x06 SLEEP` on shutdown, powering off ILI9341 display and backlight.

---

## 4. Verification & Acceptance Criteria

Compliance is validated by **`ATP-05-LIFE-GOODBYE`**:
1. Goodbye hooks execute cleanly within the 8.0s systemd timeout window.
2. Centered doodle and caption render without serial bus contention.
3. Wire opcode `0x06 SLEEP` is verified over serial, confirming low-power display sleep.
4. WCAG 2.1 AA contrast ratios verified across all theme tokens in `pi/terminal/theme.py`.
