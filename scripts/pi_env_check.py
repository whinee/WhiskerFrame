"""
Pi_Host connectivity and Python-environment verification (Req 6.1-6.3).

Verifies that the Pi_Host at ``10.0.0.212`` has the components the Host_Library
and flashing tools need: ``python3``, ``pip``, and the ``pyserial`` package. The
check is read-only and makes no changes to the Pi.

The module deliberately separates two concerns so the reporting logic can be
tested without a network or an SSH client:

- A pure reporting layer (`missing_components`, `format_report`) that maps
  component presence flags to the specific absent component names and never
  halts the verification flow on a single missing component (Req 6.3).
- A thin OS/SSH invocation layer (`ssh_run`, `probe_pi_environment`,
  `verify_pi_environment`) that connects over SSH and runs read-only probes,
  feeding their results into the pure layer.

The SSH private key is referenced by path only (``/home/lyra/.ssh/id_rsa``); its
contents are never read or logged by this module.
"""

from __future__ import annotations

import shlex
import subprocess
from typing import NamedTuple

from config import env, load_yaml_config
from debug import tracepoint

_CONFIG = load_yaml_config()
_UPS = _CONFIG.get("ups", {})
_COMPONENTS_CFG = _CONFIG.get("components", ["python3", "pip", "pyserial"])

__all__ = [
    "COMPONENTS",
    "DEFAULT_KEY_PATH",
    "DEFAULT_PROBES",
    "DEFAULT_VENV_PATH",
    "PI_HOST",
    "PI_USER",
    "ComponentPresence",
    "EnvReport",
    "ProbeResult",
    "build_probes",
    "format_report",
    "missing_components",
    "probe_pi_environment",
    "ssh_run",
    "verify_pi_environment",
]

PI_HOST: str = env("PI_HOST", "10.0.0.212")
"""Address of the Pi_Host from ``.env`` (Req 6.1)."""

PI_USER: str = env("PI_USER", "root")
"""SSH username from ``.env`` (Req 6.1)."""

DEFAULT_KEY_PATH: str = env("DEFAULT_KEY_PATH", "/home/lyra/.ssh/id_rsa")
"""SSH private key path from ``.env`` (referenced by path only; never read)."""

DEFAULT_VENV_PATH: str = env("DEFAULT_VENV_PATH", "/opt/cyd-display-link/pi/.venv")
"""uv-managed Pi host venv path from ``.env``. Probes prefer this interpreter and
fall back to the system ``python3`` when absent, so the check reflects the actual
runtime rather than the Pi's externally-managed system Python (PEP 668)."""

COMPONENTS: tuple[str, ...] = tuple(_COMPONENTS_CFG)
"""Ordered components verified on the Pi_Host, from ``.whiskerframe.yaml`` (Req 6.2)."""


def _probe_script(venv_path: str, action: str) -> str:
    r"""
    Build a non-login POSIX ``sh`` snippet that runs ``action`` on the runtime Python.

    Select the uv-managed venv interpreter at ``<venv_path>/bin/python`` when it is
    executable, otherwise fall back to the system ``python3`` resolved from
    ``PATH`` via ``command -v``. The snippet is deliberately plain POSIX ``sh`` and
    is run with ``sh -c`` (never a *login* shell), so it does not source the Pi's
    shell rc files -- those can be slow or block, which previously made each probe
    hang until the SSH timeout. If no interpreter is found the snippet exits
    non-zero so the component is reported absent.

    Args:
    - venv_path (`str`): Path to the uv-managed Pi host venv.
    - action (`str`): Arguments appended after the interpreter (e.g. ``--version``).

    Returns:
    `str`: A POSIX ``sh`` command string ending by exec-ing the interpreter.

    """
    venv_py = f"{venv_path}/bin/python"
    return (
        f'if [ -x "{venv_py}" ]; then PY="{venv_py}"; '
        'else PY="$(command -v python3 || true)"; fi; '
        '[ -n "$PY" ] || exit 127; '
        f'exec "$PY" {action}'
    )


def _pip_probe_script(venv_path: str) -> str:
    r"""
    Build a non-login ``sh`` snippet that detects an available pip.

    A uv-managed venv does not ship ``pip`` (uv is the package manager), so this
    probe accepts pip from any of: the venv's ``python -m pip``, the system
    ``python3 -m pip``, or a standalone ``pip3`` / ``pip`` on ``PATH``. Any one of
    these succeeding means pip is available to the host (Req 6.2). Runs under a
    non-login ``sh`` so no shell rc files are sourced.

    Args:
    - venv_path (`str`): Path to the uv-managed Pi host venv.

    Returns:
    `str`: A POSIX ``sh`` command string that exits zero when some pip works.

    """
    venv_py = f"{venv_path}/bin/python"
    return (
        f'{{ [ -x "{venv_py}" ] && "{venv_py}" -m pip --version; }} '
        "|| python3 -m pip --version "
        "|| pip3 --version "
        "|| pip --version"
    )


