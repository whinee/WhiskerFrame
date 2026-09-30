Module whiskerframe.transport
=============================
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

Classes
-------

`SerialTransport(port: str, baudrate: int = 115200, *, timeout: float | None = 1.0)`
:   pyserial-backed transport for framed CYD drawing commands.
    
    Open a pyserial ``Serial`` port on construction and expose :meth:`send` and
    :meth:`send_command` to write framed bytes to the CYD firmware. The instance
    is a context manager (:meth:`__enter__` / :meth:`__exit__`) and also supports
    :meth:`close` for explicit port release.
    
    pyserial is optional: constructing this class without it installed raises a
    clear :class:`ModuleNotFoundError` naming the ``serial`` extra. The pure
    command path never constructs a ``SerialTransport`` and never imports
    pyserial (Req 4.3).
    
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

    ### Methods

    `close(self) ‑> None`
    :   Close the underlying serial port.
        
        Release the OS serial device so the port becomes available again;
        idempotent to call after the port is already closed.

    `send(self, frame: bytes) ‑> None`
    :   Write pre-framed bytes to the serial port.
        
        Transmit an already-framed ``[SOF][LEN][OPCODE][PAYLOAD][CRC8]`` byte
        sequence (as produced by :func:`whiskerframe.protocol.serialize` or
        :func:`whiskerframe.protocol.frame`) to the CYD over serial.
        
        Args:
        - frame (`bytes`): Complete framed byte sequence to transmit.

    `send_command(self, command: DrawText | DrawRect) ‑> None`
    :   Serialize a drawing command and write its framed bytes to the port.
        
        Encode the resolved command via :func:`whiskerframe.protocol.serialize`
        and transmit the resulting frame with :meth:`send` (Req 1.1).
        
        Args:
        - command (`DrawText | DrawRect`): Resolved command to serialize and send.