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

## REQ-LIC (Licensing)

* **REQ-LIC-01 (Artwork Distribution)**: The `assets/images/cess` directory MAY be distributed publicly inside the open-source repository. The artist explicitly permitted non-commercial redistribution (C-01).

## REQ-PF (Purposes & Features)

* **REQ-PF-01 (Daily Driver)**: The unit MUST serve as a daily driver replacement for a smartphone (2.01).
* **REQ-PF-02 (Core Binaries)**: The base OS MUST successfully execute and prioritize `ssh`, `git`, `nmcli`, `nmap` and `nano` (2.04).
* **REQ-PF-03 (Text Discord Client)**: The deck MAY include or support a custom text-only Discord integration, bounded by API TOS terms (2.06).
* **REQ-PF-04 (Text Web Browser)**: The deck MUST support text-only web browsing with minimal JS execution (2.07).
* **REQ-PF-05 (Markdown Renderer)**: The terminal layer MUST support a custom Markdown viewer parsing basic markers into VT100 bold/color sequences (2.08).
* **REQ-PF-06 (Python & Bash)**: The development environment MUST support Bash and Python, optimized for small scripts due to the restrictive physical keyboard (2.09).
* **REQ-PF-07 (Audio playback)**: The deck MUST support streaming/MP3 audio playback out over the Type-C 3.5mm adapter interface (2.11).
* **REQ-PF-08 (OTP & Passwords)**: The deck MUST feature offline credential and OTP management (2.14).
* **REQ-PF-09 (Text Gaming)**: The deck MAY include retro emulation or gaming, strictly bound by the ~11.5 KB/s text-only serial throughput constraint (2.17).
* **REQ-PF-10 (Hardware Hacking)**: The deck MAY integrate serial consoles, logic analyzer software, or JTAG firmware programmers at a later date (Non-priority, 2.15).
* **REQ-PF-11 (Mathematical Suite)**: The deck SHOULD include a CLI interface for programmable plotting and math processing (2.16).
* **REQ-PF-12 (On-Demand Dashboard)**: The device MUST NOT run an always-on dashboard to save power, but MUST offer a terminal command or key-chord to display battery, network, and git status instantly (2.18).
