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
