# Domain 06: Hardware Enclosure, Buses & Peripherals (REQ-HW)

**Specification Prefix:** `REQ-HW`  
**System Layer:** Physical Enclosure, Electronic Buses & Peripherals  
**Primary Implementations:** `firmware/cyd_display_link/main.cpp`, `pi/battery_monitor/ina219.py`, hardware wiring  
**Acceptance Test Plans:** `ATP-09-HW-BATTERY-THERMAL`, `ATP-02-INP-CTRL-LATCH`  
**Target Milestone:** `v0` (Demo Prototype) / `v1` (Field Hardened)  

---

## 1. Scope & Domain Objectives

The Hardware Enclosure & Buses domain defines the physical node matrix, interconnect wiring, electrical power rails, real-time clock integration, coprocessor supervision, and external peripheral interfaces of the WhiskerFrame Cyberdeck. It guarantees safe electrical isolation between compute, display, and battery rails while establishing physical robustness against shock, vibration, and thermal accumulation.

---

## 2. Formal Requirements & Normative Specifications

### REQ-HW-01 [v1]: Hardware Real-Time Clock
- **Requirement:** The system MUST incorporate an I2C DS3231 Real-Time Clock module (I2C-1 @ `0x68`) with backup battery to ensure monotonic timekeeping across cold boots without network access, eliminating TLS validation failures and git timestamp drift.
- **Rationale:** Offline operations cause system clock regression to the 1970 UNIX epoch without an RTC, breaking TLS certificates, log ordering, and git commits.
- **Traceability:** `A.09`, `F-A.02`, `DEC-W15`, `DEC-W26`.

### REQ-HW-02 [v1]: Weatherproof Sealed Enclosure
- **Requirement:** Casework MUST provide a sealed, gasketed barrier protecting internal electronics from high ambient humidity and direct rain exposure typical of tropical Philippine transit.
- **Rationale:** High ambient humidity and sudden monsoon downpours quickly corrode exposed contacts and short high-voltage rails.
- **Traceability:** `1.10`, `3.05`, `DEC-W17`.

### REQ-HW-03 [v0]: Modular External USB Peripherals
- **Requirement:** To maintain the <=70 mm chassis thickness ceiling and prevent thermal concentration inside the sealed enclosure, high-power USB peripherals (ZTE MF833V LTE modem, RTL-SDR dongle) MUST connect externally via exposed USB hub ports rather than being sealed internally.
- **Rationale:** Internalizing LTE modems and SDRs concentrates heat and increases chassis bulk beyond the A5/70mm physical envelope.
- **Traceability:** `C-03`, `DEC-W17`.

### REQ-HW-04 [v0]: 3S 18650 UPS Power Supply
- **Requirement:** The internal battery subsystem MUST utilize a 3S 18650 UPS module (11.1V nominal, ~27.75 Wh energy) with an integrated I2C INA219 sensor (`0x41`) and dedicated 12.6V DC barrel charging.
- **Rationale:** A 3S battery topology minimizes I2R current losses across internal power wiring while keeping total energy well within aviation regulations.
- **Traceability:** `DEC-W17`, `DEC-W21`.

### REQ-HW-05 [v1]: Physical Power Button via RUN Pads
- **Requirement:** The chassis MUST incorporate a momentary push button wired directly to the Raspberry Pi Zero 2W `RUN` pads, enabling clean hardware power-on from halt state and emergency hard reset when held.
- **Rationale:** When the Pi halts (`poweroff`), power is still present on the rail; pulling RUN to ground resets the SoC and initiates boot without power cycling.
- **Traceability:** `REQ-HW-05`.

### REQ-HW-06 [v0]: Stock CardKB v1.1 Integration
- **Requirement:** Hardware input for `v0` MUST standardize on the stock M5Stack CardKB v1.1 unit, deferring custom keyboard PCB fabrication to `v2+`.
- **Rationale:** Minimizes lead time, cost, and custom PCB fabrication risks for the v0 prototype.
- **Traceability:** Section 4.01, `F-04.02`.