def build_probes(venv_path: str = DEFAULT_VENV_PATH) -> dict[str, tuple[str, ...]]:
    r"""
    Build the read-only remote probe commands for each component.

    Each probe runs through the Pi's runtime interpreter (the venv Python when
    present, else system ``python3``) so ``pyserial`` is detected where the
    uv-managed runtime actually installs it (Req 6.2). Every probe is read-only
    and makes no change to the Pi. Commands are run with a non-login ``sh -c`` so
    no shell rc files are sourced (avoiding slow or hanging login shells).

    Args:
    - venv_path (`str`, optional): Path to the uv-managed Pi host venv. Defaults to `DEFAULT_VENV_PATH`.

    Returns:
    `dict[str, tuple[str, ...]]`: Component-to-command map keyed by component name.

    """
    return {
        "python3": ("sh", "-c", _probe_script(venv_path, "--version")),
        "pip": ("sh", "-c", _pip_probe_script(venv_path)),
        "pyserial": ("sh", "-c", _probe_script(venv_path, "-c 'import serial'")),
    }


DEFAULT_PROBES: dict[str, tuple[str, ...]] = build_probes()
"""Read-only remote command for each component (Req 6.2). None mutate the Pi.

Probes run through the Pi runtime interpreter (uv venv Python when present, else
system ``python3``), so ``pyserial`` installed in the uv-managed venv is detected
rather than reported missing."""


class ComponentPresence(NamedTuple):
    """
    Presence flags for each verified Pi_Host component.

    Each field is ``True`` when the corresponding component was detected on the
    Pi_Host and ``False`` when it is absent. This is the sole input to the pure
    reporting layer, keeping report generation independent of SSH.

    Attributes:
    - python3 (`bool`): Whether ``python3`` is present.
    - pip (`bool`): Whether ``pip`` is present.
    - pyserial (`bool`): Whether the ``pyserial`` package is importable.

    """

    python3: bool
    pip: bool
    pyserial: bool


class EnvReport(NamedTuple):
    """
    Outcome of an environment verification.

    Attributes:
    - presence (`ComponentPresence`): Per-component presence flags.
    - missing (`tuple[str, ...]`): Absent component names, in `COMPONENTS` order.
    - all_present (`bool`): Whether every component was detected.
    - summary (`str`): Human-readable single-line report.

    """

    presence: ComponentPresence
    missing: tuple[str, ...]
    all_present: bool
    summary: str


class ProbeResult(NamedTuple):
    """
    Result of a single read-only remote probe command.

    Attributes:
    - present (`bool`): Whether the probe succeeded (component detected).
    - returncode (`int`): Exit status of the remote command.

    """

    present: bool
    returncode: int


def missing_components(presence: ComponentPresence) -> tuple[str, ...]:
    """
    Return the specific absent components, in canonical order.

    Pure function: maps presence flags to exactly the names of the components
    that are absent, preserving `COMPONENTS` order. Reports only the specific
    missing components and never treats one absent component as a broader halt
    (Req 6.3).

    Args:
    - presence (`ComponentPresence`): Per-component presence flags.

    Returns:
    `tuple[str, ...]`: Absent component names in `COMPONENTS` order; empty when
    all components are present.

    """
    flags = {
        "python3": presence.python3,
        "pip": presence.pip,
        "pyserial": presence.pyserial,
    }
    return tuple(name for name in COMPONENTS if not flags[name])


def format_report(presence: ComponentPresence) -> EnvReport:
    """
    Build a full environment report from presence flags.

    Pure function: derives the missing-component list and a human-readable
    summary. Continues the normal verification flow regardless of how many
    components are absent, reporting each absent component by name (Req 6.3).

    Args:
    - presence (`ComponentPresence`): Per-component presence flags.

    Returns:
    `EnvReport`: The presence flags, ordered missing names, an all-present
    flag, and a one-line summary.

    """
    missing = missing_components(presence)
    all_present = not missing
    if all_present:
        summary = "All components present: " + ", ".join(COMPONENTS) + "."
    else:
        summary = "Missing components: " + ", ".join(missing) + "."
    tracepoint(
        "pi_env.report",
        missing=",".join(missing) if missing else "none",
        all_present=all_present,
    )
    return EnvReport(
        presence=presence,
        missing=missing,
        all_present=all_present,
        summary=summary,
    )


