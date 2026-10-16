# Domain 12: Modularity, Expansion Interfaces & Licensing (REQ-MOD & REQ-LIC)

**Specification Prefix:** `REQ-MOD`, `REQ-LIC`  
**System Layer:** Expansion Busses, Modular Sensors & Intellectual Property Governance  
**Primary Implementations:** `docs/Pinouts.md`, `docs/Schematics.md`, STEMMA QT / Qwiic header, `assets/images/cess/`  
**Acceptance Test Plans:** `ATP-09-HW-BATTERY-THERMAL`, `ATP-10-DISP-DRAW-IMAGE`  
**Target Milestone:** `v0` (Demo Prototype) / `v1` (Field Hardened) / `v2+` (Commercial Kit)  

---

## 1. Scope & Domain Objectives

The Modularity, Expansion & Licensing domain defines the electrical expansion buses, transient suppression protections, modular sensor interfaces, and intellectual property/licensing terms governing the WhiskerFrame Cyberdeck. It provides clean, standardized expansion paths for environmental sensors without risking mainboard damage while maintaining strict compliance with third-party artwork permissions.

---

## 2. Formal Requirements & Normative Specifications

### REQ-MOD-01 [v0]: Three-Tier Bus Hierarchy
- **Requirement:** System interconnects MUST follow a 3-tier hierarchy: Small Bus (UART to CYD, I2C-0 to CardKB, I2C-1 to UPS/RTC), Medium Bus (USB 2.0 via hub), and Big Bus (PCIe/NVMe deferred to future compute upgrades).
- **Rationale:** Strict electrical hierarchy prevents high-power or noisy peripherals from destabilizing sensitive telemetry and keyboard buses.
- **Traceability:** Section 11.01, 11.02, `DEC-W23`.

### REQ-MOD-02 [v1]: Small-Bus Electrical Protection
- **Requirement:** Small-bus auxiliary power rails (3.3V/5V) MUST incorporate TVS transient voltage suppression and a 100 mA PTC resettable fuse. High-power peripherals (LTE, SDR) are strictly prohibited from small-bus rails and MUST connect via USB 2.0.
- **Rationale:** Prevents accidental short-circuits or electrostatic discharge (ESD) on exposed sensor headers from resetting the Pi Zero 2W.
- **Traceability:** Section 11.04, `DEC-W23`.

### REQ-MOD-03 [v1]: Open Modular Interface Standardization
- **Requirement:** Custom edge-card modular backplanes, EEPROM auto-detection (`VID:PID`), and dynamic pin negotiation are deferred to `v2+`. Modular sensor expansion in `v1` MUST adopt standard SparkFun Qwiic / Adafruit STEMMA QT (4-pin JST-SH 1.0mm) I2C connectors.
- **Rationale:** Adopting established industry connectors enables plug-and-play compatibility with hundreds of existing sensor breakouts without custom backplane engineering.
- **Traceability:** Section 10.08, Section 11.03, Section 11.10, `DEC-W23`.

### REQ-LIC-01 [v0]: Non-Commercial Community Artwork
- **Requirement:** Third-party artistic assets in `assets/images/cess/` MAY be distributed in the public git repository under the artist's explicit personal, non-commercial permission grant (dated 2026-10-15). Commercial redistribution and unauthorized derivative modifications remain strictly prohibited.
- **Rationale:** Respects artist copyright while enabling rich visual personality in open-source builds.
- **Traceability:** Section A.12, Section C-01, `DEC-W28`.

### REQ-LIC-02 [v2+]: Commercial Artwork Licensing Transition
- **Requirement:** Artwork under `assets/images/cess/` MUST NOT ship in commercial hardware kits or commercial sales. For any `v2+` commercial kit release, replacement bespoke artwork MUST be procured or formal commercial licensing terms executed with the artist prior to sale.
- **Rationale:** Prevents legal liability and copyright infringement in commercial production.
- **Traceability:** Section C-01, `DEC-W28`.

---

## 3. Actual Implementation Architecture

### 3.1 STEMMA QT / Qwiic Interface Pinout
Exposed on the chassis side panel via a standard 4-pin JST-SH 1.0mm keyed connector wired to the Raspberry Pi Zero 2W **I2C-1** bus:
- **Pin 1 (GND):** System Ground.
- **Pin 2 (3.3V VCC):** 3.3V Power Rail protected by a 100 mA Bourns PTC resettable fuse and TVS clamping diode.
- **Pin 3 (SDA):** I2C Data line (BCM GPIO 2 / Pin 3).
- **Pin 4 (SCL):** I2C Clock line (BCM GPIO 3 / Pin 5).

#### Supported Modular Peripherals:
- Environmental sensors: BME280 / SHT31 (Temperature, Humidity, Pressure).
- Navigation: I2C GPS modules (u-blox SAM-M8Q).
- Magnetometers / IMUs: BNO055 / LSM6DSOX (Heading, Orientation).
- Radiation detectors: PocketGeiger Type 5 I2C pulse counter.

All devices appear instantly on `/dev/i2c-1` and are discoverable via `i2cdetect -y 1`.

### 3.2 Medium Bus (USB 2.0 Hub) Architecture
The internal Terminus FE1.1s USB 2.0 hub isolates high-draw external peripherals:
- High current transients from the ZTE MF833V LTE cellular modem are buffered by a 470 $\mu\text{F}$ solid tantalum decoupling capacitor on the 5V USB rail, preventing brownouts of the Pi Zero 2W core.

### 3.3 Artwork Distribution & Licensing Registry
- Location: `assets/images/cess/`
- Contents:
  - `Lyra and Dreanne Christmas Night Market.png` (Source master, 11 MB)
  - `Lyra and Dreanne Christmas Night Market.rgb565` (Pre-converted 320x240 binary, 153,600 bytes)
  - `doodle.rgb565` (128x128 cat doodle, 32,768 bytes)
- Terms: Personal, non-commercial permission grant by artist Cess. Explicitly tagged under `REQ-LIC-01`.

---

## 4. Verification & Acceptance Criteria

- **I2C Bus Safety:** Verified that external I2C-1 sensor additions do not interfere with I2C-0 CardKB operations at address `0x5F`.
- **Licensing Audit:** Zero unapproved commercial assets detected; non-commercial grant documented in `docs/LICENSE.md` and `docs/dev/ai-decisions.md` (`DEC-W28`).