### REQ-HW-07 [v1]: Host-Lost Hardware Supervisory Watchdog
- **Requirement:** The ESP32 coprocessor MUST supervise host heartbeats over the UART link; if the host freezes for >60s without servicing the link, the coprocessor MUST display a crash recovery warning without false-triggering during normal boot.
- **Rationale:** Provides unambiguous visual indication when the Linux kernel crashes or hangs in headless field deployments.
- **Traceability:** Section 6.10, `DEC-W18`, `firmware/cyd_display_link/main.cpp`.

### REQ-HW-08 [v1]: GPIO-Poweroff Rail Load Switch
- **Requirement:** The system MUST incorporate a P-channel MOSFET load switch on the CYD 5V power rail driven by the Pi `gpio-poweroff` device-tree overlay, disconnecting display and backlight power when the Pi halts to eliminate standby battery drain.
- **Rationale:** Eliminates parasitic quiescent drain of the ESP32 and display backlight when the Pi has safely halted.
- **Traceability:** `REQ-HW-08`.

### REQ-HW-09 [v2+]: Custom WhiskerFrame Integrated Mainboard PCB
- **Requirement:** The `v2+` commercial revision MUST integrate the Raspberry Pi compute module (CM4 or Zero 2W), ESP32-S3 coprocessor, battery charger, and power management IC (PMIC) onto a single custom PCB, eliminating internal jumper wiring.
- **Rationale:** Commercial volume manufacturing requires elimination of discrete modules and point-to-point wiring.
- **Traceability:** Section 11.03, `F11.02`.

---

## 3. Actual Implementation Architecture

### 3.1 Hardware Node Matrix

```text
+-----------------------+-------------+---------------+-----------------------+
| Subsystem Node        | Bus / Port  | I2C / Device  | Operational Details   |
+-----------------------+-------------+---------------+-----------------------+
| CYD Coprocessor       | USB-Serial  | /dev/ttyUSB0  | ESP32-2432S028R       |
|                       | (CH340)     | (115200 baud) | 320x240 ILI9341 LCD   |
| CardKB Matrix         | I2C-0       | 0x5F (Pins 27,| ATmega328P coproc,    |
|                       |             | 28, GPIO 0/1) | 30ms debounce window  |
| Waveshare 3S UPS      | I2C-1       | 0x41 (Pins 3, | INA219 sensor,        |
|                       |             | 5, GPIO 2/3)  | 11.1V nominal pack    |
| DS3231 RTC            | I2C-1       | 0x68 (Pins 3, | Monotonic time,       |
|                       |             | 5, GPIO 2/3)  | CR1220 battery backup |
| STEMMA QT Expansion   | I2C-1       | 3.3V, GND,    | JST-SH 1.0mm 4-pin,   |
|                       |             | SDA, SCL      | 100 mA PTC protected  |
+-----------------------+-------------+---------------+-----------------------+
```

### 3.2 Coprocessor Watchdog Implementation (`firmware/cyd_display_link/main.cpp`)
```cpp
static const unsigned long kHostWatchdogTimeoutMs = 60000;
static unsigned long last_packet_time = 0;
static bool host_ever_seen = false;
static bool watchdog_warning_active = false;

void loop() {
  // Read and dispatch incoming serial frames...
  if (host_ever_seen && (millis() - last_packet_time > kHostWatchdogTimeoutMs)) {
    if (!watchdog_warning_active) {
      watchdog_warning_active = true;
      tft.fillRect(0, 0, 320, 24, TFT_RED);
      tft.setTextColor(TFT_WHITE, TFT_RED);
      tft.drawString("HOST LINK LOST >60s (CHECK PI)", 8, 4, 2);
    }
  }
}
```

---

## 4. Verification & Acceptance Criteria

- **`ATP-09-HW-BATTERY-THERMAL`:** Verifies I2C communication with INA219 at `0x41`, continuous status publishing, and thermal reading from `/sys/class/thermal/thermal_zone0/temp`.
- **Coprocessor Watchdog:** Verified via dry-run simulation and unit test harness; confirms warning banner renders after 60s of serial silence.
