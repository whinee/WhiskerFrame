r"""
Pure-stdlib M5Stack CardKB keyboard reader over Linux I2C.

The CardKB is an I2C keypad that returns the ASCII code of the most recent key
press as a single byte read from its I2C address (``0x5F`` on this build), or
``0x00`` when no key is pending. This driver talks to it directly through the
Linux i2c-dev character device using only the Python standard library
(``os`` + ``fcntl.ioctl`` with ``I2C_SLAVE``), so it runs inside the minimal
uv-managed Pi venv with no external dependency.

CardKB I2C Firmware and Register Architecture at 0x5F:
- Microcontroller: ATmega328P / ATmega8A firmware (M5Stack CardKeyBoard.ino).
- Registers: None. The firmware does NOT expose memory-mapped configuration
  registers, status registers, or non-volatile EEPROM storage for power-on LED state.
- I2C Read Protocol: Slave returns a single byte containing the ASCII code of
  the pending keystroke, or ``NO_KEY`` (``0x00``) when idle.
- I2C Write Protocol: Accepts single-byte opcode ``0x11`` (`OPCODE_CLEAR_LED`)
  to extinguish the onboard SK6812 NeoPixel, or 4-byte command ``0x13 [R, G, B]``
  (`OPCODE_SET_LED`) to set its color.
- Boot and Power-Cycle Invariant: Because stock firmware provides no persistent
  register to default the NeoPixel to OFF across power cycles, `CardKB.open()`,
  `CardKB.close()`, and `robust_keys()` (upon reconnect / bus recovery) explicitly
  enforce the default-off invariant by dispatching opcode ``0x11``.

Configuration (bus, address, poll cadence) is sourced from the ``cardkb:`` block
of ``.whiskerframe.yaml`` by callers; this module's defaults match the
live-verified hardware (``/dev/i2c-0`` @ ``0x5F``).
"""

from __future__ import annotations

import fcntl
import os
import time
from collections.abc import Iterator
from types import TracebackType

__all__ = [
    "DEBOUNCE_WINDOW_S",
    "I2C_SLAVE",
    "NO_KEY",
    "OPCODE_CLEAR_LED",
    "OPCODE_SET_LED",
    "VALID_BYTES",
    "CardKB",
    "CardKBError",
    "KeyFilter",
]

I2C_SLAVE: int = 0x0703
"""Linux i2c-dev ioctl request binding an open fd to a slave address."""

NO_KEY: int = 0x00
"""Byte the CardKB returns when no key press is pending."""

OPCODE_CLEAR_LED: int = 0x11
"""CardKB I2C firmware command byte to clear/turn off the onboard SK6812 NeoPixel."""

OPCODE_SET_LED: int = 0x13
"""CardKB I2C firmware command byte to set the onboard SK6812 NeoPixel RGB color."""

VALID_BYTES: frozenset[int] = frozenset(
    set(range(0x01, 0x20))  # C0 control bytes: Ctrl+letter, Tab(0x09), Enter(0x0D), Esc(0x1B), Backspace(0x08)
    | set(range(0x20, 0x7F))  # printable ASCII (incl. Space 0x20 and all Sym-layer punctuation)
    | {0x7F}  # Shift+Del (firmware emits 127)
    | set(range(0x80, 0xB0))  # Fn layer: esc..space map to 128..175 (0x80-0xAF)
    | {0xB4, 0xB5, 0xB6, 0xB7},  # arrows: left, up, down, right
)
"""Bytes the CardKB may legitimately emit; everything else is ghost/noise.

Traced to M5Stack CardKB v1.1 firmware keymap (CardKeyBoard.ino, column order
nor/shift/long_shift/sym/long_sym/fn/long_fn): nor + Sym layers stay in
0x08-0x7E, Shift+Del emits 0x7F, the Fn layer emits 0x80-0xAF (128-175), and the
four arrows emit 0xB4-0xB7. 0x00 is the idle read and 0xFF is the firmware's
internal no-key sentinel; both are intentionally excluded.
"""

DEBOUNCE_WINDOW_S: float = 0.03
"""Window within which an identical repeated raw byte is treated as rail ripple."""


