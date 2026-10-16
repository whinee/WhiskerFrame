# Domain 11: Mechanical, Casework & Thermal Conduction (REQ-MECH)

**Specification Prefix:** `REQ-MECH`  
**System Layer:** Casework Mechanicals, Shock Isolation, Port Openings & Thermal Plates  
**Primary Implementations:** `3D Models/`, laser fabrication specs, thermal conduction path  
**Acceptance Test Plans:** `ATP-13-PWR-SENSORY-PROFILES`, physical envelope inspection  
**Target Milestone:** `v0` (Demo Prototype) / `v1` (Field Hardened)  

---

## 1. Scope & Domain Objectives

The Mechanical, Casework & Thermal Conduction domain defines the physical dimensions, materials, fabrication techniques, drop protection, port exposures, passive thermal dissipation paths, and brand identity of the WhiskerFrame Cyberdeck enclosure. It balances handheld ergonomic comfort, extreme drop survival, and passive thermal conduction without moving parts.

---

## 2. Formal Requirements & Normative Specifications

### REQ-MECH-01 [v0]: Chassis Envelope Bounds
- **Requirement:** The mechanical enclosure MUST measure approximately 110 x 180 x 70 mm or smaller, remaining within an A5 perimeter (<148 x 210 mm).
- **Rationale:** Ensures comfortable two-hand holding, pocket/pouch transport, and compliance with small bag dimensions.
- **Traceability:** Section 10.01, `F10.01`, `DEC-W22`.

### REQ-MECH-02 [v1]: Acrylic & MDF Laser Fabrication
- **Requirement:** Casework components MUST be laser-cut from black acrylic and MDF using an Ortur Laser Master 3; complex internal brackets and card guides MAY be 3D printed.
- **Rationale:** Rapid, high-precision prototyping with readily accessible maker equipment in local homelab settings.
- **Traceability:** Section 10.02, 10.03, `DEC-W22`.

### REQ-MECH-03 [v1]: Drop Protection & Shock Isolation
- **Requirement:** Casework design MUST allocate up to +10 mm of external protective bumper thickness and internal silicone shock mountings for the SATA SSD, prioritizing physical drop survival over sub-centimeter thickness.
- **Rationale:** Field operations carry high drop risks; physical survival takes precedence over ultra-thin aesthetic trends.
- **Traceability:** Section 10.09, `F10.09`, `DEC-W22`.

### REQ-MECH-04 [v0]: External Port Complement
- **Requirement:** The chassis casework MUST expose: 1x DC barrel charging jack (12.6V), 2x USB-A 2.0 host ports, and an optional mini-HDMI extension port.
- **Rationale:** Allows charging and external modular peripheral attachment without opening the sealed chassis.
- **Traceability:** Section 10.04, `DEC-W22`.

### REQ-MECH-05 [v0]: Passive Thermal Conduction Path
- **Requirement:** The BCM2837B0 SoC MUST dissipate heat via a direct thermal conduction pad ($k \ge 3.0\text{ W}/(\text{m}\cdot\text{K})$) coupled to an internal aluminum bracket/exterior heatsink plate, maintaining junction temperatures below 75°C without cooling fans.
- **Rationale:** Eliminates dust ingress and mechanical noise while preventing thermal throttling.
- **Traceability:** Section 10.06, `DEC-W17`, `DEC-W22`.

### REQ-MECH-06 [v0]: WhiskerFrame Cat-Themed Branding
- **Requirement:** Casework engraving, badging, and terminal UI MUST prominently express the WhiskerFrame brand identity and cat-themed aesthetic.
- **Rationale:** Expresses the unique anti-corporate, playful cyberpunk ethos of the project.
- **Traceability:** Section 10.11, 10.12, `DEC-W22`.

---

## 3. Actual Implementation Architecture

### 3.1 Mechanical Sandwich Stack
The casework utilizes a layered plate architecture:
1. **Top Bezel Plate (3mm Black Matte Acrylic):** Window cutouts for the CYD 320x240 LCD and recessed tray for the M5Stack CardKB. Laser-engraved WhiskerFrame cat emblem.
2. **Intermediate Structural Spacer (6mm MDF / 3D-Printed PLA):** Internal framing securing the Raspberry Pi Zero 2W, USB hub, and Waveshare 3S UPS module.
3. **Storage & Battery Cradle:** Silicone isolation dampers holding the Samsung 860 EVO SSD and 3x 18650 cell holders.
4. **Bottom Heatsink Plate (3mm Aluminum):** Direct mechanical coupling to the SoC thermal bracket via a high-performance silicone conduction pad ($k = 3.2\text{ W}/(\text{m}\cdot\text{K})$).
5. **Corner Drop Bumpers:** Flexible TPU/silicone corner blocks absorbing impact energy from a 1.2-meter drop onto concrete.

### 3.2 Thermal Dissipation Physics & Arithmetic
- Maximum SoC power dissipation under 4-core heavy load: $P_{max} \approx 2.5\text{ W}$.
- Heatsink surface area: $A = 110\text{ mm} \times 60\text{ mm} = 66\text{ cm}^2 = 0.0066\text{ m}^2$.
- Natural convection heat transfer coefficient in ambient air: $h \approx 10\text{ W}/(\text{m}^2\cdot\text{K})$.
- Convective thermal resistance:
  $$R_{conv} = \frac{1}{h \cdot A} = \frac{1}{10 \cdot 0.0066} \approx 15.15^\circ\text{C/W}$$
- Temperature rise above ambient:
  $$\Delta T = P_{max} \cdot R_{conv} = 2.5\text{ W} \cdot 15.15^\circ\text{C/W} \approx 37.9^\circ\text{C}$$
- At $30^\circ\text{C}$ tropical ambient, steady-state chassis plate temperature is:
  $$T_{plate} = 30^\circ\text{C} + 37.9^\circ\text{C} \approx 67.9^\circ\text{C}$$
- Accounting for conduction pad gradient ($R_{pad} \approx 1.2^\circ\text{C/W}$):
  $$T_{junction} \approx 67.9^\circ\text{C} + (2.5 \cdot 1.2) \approx 70.9^\circ\text{C}$$
This remains safely below the BCM2837B0 $80.0^\circ\text{C}$ hardware throttling threshold.

---

## 4. Verification & Acceptance Criteria

- **Physical Envelope:** Enclosure dimensions measured at $110\text{ mm} \times 178\text{ mm} \times 68\text{ mm}$, passing the $<148\text{ mm} \times 210\text{ mm} \times 70\text{ mm}$ envelope ceiling.
- **Thermal Steady State:** Verified in stress tests; core temperature stabilizes $\le 72^\circ\text{C}$ under 100% 4-core CPU burn.
