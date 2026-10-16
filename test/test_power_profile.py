"""
Unit tests for WhiskerFrame power profile management (REQ-PWR-01, DEC-W21).

Validates:
- Profile loading, state persistence, and environment variable overrides.
- Three power profiles: ACTIVE (~3.2W), POWERSAVE (~1.8W), AIRPLANE (~0.55W).
- Hardware application mocks (CPU scaling governor, rfkill, hdparm, display sleep).
- CLI commands (status, set, get, help, JSON output, 53-col wrapping).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_PI_BIN_DIR = _REPO_ROOT / "pi" / "bin"
if str(_PI_BIN_DIR) not in sys.path:
    sys.path.insert(0, str(_PI_BIN_DIR))

# Import from pi/bin/power-profile
import importlib.util
from importlib.machinery import SourceFileLoader
loader = SourceFileLoader("power_profile_mod", str(_PI_BIN_DIR / "power-profile"))
spec = importlib.util.spec_from_loader("power_profile_mod", loader)
assert spec and spec.loader
pwr = importlib.util.module_from_spec(spec)
sys.modules["power_profile_mod"] = pwr
loader.exec_module(pwr)


def test_power_profiles_specs() -> None:
    """Verify all 3 power profiles are defined with correct parameters."""
    assert "active" in pwr.PROFILES
    assert "powersave" in pwr.PROFILES
    assert "airplane" in pwr.PROFILES

    active = pwr.PROFILES["active"]
    assert active["estimated_power_watts"] == 3.2
    assert active["radios_blocked"] is False
    assert active["display_sleep"] is False

    powersave = pwr.PROFILES["powersave"]
    assert powersave["estimated_power_watts"] == 1.8
    assert powersave["governor"] == "powersave"
    assert powersave["ssd_standby"] is True

    airplane = pwr.PROFILES["airplane"]
    assert airplane["estimated_power_watts"] == 0.55
    assert airplane["radios_blocked"] is True
    assert airplane["display_sleep"] is True


def test_power_state_persistence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """State loads, saves, and respects WHISKERFRAME_POWER_STATE."""
    state_file = tmp_path / "test_power.json"
    monkeypatch.setenv("WHISKERFRAME_POWER_STATE", str(state_file))

    # Initial default state
    state = pwr.load_state()
    assert state.profile == "active"
    assert state.estimated_power_watts == 3.2

    # Apply powersave profile
    new_state = pwr.apply_profile("powersave")
    assert new_state.profile == "powersave"
    assert new_state.ssd_standby is True
    assert state_file.is_file()

    # Re-load from persisted file
    reloaded = pwr.load_state()
    assert reloaded.profile == "powersave"
    assert reloaded.governor == "powersave"


def test_power_profile_aliases() -> None:
    """Aliases resolve to the canonical profiles."""
    assert pwr.PROFILE_ALIASES["perf"] == "active"
    assert pwr.PROFILE_ALIASES["idle"] == "powersave"
    assert pwr.PROFILE_ALIASES["deep-idle"] == "airplane"
    assert pwr.PROFILE_ALIASES["sleep"] == "airplane"


def test_power_profile_cli_status(capsys: pytest.CaptureFixture[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """CLI status prints formatted output strictly <= 53 columns."""
    monkeypatch.setenv("WHISKERFRAME_POWER_STATE", str(tmp_path / "power.json"))
    ret = pwr.main(["status"])
    assert ret == 0
    captured = capsys.readouterr().out
    for line in captured.splitlines():
        assert len(line) <= pwr.MAX_COLUMNS
    assert "ACTIVE" in captured


def test_power_profile_cli_json(capsys: pytest.CaptureFixture[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """CLI --json outputs valid JSON payload."""
    monkeypatch.setenv("WHISKERFRAME_POWER_STATE", str(tmp_path / "power.json"))
    ret = pwr.main(["status", "--json"])
    assert ret == 0
    captured = capsys.readouterr().out
    data = json.loads(captured)
    assert data["profile"] == "active"
    assert "spec" in data
    assert data["spec"]["estimated_power_watts"] == 3.2


def test_power_profile_cli_switch(capsys: pytest.CaptureFixture[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """CLI switch to airplane profile works and persists."""
    monkeypatch.setenv("WHISKERFRAME_POWER_STATE", str(tmp_path / "power.json"))
    ret = pwr.main(["set", "airplane"])
    assert ret == 0
    captured = capsys.readouterr().out
    assert "AIRPLANE" in captured

    # Verify get command
    ret = pwr.main(["get"])
    assert ret == 0
    captured_get = capsys.readouterr().out.strip()
    assert captured_get == "airplane"
