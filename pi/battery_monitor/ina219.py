r"""
Pure-stdlib Texas Instruments INA219 driver over Linux I2C (Req: UPS Module 3S).

Talks to the INA219 current/voltage monitor directly through the Linux i2c-dev
character device (``/dev/i2c-N``), using only the Python standard library
(``os`` + ``fcntl.ioctl`` with ``I2C_SLAVE``). This avoids any external
dependency (``smbus``/``smbus2``) so the driver runs inside the minimal
uv-managed Pi venv that ships only ``pydantic`` / ``pyserial``.

The device is treated as read-only except for the two one-time writes the chip
requires at initialization: the calibration register (so the current/power
registers read in known units) and the configuration register (range, gain,
ADC resolution, continuous mode). All register reads/writes are 16-bit
big-endian, matching the INA219 datasheet.

Register/calibration math (32 V bus range, 2 A max, ``cal = 4096``,
``0.1`` ohm shunt) is pinned to the values verified live on this build:
``bus_voltage_V = (read16(0x02) >> 3) * 0.004`` and
``current_mA = signed(read16(0x04)) * 0.1`` after the calibration write.
"""

from __future__ import annotations

import fcntl
import os
import struct
from types import TracebackType

from .debug import is_debug, tracepoint

__all__ = [
    "I2C_SLAVE",
    "INA219",
    "REG_BUS_VOLTAGE",
    "REG_CALIBRATION",
    "REG_CONFIG",
    "REG_CURRENT",
    "REG_POWER",
    "REG_SHUNT_VOLTAGE",
    "INA219Error",
]

# Linux i2c-dev ioctl request to bind the open fd to a slave address.
I2C_SLAVE: int = 0x0703

# INA219 register map (datasheet).
REG_CONFIG: int = 0x00
REG_SHUNT_VOLTAGE: int = 0x01
REG_BUS_VOLTAGE: int = 0x02
REG_POWER: int = 0x03
REG_CURRENT: int = 0x04
REG_CALIBRATION: int = 0x05

# Configuration word for 32 V bus range, /8 gain, 12-bit ADCs, continuous mode:
# (0x01<<13) | (0x03<<11) | (0x03<<7) | (0x03<<3) | 0x07.
_CONFIG_VALUE: int = (0x01 << 13) | (0x03 << 11) | (0x03 << 7) | (0x03 << 3) | 0x07

# Calibration value paired with a 0.1 ohm shunt for a 0.1 mA current LSB.
_CALIBRATION_VALUE: int = 4096

# Fixed scale factors from the datasheet for the calibration above.
_BUS_VOLTAGE_LSB_V: float = 0.004  # 4 mV per bit, after the >>3 shift.
_CURRENT_LSB_MA: float = 0.1  # 0.1 mA per bit at cal = 4096.
_SHUNT_VOLTAGE_LSB_MV: float = 0.01  # 10 uV per bit.
_POWER_LSB_W: float = 0.002  # 20 * current LSB = 2 mW per bit.

_U16_SIGN_BIT: int = 0x8000
_U16_MODULUS: int = 0x10000


class INA219Error(RuntimeError):
    """
    Raised when an INA219 I2C transaction fails.

    Wraps the low-level ``OSError`` from opening the bus, binding the slave
    address, or reading/writing a register so the daemon can catch a single
    typed error and apply its retry/backoff railguard instead of crashing.

    Attributes:
    - message (`str`): Human-readable description of the failed transaction.

    """


def _to_signed_16(value: int) -> int:
    r"""
    Interpret an unsigned 16-bit register word as a signed two's-complement int.

    The INA219 current and shunt-voltage registers are signed; a raw read yields
    a ``0..65535`` word that must be sign-extended for negative (charging or
    reverse) readings.

    Args:
    - value (`int`): Unsigned 16-bit register value (``0..65535``).

    Returns:
    `int`: The signed interpretation in ``-32768..32767``.

    """
    return value - _U16_MODULUS if value & _U16_SIGN_BIT else value


