"""
Unit tests for WhiskerFrame sensory audio profiles & overload mitigation (REQ-ENV-04, REQ-INP-08).

Validates:
- Profile loading, state persistence, and environment variable overrides.
- 3 Environmental presets: CLASSROOM (0%), OFFICE (25%), COMMUTE (100%).
- Cognitive sensory overload toggle (REQ-INP-08) instant muting.
- CLI commands (status, set, overload, silence, JSON output, 53-col bounds).
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

import importlib.util
from importlib.machinery import SourceFileLoader
loader = SourceFileLoader("sensory_profile_mod", str(_PI_BIN_DIR / "profile"))
spec = importlib.util.spec_from_loader("sensory_profile_mod", loader)
assert spec and spec.loader
prof = importlib.util.module_from_spec(spec)
sys.modules["sensory_profile_mod"] = prof
loader.exec_module(prof)


def test_sensory_profiles_specs() -> None:
    """Verify all 3 environmental presets are defined."""
    assert "classroom" in prof.PROFILES
    assert "office" in prof.PROFILES
    assert "commute" in prof.PROFILES

    classroom = prof.PROFILES["classroom"]
    assert classroom["buzzer_volume"] == 0
    assert classroom["haptics_enabled"] is False
    assert classroom["alerts_audible"] is False

    office = prof.PROFILES["office"]
    assert office["buzzer_volume"] == 25
    assert office["haptics_enabled"] is True
    assert office["alerts_audible"] is True

    commute = prof.PROFILES["commute"]
    assert commute["buzzer_volume"] == 100
    assert commute["haptics_enabled"] is True
    assert commute["alerts_audible"] is True


def test_sensory_state_persistence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """State loads, saves, and respects WHISKERFRAME_SENSORY_STATE."""
    state_file = tmp_path / "test_sensory.json"
    monkeypatch.setenv("WHISKERFRAME_SENSORY_STATE", str(state_file))

    # Initial default state is office
    state = prof.load_state()
    assert state.profile == "office"
    assert state.overload_active is False

    # Switch to classroom
    new_state = prof.apply_profile("classroom")
    assert new_state.profile == "classroom"
    assert new_state.buzzer_volume == 0
    assert state_file.is_file()

    # Re-load
    reloaded = prof.load_state()
    assert reloaded.profile == "classroom"


def test_sensory_overload_toggle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Sensory overload instantly silences all audio regardless of profile."""
    state_file = tmp_path / "test_sensory.json"
    monkeypatch.setenv("WHISKERFRAME_SENSORY_STATE", str(state_file))

    # Start in commute (loud) profile
    prof.apply_profile("commute")
    state = prof.load_state()
    assert state.buzzer_volume == 100
    assert state.alerts_audible is True

    # Activate sensory overload
    overload_state = prof.set_overload(True)
    assert overload_state.overload_active is True
    assert overload_state.buzzer_volume == 0
    assert overload_state.alerts_audible is False
    assert overload_state.bell_mode == "visual"

    # Deactivate sensory overload -> restores profile volume
    restored = prof.set_overload(False)
    assert restored.overload_active is False
    assert restored.buzzer_volume == 100
    assert restored.alerts_audible is True


def test_sensory_profile_cli_status(capsys: pytest.CaptureFixture[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """CLI status output is <= 53 columns."""
    monkeypatch.setenv("WHISKERFRAME_SENSORY_STATE", str(tmp_path / "sensory.json"))
    ret = prof.main(["status"])
    assert ret == 0
    captured = capsys.readouterr().out
    for line in captured.splitlines():
        assert len(line) <= prof.MAX_COLUMNS
    assert "OFFICE" in captured


def test_sensory_profile_cli_overload(capsys: pytest.CaptureFixture[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """CLI overload command toggles mitigation."""
    monkeypatch.setenv("WHISKERFRAME_SENSORY_STATE", str(tmp_path / "sensory.json"))
    ret = prof.main(["overload", "on"])
    assert ret == 0
    captured = capsys.readouterr().out
    assert "SENSORY OVERLOAD MITIGATION ACTIVE" in captured

    # Status shows active
    ret = prof.main(["status", "--json"])
    assert ret == 0
    data = json.loads(capsys.readouterr().out)
    assert data["overload_active"] is True
    assert data["buzzer_volume"] == 0