class KeyFilter:
    r"""
    Pure, hardware-free input filter for CardKB bytes.

    Whitelists valid bytes (`VALID_BYTES`) and drops everything else (idle
    ``0x00``, floating-bus ``0xFF``, stray high bytes). Also debounces: an
    identical raw byte repeated within `DEBOUNCE_WINDOW_S` is rejected as rail
    ripple, while a different byte always passes and the same byte passes again
    once the window elapses. State is minimal (last byte + last time) so it is
    deterministically testable with injected timestamps.
    """

    def __init__(self, window_s: float = DEBOUNCE_WINDOW_S) -> None:
        self.window_s = window_s
        self._last_byte: int | None = None
        self._last_time: float = 0.0

    def accept(self, byte: int, now: float) -> bool:
        r"""
        Return whether ``byte`` read at monotonic ``now`` should be yielded.

        Args:
        - byte (`int`): Raw byte read from the CardKB (``0..255``).
        - now (`float`): Monotonic timestamp of the read, in seconds.

        Returns:
        `bool`: ``True`` to yield the byte, ``False`` to drop it.
        """
        if byte not in VALID_BYTES:
            return False
        if byte == self._last_byte and (now - self._last_time) < self.window_s:
            return False
        self._last_byte = byte
        self._last_time = now
        return True

_REOPEN_BACKOFF_START_S: float = 0.5
"""Initial delay before re-opening the CardKB after a bus error."""

_REOPEN_BACKOFF_MAX_S: float = 5.0
"""Maximum delay between CardKB re-open attempts."""


class CardKBError(RuntimeError):
    """
    Raised when a CardKB I2C transaction fails.

    Wraps the low-level ``OSError`` from opening the bus, binding the slave
    address, or reading a key byte so callers can catch one typed error and keep
    the input loop alive instead of crashing.
    """


