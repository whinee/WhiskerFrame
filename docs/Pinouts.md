# Pinouts

## Raspberry Pi Zero 2WHC

![[Pasted image 20260930113734.png]]

## UPS module

| Function |  A  |  B  |  C  |  D  |
| :------: | :-: | :-: | :-: | :-: |
|   Pin    |  1  |  3  |  5  |  7  |
|  Label   | 5V  | GND | 3V3 | SDA |
|  Label   | 5V  | GND | 3V3 | SCL |
|   Pin    |  2  |  4  |  6  |  8  |

## UPS module — I2C details

- Monitor chip: Texas Instruments **INA219** (voltage / current / power).
- I2C bus: **I2C-1** (Pi GPIO 2 = SDA / GPIO 3 = SCL, physical pins 3 / 5).
- I2C address: **`0x41`**.
- Battery pack: 3S (3x 18650 in series), nominal range ~9.0 V (empty) to 12.6 V (full).
- Enable the bus: uncomment `dtparam=i2c_arm=on` in `/boot/firmware/config.txt`,
  add `i2c-dev` to `/etc/modules`, reboot; verify with `i2cdetect -y 1` (address 41).
