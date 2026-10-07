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
