# Product Requirements

## REQ-CAPABILITIES (User-Facing)

* **REQ-CAP-01 (Offline reading)**: The deck MUST support an offline repository of articles (e.g. Wikipedia).
* **REQ-CAP-02 (Local coding)**: The deck MUST support local coding and offline access to Python/Bash manuals, acknowledging the limitation of the small 320x240 screen.
* **REQ-CAP-03 (Text-Only TUI)**: The deck MUST operate strictly as a text-only platform without an LLM running locally.

## REQ-UX (Hardware UX & Ergonomics)

* **REQ-UX-01 (Form Factor)**: The deck MUST fit within an A5 perimeter (148 x 210 mm) and MUST be thinner than 65 mm.
* **REQ-UX-02 (Tactile Input)**: The deck MUST feature physical keys (not glass) to mitigate thumb-typing constraints of standard phones.
* **REQ-UX-03 (Zero Distraction)**: The deck MUST have no push-notification system or ad-supported software interrupting the terminal experience.

## REQ-HW (Hardware Enclosure & Peripherals)

* **REQ-HW-01 (RTC)**: The architecture MUST include an I2C DS3231 Real-Time Clock module so logs and git timestamps sync correctly while off-grid.
* **REQ-HW-02 (Weatherproofing)**: The case MUST be fully enclosed to prevent humidity from damaging the components in tropical (PH) climates.
* **REQ-HW-05 (Physical Alerts & Switches)**: The system MUST include dedicated physical toggle switches for radio (Wi-Fi/LTE) kill, master audio mute, and auxiliary alert (buzzer) mute to ensure operational silence in sensitive environments (3.08, 4.07).
* **REQ-HW-06 (Keyboard & Input MVP)**: The initial version MUST utilize the off-the-shelf CardKB v1.1 module, deferring custom custom PCB/PCB-case design to v2+ (4.02, 4.04).
* **REQ-HW-07 (Rotary Encoder Controls)**: The system SHOULD feature a hardware rotary encoder wired to ESP32 coprocessor mapping rotary position to terminal volume/brightness/font-size/scrolling (4.03, 4.07).

## REQ-ENV (Environmental & Operating Contexts)

* **REQ-ENV-01 (Fanless Rain Resistance)**: The chassis MUST operate with passive (fanless) cooling and incorporate weather-resistant sealing to protect internal electronics during transit exposure (3.05).
* **REQ-ENV-02 (Two-Thumb Handheld Posture)**: The physical chassis balance and keyboard placement MUST support two-thumb typing while handheld without requiring a desk or lap rest (3.02).
* **REQ-ENV-03 (Ambient Light Compensation)**: The display subsystem SHOULD utilize the CYD on-board LDR (light sensor) to dynamically adjust backlight PWM and select high-contrast palettes in bright environments (3.06).
* **REQ-ENV-04 (Multi-Environment Audio Profiles)**: The audio and buzzer alert subsystems MUST support configurable operational profiles (e.g. silent/classroom, quiet/library, outdoor) with an immediate software/hardware mute switch (3.08).
* **REQ-ENV-05 (Multi-Network Roaming)**: The networking subsystem MUST support profile-based management across home WPA2, enterprise 802.1X, mobile hotspots, and captive portals via a mix of iwd client automation and w3m/curl-based portal handling (3.10).
* **REQ-ENV-06 (Air Travel Pack Compliance)**: The onboard battery pack MUST remain strictly under 100 Wh (3S 18650 pack ~35 Wh) to comply with FAA/ICAO passenger aircraft cabin carry-on regulations (3.09).
* **REQ-ENV-07 (Daily Use Duration)**: The deck MUST support a daily use pattern of 6 hours active usage and 18 hours idle (3.11).

## REQ-INP (Input Subsystem)