def ssh_run(
    command: tuple[str, ...],
    *,
    host: str = PI_HOST,
    user: str = PI_USER,
    key_path: str = DEFAULT_KEY_PATH,
    timeout: float = 10.0,
) -> subprocess.CompletedProcess[bytes]:
    """
    Run a read-only command on the Pi_Host over SSH.

    Connects to the Pi_Host as ``user`` using the private key at ``key_path``
    (Req 6.1). The key is passed to ``ssh`` by path via ``-i`` only; its
    contents are never read or logged by this function. ``command`` is joined
    into a single shell-quoted string before being handed to ``ssh``: the remote
    ``sshd`` concatenates its trailing arguments and re-parses them through the
    login shell, so passing separate argv elements would double-split the command
    and corrupt any quoting. `shlex.quote` on each element preserves it intact.

    Args:
    - command (`tuple[str, ...]`): Remote command and arguments to execute.
    - host (`str`, optional): Pi_Host address. Defaults to `PI_HOST`.
    - user (`str`, optional): SSH username. Defaults to `PI_USER`.
    - key_path (`str`, optional): Path to the SSH private key. Defaults to `DEFAULT_KEY_PATH`.
    - timeout (`float`, optional): Per-command timeout in seconds. Defaults to `10.0`.

    Returns:
    `subprocess.CompletedProcess[bytes]`: The completed SSH invocation.

    """
    remote = " ".join(shlex.quote(part) for part in command)
    tracepoint("pi_env.ssh_run", host=host, remote=remote)
    ssh_command = (
        "ssh",
        "-i",
        key_path,
        "-o",
        "BatchMode=yes",
        "-o",
        "StrictHostKeyChecking=accept-new",
        "-o",
        f"ConnectTimeout={max(1, int(timeout))}",
        f"{user}@{host}",
        remote,
    )
    return subprocess.run(  # noqa: S603
        ssh_command,
        capture_output=True,
        timeout=timeout,
        check=False,
    )


def probe_pi_environment(
    *,
    host: str = PI_HOST,
    user: str = PI_USER,
    key_path: str = DEFAULT_KEY_PATH,
    venv_path: str = DEFAULT_VENV_PATH,
    probes: dict[str, tuple[str, ...]] | None = None,
    timeout: float = 10.0,
) -> dict[str, ProbeResult]:
    """
    Run each read-only component probe on the Pi_Host over SSH.

    Executes ``python3 --version``, ``pip --version``, and
    ``python3 -c "import serial"`` (Req 6.2) via `ssh_run`. Each probe is
    read-only and makes no changes to the Pi. A non-zero exit status marks the
    component absent; a failed connection or timeout marks every probe absent so
    the pure layer can still report a complete result (Req 6.3).

    Args:
    - host (`str`, optional): Pi_Host address. Defaults to `PI_HOST`.
    - user (`str`, optional): SSH username. Defaults to `PI_USER`.
    - key_path (`str`, optional): Path to the SSH private key. Defaults to `DEFAULT_KEY_PATH`.
    - probes (`dict[str, tuple[str, ...]] | None`, optional): Component-to-command map. Defaults to `DEFAULT_PROBES`.
    - timeout (`float`, optional): Per-probe timeout in seconds. Defaults to `10.0`.

    Returns:
    `dict[str, ProbeResult]`: Probe result keyed by component name.

    """
    active_probes = build_probes(venv_path) if probes is None else probes
    results: dict[str, ProbeResult] = {}
    for name, command in active_probes.items():
        try:
            completed = ssh_run(
                command,
                host=host,
                user=user,
                key_path=key_path,
                timeout=timeout,
            )
        except (OSError, subprocess.SubprocessError):
            results[name] = ProbeResult(present=False, returncode=-1)
            tracepoint(
                "pi_env.probe_result",
                component=name,
                present=False,
                returncode=-1,
            )
            continue
        results[name] = ProbeResult(
            present=completed.returncode == 0,
            returncode=completed.returncode,
        )
        tracepoint(
            "pi_env.probe_result",
            component=name,
            present=completed.returncode == 0,
            returncode=completed.returncode,
        )
    return results


def verify_pi_environment(
    *,
    host: str = PI_HOST,
    user: str = PI_USER,
    key_path: str = DEFAULT_KEY_PATH,
    venv_path: str = DEFAULT_VENV_PATH,
    timeout: float = 10.0,
) -> EnvReport:
    """
    Verify the Pi_Host Python environment and report missing components.

    Orchestrates the read-only SSH probes (`probe_pi_environment`) and feeds
    their results into the pure reporting layer (`format_report`). The check is
    read-only and reports exactly the absent components without halting on any
    single missing one (Req 6.1, 6.2, 6.3).

    Args:
    - host (`str`, optional): Pi_Host address. Defaults to `PI_HOST`.
    - user (`str`, optional): SSH username. Defaults to `PI_USER`.
    - key_path (`str`, optional): Path to the SSH private key. Defaults to `DEFAULT_KEY_PATH`.
    - timeout (`float`, optional): Per-probe timeout in seconds. Defaults to `10.0`.

    Returns:
    `EnvReport`: The full environment report.

    """
    probed = probe_pi_environment(
        host=host,
        user=user,
        key_path=key_path,
        venv_path=venv_path,
        timeout=timeout,
    )
    presence = ComponentPresence(
        python3=probed["python3"].present,
        pip=probed["pip"].present,
        pyserial=probed["pyserial"].present,
    )
    return format_report(presence)


if __name__ == "__main__":
    report = verify_pi_environment()
    print(report.summary)
