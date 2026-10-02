r"""
Pure-stdlib M5Stack CardKB keyboard reader over Linux I2C.

The CardKB is an I2C keypad that returns the ASCII code of the most recent key
press as a single byte read from its I2C address (``0x5F`` on this build), or
``0x00`` when no key is pending. This driver talks to it directly through the
Linux i2c-dev character device using only the Python standard library
(``os`` + ``fcntl.ioctl`` with ``I2C_SLAVE``), so it runs inside the minimal
uv-managed Pi venv with no external dependency.

The device is strictly read-only: a key read is a single-byte I2C read, with no
register writes. Configuration (bus, address, poll cadence) is sourced from the
``cardkb:`` block of ``.whiskerframe.yaml`` by callers; this module's defaults
match the live-verified hardware (``/dev/i2c-0`` @ ``0x5F``).
"""

from __future__ import annotations

import fcntl
import os
import time
from collections.abc import Iterator
from types import TracebackType

__all__ = [
    "I2C_SLAVE",
    "NO_KEY",
    "CardKB",
    "CardKBError",
]

I2C_SLAVE: int = 0x0703
"""Linux i2c-dev ioctl request binding an open fd to a slave address."""

NO_KEY: int = 0x00
"""Byte the CardKB returns when no key press is pending."""

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

    def __init__(self, bus: int = 0, address: int = 0x5F) -> None:
        r"""
        Initialize the reader for a bus and slave address (does not open it).

        Args:
        - bus (`int`, optional): I2C bus number for ``/dev/i2c-N``. Defaults to ``0``.
        - address (`int`, optional): 7-bit CardKB slave address. Defaults to ``0x5F``.

        """
        self.bus = bus
        self.address = address
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
        Open the I2C device and bind it to the CardKB slave address.

        Raises:
        - `CardKBError`: If the device cannot be opened or the address bound.

        """
        device = f"/dev/i2c-{self.bus}"
        try:
            self._fd = os.open(device, os.O_RDWR)
            fcntl.ioctl(self._fd, I2C_SLAVE, self.address)
        except OSError as err:
            self.close()
            raise CardKBError(
                f"cannot open {device} @ {self.address:#04x}: {err}",
            ) from err

    def close(self) -> None:
        r"""
        Close the I2C device if it is open.

        Safe to call more than once; an already-closed descriptor is ignored.

        """
        if self._fd is not None:
            try:
                os.close(self._fd)
            except OSError:
                pass
            self._fd = None

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
        while self._fd is not None:
            key = self.read_key()
            if key != NO_KEY:
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
        backoff = _REOPEN_BACKOFF_START_S
        while True:
            try:
                if self._fd is None:
                    self.open()
                key = self.read_key()
                backoff = _REOPEN_BACKOFF_START_S
                if key != NO_KEY:
                    yield key
                time.sleep(poll_interval_s)
            except CardKBError:
                self.close()
                time.sleep(backoff)
                backoff = min(_REOPEN_BACKOFF_MAX_S, backoff * 2)