* **REQ-INP-01 (CardKB Terminal Control Mapping)**: The input subsystem MUST map terminal control characters (Ctrl, Alt, Esc, Tab, Arrow keys, Function keys) via software modifier layers and sequential sticky chords on the CardKB matrix (4.01).
* **REQ-INP-02 (Key-to-Glyph Latency)**: Keypress-to-terminal display latency MUST remain imperceptible (<50 ms) under normal typing load (4.13).
* **REQ-INP-03 (Modal Rotary Encoder)**: The input subsystem SHALL support a hardware rotary encoder with a push-button modal cycle (volume, brightness, scroll, font size) and visual mode indicator (4.07).
* **REQ-INP-04 (Tactile Haptics & Audible Alerts)**: The system SHALL support a vibration motor and piezo buzzer for critical system state warnings (battery <5%, earlyoom kills, critical system alarms) bounded by active audio profiles (4.09, 4.10, REQ-ENV-04).
* **REQ-INP-05 (Sensory Management Mode)**: The UI and alert system MUST provide a single-action toggle to silence auxiliary alerts and prevent cognitive sensory overload (4.12).
* **REQ-INP-06 (Ambidextrous Layout)**: Physical chassis controls and button positions SHOULD maintain bilateral symmetry for equal left- and right-handed reachability (4.16).
* **REQ-INP-07 (Auxiliary Bluetooth Input)**: The system MAY support pairing external Bluetooth keyboards or input devices via the host Bluetooth controller (4.15).

## REQ-LIC (Licensing)

* **REQ-LIC-01 (Artwork Distribution)**: The `assets/images/cess` directory MAY be distributed publicly inside the open-source repository. The artist explicitly permitted non-commercial redistribution (C-01).

## REQ-PF (Purposes & Features)

* **REQ-PF-01 (Daily Driver)**: The unit MUST serve as a daily driver replacement for a smartphone (2.01).
* **REQ-PF-02 (Core Binaries)**: The base OS MUST successfully execute and prioritize `ssh`, `git`, `nmcli`, `nmap` and `nano` (2.04).
* **REQ-PF-03 (Text Discord Client)**: The deck MAY include or support a custom text-only Discord integration, bounded by API TOS terms (2.06).
* **REQ-PF-04 (Text Web Browser)**: The deck MUST support text-only web browsing with minimal JS execution (2.07).
* **REQ-PF-05 (Markdown Renderer)**: The terminal layer MUST support a custom Markdown viewer parsing basic markers into VT100 bold/color sequences (2.08).
* **REQ-PF-06 (Python & Bash)**: The development environment MUST support Bash and Python, optimized for small scripts due to the restrictive physical keyboard (2.09).
* **REQ-PF-07 (Audio playback)**: The deck MUST support streaming/MP3 audio playback out over the Type-C 3.5mm adapter interface. To preserve CPU and UART bandwidth for TUI rendering, audio MUST operate as a background asynchronous process with minimal UI feedback (2.11).
* **REQ-PF-08 (OTP & Passwords)**: The deck MUST feature offline credential and OTP management (2.14).
* **REQ-PF-09 (Text Gaming)**: The deck MAY include low-bandwidth text-mode games (e.g., Snake, Nethack, Zork), strictly bound by the ~11.5 KB/s text-only serial throughput constraint (2.17).
* **REQ-PF-10 (Hardware Hacking)**: The deck MAY integrate serial consoles, logic analyzer software, or JTAG firmware programmers at a later date (Non-priority, 2.15).
* **REQ-PF-11 (Mathematical Suite)**: The deck SHOULD include a CLI interface for programmable plotting and math processing (2.16).
* **REQ-PF-12 (On-Demand Dashboard)**: The device MUST NOT run an always-on dashboard to save power, but MUST offer a terminal command or key-chord to display battery, network, and git status instantly (2.18).
* **REQ-PF-13 (Mobile Hotspot Integration)**: The deck MUST support connecting to smartphone-hosted Wi-Fi hotspots for external service access (2.01).
* **REQ-PF-14 (Discord Messaging)**: The deck SHALL support text-based communication via official Discord webhook APIs for private messaging (2.06).
