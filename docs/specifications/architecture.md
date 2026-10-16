## §1. System Architecture & Hardware Topology

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

### 1.2 Communication Protocols & Bus Hierarchy

| Bus Tier | Interface / Port | Attached Devices | Link Parameters | Protocol Specification |
| --- | --- | --- | --- | --- |
| **Small Bus** | UART (CH340) | Host Pi Zero 2W -> ESP32-2432S028 CYD Coprocessor | 115200 baud (runtime), 460800 baud (flash) | Binary framing (`SOF 0xA5`, `LEN`, `OPCODE`, `CRC8`), opcodes `0x01`–`0x06`. See [contracts/wire-protocol.md](contracts/wire-protocol.md). |
| **Small Bus** | I2C-0 (`/dev/i2c-0`) | Host Pi (GPIO 0/1, Pins 27/28) -> M5Stack CardKB (`0x5F`) | 100 kHz standard mode | Polled ASCII byte stream, sequential sticky Ctrl latch (`0x8C`), SK6812 NeoPixel control (`0x13`/`0x11`). See [terminal.md](terminal.md). |
| **Small Bus** | I2C-1 (`/dev/i2c-1`) | Host Pi (GPIO 2/3, Pins 3/5) -> Waveshare UPS 3S (`0x41`), DS3231 RTC (`0x68` [v1]) | 100 kHz standard mode | INA219 voltage/current telemetry; DS3231 monotonic timekeeping. |
| **Medium Bus** | USB 2.0 Host | Pi Micro-USB OTG -> Unpowered 4-Port Hub | 480 Mbps high-speed shared | Host connections: Samsung 860 EVO SSD, ZTE MF833V LTE modem, RTL-SDR. |
| **Big Bus** | PCIe / NVMe | Deferred to v2+ (e.g. Pi CM4 / Pi 5 baseboard) | Gen 2/3 x1 | High-speed storage expansion (deferred). |

### 1.3 Memory & Resource Budgets

| Resource / Subsystem | Physical Ceiling | Allocated Budget | Safety Floor / Threshold | Management Mechanism |
| --- | --- | --- | --- | --- |
| **Pi Zero 2W System RAM** | 512 MB (LPDDR2) | ~416 MB (usable after `gpu_mem=16`) | Broken below 50 MB free (`REQ-OPS-02`) | No Docker/heavy DBs (`REQ-OPS-01`), `earlyoom` daemon, per-service `MemoryMax=` |
| **Swap Space (SSD)** | 250 GB SSD | 1024 MB swapfile on `@swap` (`nodatacow`) | Priority -2 (fallback only) | `swappiness=10`, memory-safety role |
| **Compressed RAM (zram)** | 416 MB RAM | 208 MB zram0 (`zstd`/`lzo-rle`) | Priority 100 (fast burst swap) | `zram-tools` / kernel zram |
| **Ephemeral Guest RAM** | 416 MB RAM | 8 MB tmpfs at `/home/guest` | Max 64 MB cgroup slice | `systemd user-.slice`, `MemoryMax=64M`, auto-cleaned on logout |
| **Log & Buffer Wear** | 416 MB RAM | 32 MB log2ram tmpfs buffer | Max 200 MB on persistent SSD | `log2ram` hourly commit + SSD journald diversion |
| **CYD ESP32 SRAM** | 520 KB SRAM | ~328 KB internal SRAM | Free heap > 80 KB | Font glyph subset caching (ASCII only), no Unicode bloat |

---

