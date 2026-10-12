# Spec Interview Observations & Background Notes

### Section 3 (Contexts & Environment)
- **3.01 / 3.02 (Posture & Locations):** Primary posture is two-thumb typing across diverse mobile environments (outdoors, 2-hour commute, lab, desk, bed). Establishes structural rigidity and center-of-gravity balance requirements for handheld two-thumb operation.
- **3.04 (Aesthetics):** Explicitly designed to look like visible cyberpunk / maker tech rather than stealth/innocuous disguise.
- **3.07 (Durability):** Daily transit transport establishes vibration, drop-resistance, and secure internal component mounting requirements.
- **3.09 (Air Travel Compliance):** 3x 18650 Li-ion cells in series (nominal 11.1V, ~2.5–3.5Ah per cell) provide ~28–39 Wh total energy. This is well below the FAA/TSA/CAAP 100 Wh airline carry-on limit for lithium-ion battery packs. Transport is compliant in cabin baggage (checked baggage forbidden).
- **3.12 (Power Sources):** Dual-source operation verified: internal 3S 18650 UPS module for battery run-time, wall charging for mains supply.

### Section 4 (Input)
- **4.01 (Form Factor):** CardKB selected as the minimum viable physical keyboard footprint for handheld two-thumb typing.
- **4.12 (Cognitive / Sensory Ergonomics):** Device must support a low-stimulation / anti-overwhelm mode (ability to silence secondary displays, notification buzzers, and tickers to focus strictly on the terminal prompt).
- **4.13 (Key Latency):** "Instant feel" (<30–50 ms key-to-glyph) target matches the current CardKB driver design (30 ms debounce window in `pi/cardkb/reader.py`).
- **4.14 (Shortcuts):** Sane, lightweight keychording philosophy affirmed (e.g. `Fn+Del` for font resize).
- **4.15 (Bluetooth):** Bluetooth HID peripheral pairing (keyboard/mouse) recognized as optional secondary capability supported by Pi Zero 2W's onboard BT 4.2.
- **4.16 (Symmetry):** Symmetrical chassis layout confirmed for ambidextrous two-thumb balance.
