# Domain 09: Power Profiles & Battery Management (REQ-PWR)

**Specification Prefix:** `REQ-PWR`  
**System Layer:** Power Rails, Battery Chemistry, Telemetry & Profile Management  
**Primary Implementations:** `pi/bin/power-profile`, `pi/battery_monitor/`, `firmware/cyd_display_link/`  
**Acceptance Test Plans:** `ATP-09-HW-BATTERY-THERMAL`, `ATP-13-PWR-SENSORY-PROFILES`  
**Target Milestone:** `v0` (Demo Prototype) / `v1` (Field Hardened)  

---

## 1. Scope & Domain Objectives

The Power Profiles & Battery Management domain defines the internal power architecture, battery chemistry and capacity curves, I2C telemetry sampling, low-battery emergency shutdown cutoff, low-power display sleep states, and three-tier operational power profiles. The subsystem guarantees all-day field runtime, protects the lithium pack from over-discharge, and prevents filesystem corruption due to sudden power loss.

---

## 2. Formal Requirements & Normative Specifications

### REQ-PWR-01 [v1]: Three-Tier Power Management Profiles
- **Requirement:** The power management subsystem MUST implement three software profiles:
  1. `ACTIVE`: Full CPU frequency (1.0 GHz), display backlight on, radios active, SSD active (~3.2W typical load).
  2. `IDLE/POWERSAVE`: CPU governor set to `powersave` (600 MHz), display dimmed, SSD spun down via `hdparm -y`, auxiliary polling paused (~1.8W idle).
  3. `AIRPLANE/DEEP-IDLE`: All radios disabled via `rfkill`, display unpowered via opcode `0x06`, CPU 600 MHz (~0.55W sleep).
- **Rationale:** Allows the operator to dynamically stretch battery runtime from 8.6 hours (full active load) to over 50 hours (airplane transit idle).
- **Traceability:** Section 9.08, `F09.08`, `DEC-W21`, `DEC-W39`, `TSK-24`.

### REQ-PWR-02 [v0]: Low-Battery Emergency Cutoff
- **Requirement:** The battery monitoring daemon MUST initiate an orderly emergency shutdown when remaining battery capacity drops to 5%, preventing lithium cell over-discharge and BTRFS metadata corruption.
- **Rationale:** Lithium-ion cells suffer permanent chemical degradation if discharged below 3.0V per cell (~9.0V pack). Orderly shutdown ensures BTRFS syncs all metadata to disk before the BMS cuts power.
- **Traceability:** Section 9.05, 9.06, `DEC-W21`, `pi/battery_monitor/daemon.py`.

### REQ-PWR-03 [v0]: Telemetry Capacity Profiling
- **Requirement:** Pack voltage, current, and capacity MUST be continuously sampled and logged from the Waveshare UPS I2C INA219 sensor (`0x41`) by `battery-monitor.service`, characterizing discharge curves in software without external test bench instruments.
- **Rationale:** Continuous telemetry enables accurate runtime estimation and early warning of failing cells.
- **Traceability:** Section 9.07, `F09.01`, `DEC-W21`.

### REQ-PWR-04 [v0]: Dedicated 3S DC Charging
- **Requirement:** The internal 3S 18650 pack MUST be charged via a dedicated 12.6V DC barrel jack; simultaneous operation while charging (run-while-charging) MUST be supported.
- **Rationale:** Separating charging from USB data ports prevents ground loops and permits high-current 2A fast balance charging.
- **Traceability:** Section 9.02, `DEC-W21`.

### REQ-PWR-05 [v0]: Always-On Mobile Operational Stance
- **Requirement:** The cyberdeck MUST operate as an always-on mobile terminal, entering low-power idle rather than performing cold boot cycles when carried.
- **Rationale:** Cold booting takes ~25 seconds; instant wake from low-power idle maintains readiness for rapid note-taking and emergency operations.
- **Traceability:** Section 9.09, `DEC-W21`.