class INA219:
    r"""
    Minimal INA219 driver over the Linux i2c-dev character device.

    Opens ``/dev/i2c-{bus}``, binds it to the INA219 slave address via the
    ``I2C_SLAVE`` ioctl, and exposes read helpers for bus voltage, current,
    shunt voltage, and power. Only stdlib is used, so it runs in the minimal Pi
    venv. Aside from the one-time calibration/config writes in `calibrate`, the
    device is read-only.

    Use as a context manager (``with INA219() as dev: ...``) or call `open` /
    `close` explicitly. Every transaction raises `INA219Error` on failure so the
    daemon never crashes on a transient bus glitch.

    Attributes:
    - bus (`int`): I2C bus number (the ``N`` in ``/dev/i2c-N``).
    - address (`int`): 7-bit INA219 slave address.

    """

    def __init__(self, bus: int = 1, address: int = 0x41) -> None:
        r"""
        Initialize the driver for a bus and slave address (does not open it).

        Args:
        - bus (`int`, optional): I2C bus number for ``/dev/i2c-N``. Defaults to ``1``.
        - address (`int`, optional): 7-bit INA219 slave address. Defaults to ``0x41``.

        """
        self.bus = bus
        self.address = address
        self._fd: int | None = None

    def __enter__(self) -> INA219:
        r"""
        Open and calibrate the device for use in a ``with`` block.

        Returns:
        `INA219`: This opened, calibrated driver instance.

        """
        self.open()
        self.calibrate()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        r"""
        Close the device when leaving a ``with`` block.

        Args:
        - exc_type (`type[BaseException] | None`): Pending exception type, if any.
        - exc (`BaseException | None`): Pending exception instance, if any.
        - tb (`TracebackType | None`): Pending traceback, if any.

        """
        self.close()

    def open(self) -> None:
        r"""
        Open the I2C device and bind it to the INA219 slave address.

        Opens ``/dev/i2c-{bus}`` read-write (writes are required only for the
        one-time calibration) and issues the ``I2C_SLAVE`` ioctl so subsequent
        reads/writes target the configured address.

        Raises:
        - `INA219Error`: If the device cannot be opened or the address bound.

        """
        device = f"/dev/i2c-{self.bus}"
        try:
            self._fd = os.open(device, os.O_RDWR)
            fcntl.ioctl(self._fd, I2C_SLAVE, self.address)
            tracepoint("ina219.open", bus=self.bus, address=hex(self.address))
        except OSError as err:
            self.close()
            raise INA219Error(
                f"cannot open {device} @ {self.address:#04x}: {err}",
            ) from err

    def close(self) -> None:
        r"""
        Close the I2C device if it is open.

        Safe to call more than once; a missing or already-closed descriptor is
        ignored so cleanup never raises.

        """
        if self._fd is not None:
            try:
                os.close(self._fd)
            except OSError:
                pass
            self._fd = None

    def _require_fd(self) -> int:
        r"""
        Return the open file descriptor or raise if the device is closed.

        Returns:
        `int`: The open ``/dev/i2c-N`` file descriptor.

        Raises:
        - `INA219Error`: If the device has not been opened.

        """
        if self._fd is None:
            raise INA219Error("I2C device is not open; call open() first")
        return self._fd

    def _write_register(self, register: int, value: int) -> None:
        r"""
        Write a 16-bit big-endian value to a register.

        Args:
        - register (`int`): Register address (``0x00``-``0x05``).
        - value (`int`): 16-bit value to write.

        Raises:
        - `INA219Error`: If the write transaction fails.

        """
        fd = self._require_fd()
        payload = struct.pack(">BH", register, value & 0xFFFF)
        try:
            os.write(fd, payload)
        except OSError as err:
            raise INA219Error(f"write reg {register:#04x} failed: {err}") from err

    def _read_register(self, register: int) -> int:
        r"""
        Read a 16-bit big-endian value from a register.

        Writes the register pointer, then reads two bytes back, as the INA219
        register-read protocol requires.

        Args:
        - register (`int`): Register address (``0x00``-``0x05``).

        Returns:
        `int`: The unsigned 16-bit register value (``0..65535``).

        Raises:
        - `INA219Error`: If the read transaction fails or returns short data.

        """
        fd = self._require_fd()
        try:
            os.write(fd, bytes((register,)))
            raw = os.read(fd, 2)
        except OSError as err:
            raise INA219Error(f"read reg {register:#04x} failed: {err}") from err
        if len(raw) != 2:
            raise INA219Error(f"read reg {register:#04x} returned {len(raw)} bytes")
        value = int(struct.unpack(">H", raw)[0])
        if is_debug():
            tracepoint("ina219.read", register=hex(register), raw=value)
        return value

    def calibrate(self) -> None:
        r"""
        Perform the one-time calibration and configuration writes.

        Writes the calibration register (so current/power read in known units)
        and the configuration register (32 V range, /8 gain, 12-bit continuous).
        These are the only writes the driver issues; everything else is
        read-only.

        Raises:
        - `INA219Error`: If either configuration write fails.

        """
        self._write_register(REG_CALIBRATION, _CALIBRATION_VALUE)
        self._write_register(REG_CONFIG, _CONFIG_VALUE)
        tracepoint(
            "ina219.calibrate",
            calibration=_CALIBRATION_VALUE,
            config=hex(_CONFIG_VALUE),
        )

    def bus_voltage_v(self) -> float:
        r"""
        Read the bus voltage in volts.

        Applies the datasheet transform ``(raw >> 3) * 0.004`` to the bus-voltage
        register (the low 3 status bits are shifted out).

        Returns:
        `float`: Bus voltage in volts.

        Raises:
        - `INA219Error`: If the register read fails.

        """
        raw = self._read_register(REG_BUS_VOLTAGE)
        return (raw >> 3) * _BUS_VOLTAGE_LSB_V

    def current_ma(self) -> float:
        r"""
        Read the current in milliamps.

        Sign-extends the current register and scales by the ``0.1`` mA LSB fixed
        by the calibration. Positive values indicate current flowing in the
        configured sense direction; negative values indicate the reverse.

        Returns:
        `float`: Current in milliamps (signed).

        Raises:
        - `INA219Error`: If the register read fails.

        """
        raw = self._read_register(REG_CURRENT)
        return _to_signed_16(raw) * _CURRENT_LSB_MA

    def shunt_mv(self) -> float:
        r"""
        Read the shunt voltage in millivolts.

        Sign-extends the shunt-voltage register and scales by the ``0.01`` mV
        (10 uV) LSB.

        Returns:
        `float`: Shunt voltage in millivolts (signed).

        Raises:
        - `INA219Error`: If the register read fails.

        """
        raw = self._read_register(REG_SHUNT_VOLTAGE)
        return _to_signed_16(raw) * _SHUNT_VOLTAGE_LSB_MV

    def power_w(self) -> float:
        r"""
        Read the power in watts.

        Scales the power register by the ``0.002`` W (2 mW) LSB fixed by the
        calibration.

        Returns:
        `float`: Power in watts.

        Raises:
        - `INA219Error`: If the register read fails.

        """
        raw = self._read_register(REG_POWER)
        return raw * _POWER_LSB_W