class CardKB:
    r"""
    Minimal M5Stack CardKB reader over the Linux i2c-dev character device.

    Opens ``/dev/i2c-{bus}``, binds it to the CardKB slave address via the
    ``I2C_SLAVE`` ioctl, and reads one key byte at a time. Only stdlib is used, so
    it runs in the minimal Pi venv. The device is read-only (single-byte reads).

    Use as a context manager (``with CardKB() as kb: ...``) or call `open` /
    `close` explicitly. Every transaction raises `CardKBError` on failure.

    Attributes:
    - bus (`int`): I2C bus number (the ``N`` in ``/dev/i2c-N``).
    - address (`int`): 7-bit CardKB slave address.

    """

    def __init__(
        self,
        bus: int = 0,
        address: int = 0x5F,
        default_led_off: bool = True,
    ) -> None:
        r"""
        Initialize the reader for a bus and slave address (does not open it).

        Args:
        - bus (`int`, optional): I2C bus number for ``/dev/i2c-N``. Defaults to ``0``.
        - address (`int`, optional): 7-bit CardKB slave address. Defaults to ``0x5F``.
        - default_led_off (`bool`, optional): Whether to ensure NeoPixel LED defaults
          to OFF across boot and power cycles. Defaults to ``True``.

        """
        self.bus = bus
        self.address = address
        self.default_led_off = default_led_off
        self._fd: int | None = None

    def __enter__(self) -> CardKB:
        r"""
        Open the device for use in a ``with`` block.

        Returns:
        `CardKB`: This opened reader instance.

        """
        self.open()
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
        Open the I2C device, bind it to the slave address, and ensure LED is OFF.

        The stock CardKB firmware (ATmega328P/8A) has no persistent configuration
        registers or EEPROM storage for default LED state at power-on. When
        ``default_led_off`` is enabled, this method actively transmits opcode
        ``0x11`` immediately after binding the slave address to guarantee the
        onboard SK6812 NeoPixel is extinguished across boot and power cycles.

        Raises:
        - `CardKBError`: If the device cannot be opened or the address bound.

        """
        device = f"/dev/i2c-{self.bus}"
        try:
            self._fd = os.open(device, os.O_RDWR)
            fcntl.ioctl(self._fd, I2C_SLAVE, self.address)
            if self.default_led_off:
                self.clear_led()
        except OSError as err:
            self.close()
            raise CardKBError(
                f"cannot open {device} @ {self.address:#04x}: {err}",
            ) from err

    def close(self) -> None:
        r"""
        Close the I2C device if it is open, ensuring NeoPixel is extinguished.

        Safe to call more than once; an already-closed descriptor is ignored.

        """
        if self._fd is not None:
            if self.default_led_off:
                self.clear_led()
            try:
                os.close(self._fd)
            except OSError:
                pass
            self._fd = None

    def ensure_default_led_off(self) -> bool:
        r"""
        Ensure the CardKB onboard SK6812 NeoPixel is turned off.

        Enforces the default-off invariant across boot and power cycles by
        transmitting opcode ``0x11`` to slave address ``0x5F``.

        Returns:
        `bool`: ``True`` if transmitted successfully, ``False`` on error.

        """
        return self.clear_led()

    def read_key(self) -> int:
        r"""
        Read one key byte from the CardKB.

        Returns the ASCII code of the pending key press, or `NO_KEY` (``0``) when
        no key is pending. A single-byte read; never writes to the device.

        Raises:
        - `CardKBError`: If the device is not open or the read fails.

        Returns:
        `int`: The key byte in ``0..255`` (``0`` means no key).

        """
        if self._fd is None:
            raise CardKBError("CardKB device is not open; call open() first")
        try:
            data = os.read(self._fd, 1)
        except OSError as err:
            raise CardKBError(f"read failed: {err}") from err
        return data[0] if data else NO_KEY

    def set_led(self, r: int, g: int, b: int) -> bool:
        r"""
        Set the CardKB onboard SK6812 NeoPixel RGB color.

        CardKB firmware (receiveEvent) supports opcode ``0x13`` (`OPCODE_SET_LED`)
        with 3 RGB byte parameters: ``bytes([0x13, r, g, b])``. Fails silent on bus
        error.

        Args:
        - r (`int`): Red intensity (``0..255``).
        - g (`int`): Green intensity (``0..255``).
        - b (`int`): Blue intensity (``0..255``).

        Returns:
        `bool`: ``True`` if transmitted successfully, ``False`` on bus error.

        """
        if self._fd is None:
            return False
        try:
            os.write(self._fd, bytes([OPCODE_SET_LED, r & 0xFF, g & 0xFF, b & 0xFF]))
            return True
        except OSError:
            return False

    def clear_led(self) -> bool:
        r"""
        Turn off the CardKB onboard SK6812 NeoPixel.

        CardKB firmware supports opcode ``0x11`` (`OPCODE_CLEAR_LED`) to clear
        the pixel.

        Returns:
        `bool`: ``True`` if transmitted successfully, ``False`` on bus error.

        """
        if self._fd is None:
            return False
        try:
            os.write(self._fd, bytes([OPCODE_CLEAR_LED]))
            return True
        except OSError:
            return False

    def keys(self, poll_interval_s: float = 0.05) -> Iterator[int]:
        r"""
        Yield key bytes as they are pressed, polling at a fixed cadence.

        Continuously reads the CardKB, yielding each non-zero key byte once per
        press and sleeping ``poll_interval_s`` between polls. Runs until the
        caller stops iterating or `close` is called.

        Args:
        - poll_interval_s (`float`, optional): Seconds between polls. Defaults to ``0.05``.

        Yields:
        `int`: Each pressed key's ASCII byte (``1..255``).

        """
        key_filter = KeyFilter()
        while self._fd is not None:
            key = self.read_key()
            if key_filter.accept(key, time.monotonic()):
                yield key
            time.sleep(poll_interval_s)

    def robust_keys(
        self,
        poll_interval_s: float = 0.05,
    ) -> Iterator[int]:
        r"""
        Yield key bytes forever, self-recovering from bus errors (field-safe).

        Like `keys`, but never propagates a `CardKBError`: if the device throws a
        bus error (transient I2C glitch, a momentary disconnect, or the keypad
        being unplugged), the reader closes, waits with bounded exponential
        backoff, and re-opens, resuming once the CardKB responds again. This is
        the iterator the deployed input path should use, since the cyberdeck may
        run unattended where the keypad cannot be reseated by hand.

        The generator opens the device itself if it is not already open, so a
        caller can simply iterate it. A successful read resets the backoff.

        Args:
        - poll_interval_s (`float`, optional): Seconds between polls when healthy. Defaults to ``0.05``.

        Yields:
        `int`: Each pressed key's ASCII byte (``1..255``).

        """
        key_filter = KeyFilter()
        backoff = _REOPEN_BACKOFF_START_S
        while True:
            try:
                if self._fd is None:
                    self.open()
                key = self.read_key()
                backoff = _REOPEN_BACKOFF_START_S
                if key_filter.accept(key, time.monotonic()):
                    yield key
                time.sleep(poll_interval_s)
            except CardKBError:
                self.close()
                time.sleep(backoff)
                backoff = min(_REOPEN_BACKOFF_MAX_S, backoff * 2)
