"""
Optional pyserial transport for sending framed drawing commands to the CYD.

Wrap a pyserial ``Serial`` port so resolved :class:`whiskerframe.models.DrawText`
and :class:`whiskerframe.models.DrawRect` commands (or their pre-framed bytes) can
be transmitted to the CYD firmware over the USB-serial link (Req 1.1). The
firmware decodes the same ``[SOF][LEN][OPCODE][PAYLOAD][CRC8]`` frames produced by
:func:`whiskerframe.protocol.serialize`.

pyserial is an optional dependency shipped as the ``serial`` extra
(``pip install whiskerframe[serial]``). The import is guarded so that importing
this module never hard-fails when pyserial is absent; the failure is deferred to
:class:`SerialTransport` construction, which raises a clear
:class:`ModuleNotFoundError` naming the missing extra. The pure command path
(``whiskerframe`` package, :func:`whiskerframe.protocol.serialize`) never imports
this module and therefore never needs pyserial installed (Req 4.3).
"""

from __future__ import annotations

from types import TracebackType
from typing import TYPE_CHECKING, Any

from whiskerframe.models import DrawRect, DrawText
from whiskerframe.protocol import serialize

if TYPE_CHECKING:
    from serial import Serial

__all__ = [
    "SerialTransport",
]

_MISSING_PYSERIAL_MSG = (
    "SerialTransport requires the optional 'pyserial' dependency. "
    "Install it with the 'serial' extra: pip install whiskerframe[serial]."
)


def _require_pyserial() -> Any:
    """
    Import and return the pyserial ``serial`` module, guarding its absence.

    Attempt the deferred import of pyserial so that importing this module stays
    cheap and side-effect-free, and so the pure command path never requires the
    optional dependency (Req 4.3).

    Raises:
    - `ModuleNotFoundError`: If pyserial is not installed, with a message naming
      the ``serial`` extra (``pip install whiskerframe[serial]``).

    Returns:
    `Any`: The imported pyserial ``serial`` module.

    """
    try:
        import serial
    except ModuleNotFoundError as exc:  # pragma: no cover - env-dependent
        raise ModuleNotFoundError(_MISSING_PYSERIAL_MSG) from exc
    return serial


class SerialTransport:
    """
    pyserial-backed transport for framed CYD drawing commands.

    Open a pyserial ``Serial`` port on construction and expose :meth:`send` and
    :meth:`send_command` to write framed bytes to the CYD firmware. The instance
    is a context manager (:meth:`__enter__` / :meth:`__exit__`) and also supports
    :meth:`close` for explicit port release.

    pyserial is optional: constructing this class without it installed raises a
    clear :class:`ModuleNotFoundError` naming the ``serial`` extra. The pure
    command path never constructs a ``SerialTransport`` and never imports
    pyserial (Req 4.3).
    """

    def __init__(
        self,
        port: str,
        baudrate: int = 115200,
        *,
        timeout: float | None = 1.0,
    ) -> None:
        """
        Open a pyserial port for transmitting framed drawing commands.

        Import pyserial lazily (raising if absent) and open the named serial port
        at the given baud rate, ready for :meth:`send` / :meth:`send_command`.

        Args:
        - port (`str`): Serial device path (e.g. ``/dev/ttyUSB0``).
        - baudrate (`int`, optional): Serial baud rate. Defaults to `115200`.
        - timeout (`float | None`, optional): Write/read timeout in seconds, or
          `None` to block indefinitely. Defaults to `1.0`.

        Raises:
        - `ModuleNotFoundError`: If pyserial is not installed, with a message
          naming the ``serial`` extra (``pip install whiskerframe[serial]``).

        """
        serial = _require_pyserial()
        self._serial: Serial = serial.Serial(
            port=port,
            baudrate=baudrate,
            timeout=timeout,
        )

    def send(self, frame: bytes) -> None:
        """
        Write pre-framed bytes to the serial port and flush immediately.

        Transmit an already-framed ``[SOF][LEN][OPCODE][PAYLOAD][CRC8]`` byte
        sequence to the CYD over serial and flush the underlying serial port so
        transmission to the hardware is never delayed.

        Args:
        - frame (`bytes`): Complete framed byte sequence to transmit.

        """
        self._serial.write(frame)
        self._serial.flush()

    def flush(self) -> None:
        """
        Flush the underlying serial port buffer.

        Ensure all written bytes are transmitted over the physical USB serial link immediately.

        """
        self._serial.flush()

    def send_command(self, command: DrawText | DrawRect) -> None:
        """
        Serialize a drawing command and write its framed bytes to the port.

        Encode the resolved command via :func:`whiskerframe.protocol.serialize`
        and transmit the resulting frame with :meth:`send` (Req 1.1).

        Args:
        - command (`DrawText | DrawRect`): Resolved command to serialize and send.

        """
        self.send(serialize(command))

    def close(self) -> None:
        """
        Close the underlying serial port.

        Release the OS serial device so the port becomes available again;
        idempotent to call after the port is already closed.

        """
        self._serial.close()

    def __enter__(self) -> SerialTransport:
        """
        Enter the transport context, returning the open transport.

        Returns:
        `SerialTransport`: This transport with its port open.

        """
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """
        Exit the transport context, closing the serial port.

        Release the serial port via :meth:`close` regardless of whether the
        managed block raised.

        Args:
        - exc_type (`type[BaseException] | None`): Exception type if one was
          raised in the managed block, else `None`.
        - exc_value (`BaseException | None`): Exception instance if raised, else
          `None`.
        - traceback (`TracebackType | None`): Traceback if raised, else `None`.

        """
        self.close()
