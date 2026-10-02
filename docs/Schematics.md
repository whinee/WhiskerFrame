# Schematics

## UPS Module 3S <-> Raspberry Pi (I2C-1)

The UPS Module 3S exposes a Texas Instruments **INA219** monitor on I2C. Wire it to
the Pi's **hardware I2C-1** bus (GPIO 2/3). Do not use GPIO 27/22 — those have no
hardware I2C peripheral.

| Pin | Raspberry Pi      | Connection | UPS Module | Pin |
| :-: | :---------------- | :--------: | :--------: | :-: |
|  3  | GPIO 2 (I2C1 SDA) |   Orange   |    SDA     |  7  |
|  5  | GPIO 3 (I2C1 SCL) |   Purple   |    SCL     |  8  |
|  6  | GND               |   Green    |    GND     |  3  |
|  9  | GND               |    Blue    |    GND     |  4  |

INA219 I2C address: `0x41` on `/dev/i2c-1`. Enable the bus with
`dtparam=i2c_arm=on` (see `docs/dev/manual-hardware-steps.md`, Section D).

## CardKB <-> Raspberry Pi (I2C-0)

The M5Stack CardKB is an I2C keypad on the Pi's **I2C-0** bus (GPIO 0/1). This is
a separate bus from the UPS (I2C-1), so the two coexist. Enable I2C-0 with
`dtparam=i2c_vc=on` + `dtoverlay=i2c0,pins_0_1` (see
`docs/dev/manual-hardware-steps.md`).

| Pin | Raspberry Pi      | Connection | CardKB | Pin |
| :-: | :---------------- | :--------: | :----: | :-: |
|  4  | 5V                |    Red     |   5V   |  2  |
| 25  | GND               |   Black    |  GND   |  1  |
| 27  | GPIO 0 (I2C0 SDA) |   Yellow   |  SDA   |  3  |
| 28  | GPIO 1 (I2C0 SCL) |   Green    |  SCL   |  4  |

CardKB I2C address: `0x5F` on `/dev/i2c-0`. It returns the ASCII byte of the
pressed key (`0x00` when idle).