### REQ-PWR-06 [v0]: Firmware Sleep Opcode `0x06`
- **Requirement:** The wire protocol and ESP32 firmware MUST support opcode `0x06` (`SLEEP`) to place the display controller in low-power sleep (DISPOFF/SLPIN, backlight PWM 0%, CPU 80 MHz, ~75 mW draw) while remaining awake on the serial RX pin to wake instantly on the next frame.
- **Rationale:** Display backlight is a primary power consumer; putting the coprocessor to sleep saves ~0.8W.
- **Traceability:** `WS-3`, `DEC-W29`, `firmware/cyd_display_link/main.cpp`.

### REQ-PWR-07 [v1]: Unswitched Rail Standby Drain Elimination
- **Requirement:** The hardware power architecture MUST eliminate unswitched standby current drain on the CYD 5V rail by incorporating a load switch controlled via GPIO poweroff signals.
- **Rationale:** Eliminates parasitic quiescent drain when the cyberdeck is completely halted.
- **Traceability:** `REQ-PWR-07`.

### REQ-PWR-08 [v2+]: Hardware Battery Fuel Gauge
- **Requirement:** The `v2+` mainboard MUST incorporate an integrated MAX17048 I2C fuel gauge utilizing the ModelGauge algorithm to track state-of-charge, eliminating voltage-sag estimation errors during CPU bursts.
- **Rationale:** Voltage-based capacity estimation can fluctuate during sudden CPU bursts; ModelGauge tracks chemical charge state directly.
- **Traceability:** `REQ-PWR-08`.

---

## 3. Actual Implementation Architecture

### 3.1 The Three-Tier Power Profile Controller (`pi/bin/power-profile`)
Exposes commands: `wf power status`, `wf power set active|powersave|airplane`.

```text
+-------------------+-------------+---------------+-----------------------+
| Subsystem         | ACTIVE      | POWERSAVE     | AIRPLANE              |
+-------------------+-------------+---------------+-----------------------+
| CPU Governor      | ondemand    | powersave     | powersave             |
| CPU Max Frequency | 1.0 GHz     | 600 MHz       | 600 MHz               |
| Wi-Fi / Bluetooth | Unblocked   | Unblocked     | Blocked (rfkill all)  |
| CYD LCD Backlight | 100% (High) | Dimmed (Low)  | 0% (Opcode 0x06 Sleep)|
| Samsung 860 SSD   | Active      | Spun down     | Spun down (hdparm -y) |
| Power Consumption | ~3.2 W      | ~1.8 W        | ~0.55 W               |
| Runtime on 27.7Wh | ~8.6 Hours  | ~15.4 Hours   | ~50.4 Hours           |
+-------------------+-------------+---------------+-----------------------+
```

### 3.2 Battery Monitoring Daemon (`pi/battery_monitor/daemon.py`)
- Reads INA219 sensor over `/dev/i2c-1` at `0x41` every 5.0 seconds.
- Converts 3S pack voltage (9.0V–12.6V) into accurate non-linear percentage.
- Writes kernel-compatible `uevent` and `status.json` to `/run/battery_monitor/`:
  ```json
  {
    "bus_voltage_v": 12.35,
    "current_ma": 245.2,
    "battery_percent": 91.5,
    "power_mw": 3028.2,
    "status": "Discharging",
    "updated_at": "2026-10-16T12:00:00Z",
    "fresh": true
  }
  ```
- **Automatic Cutoff:** If `battery_percent <= 5.0` and `auto_shutdown: true`, daemon executes `logger -p crit "Battery critical (<=5%); initiating emergency shutdown" && systemctl poweroff`.

---

## 4. Verification & Acceptance Criteria

- **`ATP-09-HW-BATTERY-THERMAL`:** Verifies continuous polling of INA219, publishing of `status.json` and `uevent`, voltage-to-percentage accuracy, and emergency shutdown threshold at 5%.
- **`ATP-13-PWR-SENSORY-PROFILES`:** Verifies dynamic switching between `ACTIVE`, `POWERSAVE`, and `AIRPLANE` profiles, confirming governor updates and rfkill state.
