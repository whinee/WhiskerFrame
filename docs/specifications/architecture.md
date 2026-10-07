## 1. System Architecture & Hardware Topology

The cyberdeck functions as an asymmetric dual-core system: a Linux host (Pi Zero 2W) handling storage, networking, PAM, and high-level agent logic, while an ESP32 coprocessor acts as a dedicated graphic/terminal rendering unit over serial.

```
                    +-------------------------------------------------+
                    |              Raspberry Pi Zero 2W               |
                    |               (Raspberry Pi OS)                 |
                    +---+--------------+--------------+---------------+
                        |              |              |               |
           USB-Serial   |        I2C-0 |        I2C-1 |       USB OTG |
           (CH340)      |        (Pin 27/28)    (Pin 3/5)             |
                        |              |              |       Unpowered Hub
                        v              v              v               v
               +----------------+ +----------+ +---------------+ +-----------+
               | ESP32-2432S028 | | M5Stack  | | UPS Module 3S | | ZTE LTE   |
               | (CYD Coproc)   | |  CardKB  | | (INA219 Sens) | | Modem &   |
               | ILI9341 Display| | Addr 0x5F| | Addr 0x41    | | RTL-SDR   |
               +----------------+ +----------+ +---------------+ +-----------+

```

### 1.1 Hardware Node Matrix

| Component | Interface / Port | Address / Node | Operational Parameters | Critical Constraints |
| --- | --- | --- | --- | --- |
| **CYD (ESP32)** | USB-Serial (CH340) | `/dev/ttyUSB0` (`usb-1a86_USB_Serial...`) | 115200 baud (runtime), 460800 baud (flash) | Hardware is sealed inside deck. Panel requires `tft.invertDisplay(true)`. Exclusive lock by `terminal.service`. |
| **M5Stack CardKB** | I2C-0 (Pins 27/28) | `/dev/i2c-0` @ `0x5F` | Polled ASCII byte stream (`0x00` = idle) | Requires `dtparam=i2c_vc=on` & `dtoverlay=i2c0,pins_0_1`. Self-healing via `robust_keys()`. |
| **UPS Module 3S** | I2C-1 (Pins 3/5) | `/dev/i2c-1` @ `0x41` | 3S Li-ion pack (9.0V–12.6V) | Managed by `battery-monitor.service`. Calibrates per poll; auto-shutdown trigger at 5%. |
| **Networking** | USB OTG Hub | `usb0` (Modem) / `/dev/swradio0` (SDR) | ZTE MF833V (LTE) + Generic SDR | Connected via unpowered hub. Max total draw 1.5A from Pi to prevent volt drop. |
| **Storage (SSD)** | USB 2.0 (SATA-to-USB) | `/dev/disk/by-uuid/98bb87d2-7128-470e-91d5-9e117df2ab1a` | **btrfs** (whole-disk, label `cyberdeck-ssd`); `@data` subvol → `/mnt/250GB-SSD` (`noatime,compress=zstd`); `@swap` subvol holds the swapfile (`nodatacow`) | Must use `nofail` + device timeout to prevent boot hangs. Reconciled ext4→btrfs 2026-10-07 (DEC-W12); old ext4 UUID `a6ca355e-…` is dead. Swap is `nodatacow`/uncompressed (CoW incompatible with swap). |

---

