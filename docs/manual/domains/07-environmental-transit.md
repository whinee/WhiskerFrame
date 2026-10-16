# Domain 07: Environmental, Posture & Transit Boundaries (REQ-ENV)

**Specification Prefix:** `REQ-ENV`  
**System Layer:** Physical Boundaries, Environmental Adaptation & Transit Profile  
**Primary Implementations:** `pi/bin/profile`, `assets/themes/mono-high-contrast.json`, thermal dissipation design  
**Acceptance Test Plans:** `ATP-13-PWR-SENSORY-PROFILES`, `ATP-09-HW-BATTERY-THERMAL`  
**Target Milestone:** `v0` (Demo Prototype) / `v1` (Field Hardened)  

---

## 1. Scope & Domain Objectives

The Environmental, Posture & Transit domain defines the physical ergonomics, operating postures, ambient light adaptations, thermal dissipation limits, and aviation transit boundaries of the WhiskerFrame Cyberdeck. The deck is explicitly tailored for mobile transit in tropical Philippine conditions (high heat, high humidity) while maintaining compliance with international aviation carry-on regulations.

---

## 2. Formal Requirements & Normative Specifications

### REQ-ENV-01 [v1]: Fanless Conduction Cooling
- **Requirement:** The cyberdeck MUST operate with 100% passive fanless cooling to preserve acoustic silence and prevent dust/water ingress, conducting heat from the SoC directly to an external aluminum plate.
- **Rationale:** Fans consume power, generate acoustic noise, draw in tropical moisture/dust, and introduce mechanical failure points.
- **Traceability:** Section 3.05, `DEC-W17`, `DEC-W22`.

### REQ-ENV-02 [v0]: Two-Thumb Handheld Posture
- **Requirement:** The physical balance and center-of-gravity of the chassis MUST support two-thumb typing while standing or commuting without requiring a table rest.
- **Rationale:** Public transit (jeepneys, buses, trains) offers no flat desk surfaces; the operator must be able to securely hold and operate the deck while standing.
- **Traceability:** Section 3.02, `DEC-W17`.

### REQ-ENV-03 [v1]: Ambient Light Contrast Compensation
- **Requirement:** The display subsystem SHOULD sample the CYD on-board light-dependent resistor (LDR) to dynamically scale backlight PWM and automatically invert palettes to a high-contrast mono theme in direct sunlight.
- **Rationale:** Direct equatorial sunlight washes out pastel colors; high-contrast monochrome inversion maintains readability.
- **Traceability:** Section 3.06, Section 5.08, `DEC-W19`.

### REQ-ENV-04 [v1]: Configurable Environmental Audio Profiles
- **Requirement:** The audio subsystem MUST provide three profile presets (`classroom/silent`, `office/quiet`, `commute/loud`) toggling haptics and buzzer volumes via hotkey or CLI.
- **Rationale:** Audible alerts must adapt to context: absolute silence in classrooms and libraries, loud alerts in noisy public transit.
- **Traceability:** Section 3.08, `DEC-W17`, `pi/bin/profile`.

### REQ-ENV-05 [v1]: Multi-Network Profile Roaming
- **Requirement:** The network stack MUST support seamless roaming across home WPA2, campus 802.1X, mobile hotspots, and captive portals using `iwd`/NetworkManager profile automation and `w3m` portal landing.
- **Rationale:** Handheld operation spans diverse networks throughout a typical daily commute.
- **Traceability:** Section 3.10, `DEC-W29`.

### REQ-ENV-06 [v0]: Passenger Aircraft Cabin Compliance
- **Requirement:** The internal 3S lithium-ion battery pack MUST NOT exceed 100 Wh (actual pack: 27.75 Wh nominal), complying strictly with FAA, ICAO, and CAAP regulations for passenger cabin carry-on baggage.
- **Rationale:** International and domestic aviation regulations strictly ban uncertified lithium batteries $>100\text{ Wh}$ in passenger cabins.
- **Traceability:** Section 3.09, `DEC-W17`.

### REQ-ENV-07 [v0]: Operational Duty Cycle
- **Requirement:** The deck MUST support an operational daily profile of at least 6.0 hours of active terminal usage and 18.0 hours of low-power idle.
- **Rationale:** Guarantees all-day autonomy across full work and commute cycles on a single charge.
- **Traceability:** Section 3.11, `DEC-W21`.

---

## 3. Actual Implementation Architecture

### 3.1 Passive Thermal Conduction Engine
The BCM2837B0 SoC generates up to 2.5W under sustained compilation load:
- **Thermal Resistance Model:** $\theta_{junction-case} \approx 4.0^\circ\text{C/W}$.
- **Conduction Interface:** Direct thermal silicone pad with thermal conductivity $k \ge 3.0\text{ W}/(\text{m}\cdot\text{K})$ coupled to an internal aluminum bracket and exterior 3mm aluminum heatsink plate ($A \approx 60\text{ cm}^2$).
- **Thermal Steady State:** Under $30^\circ\text{C}$ ambient conditions with continuous full load, SoC junction temperature stabilizes at $\sim 62^\circ\text{C}$, well below the $80^\circ\text{C}$ thermal throttling threshold.

### 3.2 Sunlight-Readable Monochrome Theme
Stored at `assets/themes/mono-high-contrast.json`:
- **Background:** Pure White `#FFFFFF` (RGB565: `0xFFFF`).
- **Foreground:** Pure Black `#000000` (RGB565: `0x0000`).
- **Contrast Ratio:** 21.0:1 (maximum achievable contrast).
- **Activation:** Can be applied via `.whiskerframe.yaml` or dynamically invoked during high ambient lux conditions.

### 3.3 Environmental Audio Profiles (`pi/bin/profile`)
Managed via `pi/bin/profile` and `wf profile`:
- **`CLASSROOM`:** Buzzer volume 0%, vibration disabled. Silent operation.
- **`OFFICE`:** Buzzer volume 25% (gentle low-duty cycle chirp), vibration enabled for critical alerts.
- **`COMMUTE`:** Buzzer volume 100% (high-frequency resonant pulse), vibration enabled for all notifications.
- **`OVERLOAD`:** Instant cognitive sensory clamp suppressing all sound and haptics to zero.

---

## 4. Verification & Acceptance Criteria

- **`ATP-13-PWR-SENSORY-PROFILES`:** Verifies sensory profile switching between `CLASSROOM`, `OFFICE`, and `COMMUTE`, confirming audio volume clamping and overload suppression.
- **Aviation Battery Safety:** Pack capacity confirmed at 27.75 Wh nominal (3x 18650 cells @ 2500 mAh, 11.1V), representing only 27.75% of the 100 Wh regulatory limit.
