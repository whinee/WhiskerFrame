"""
Unit tests for critical system state alerts & profile governance (REQ-INP-07).

Validates:
- Battery capacity thresholds: <=5% CRITICAL, <=15% WARNING.
- Thermal thresholds: >=80°C CRITICAL, >=75°C WARNING.
- Memory thresholds: <50MB CRITICAL, <100MB WARNING.
- Governance by active sensory profile and overload mitigation.
"""

from __future__ import annotations

import pytest

from whiskerframe.alerts import (
    AlertCategory,
    AlertSeverity,
    SystemMetrics,
    check_system_health,
    evaluate_alerts,
)


def test_battery_alerts_nominal() -> None:
    """Healthy battery produces no alert events."""
    metrics = SystemMetrics(battery_percent=85.0, thermal_celsius=50.0, available_ram_mb=250.0)
    events = evaluate_alerts(metrics)
    assert len(events) == 0


def test_battery_alerts_low_and_critical() -> None:
    """Low battery triggers warning; <=5% triggers critical."""
    # Low warning
    metrics_low = SystemMetrics(battery_percent=12.0, thermal_celsius=50.0, available_ram_mb=250.0)
    events_low = evaluate_alerts(metrics_low)
    assert len(events_low) == 1
    assert events_low[0].category == AlertCategory.BATTERY
    assert events_low[0].severity == AlertSeverity.WARNING

    # Critical cutoff
    metrics_crit = SystemMetrics(battery_percent=4.8, thermal_celsius=50.0, available_ram_mb=250.0)
    events_crit = evaluate_alerts(metrics_crit)
    assert len(events_crit) == 1
    assert events_crit[0].category == AlertCategory.BATTERY
    assert events_crit[0].severity == AlertSeverity.CRITICAL


def test_thermal_alerts() -> None:
    """Thermal threshold alerts trigger at 75°C and 80°C."""
    # Warning
    events_warn = evaluate_alerts(SystemMetrics(battery_percent=80.0, thermal_celsius=76.5, available_ram_mb=200.0))
    assert len(events_warn) == 1
    assert events_warn[0].category == AlertCategory.THERMAL
    assert events_warn[0].severity == AlertSeverity.WARNING

    # Critical
    events_crit = evaluate_alerts(SystemMetrics(battery_percent=80.0, thermal_celsius=82.0, available_ram_mb=200.0))
    assert len(events_crit) == 1
    assert events_crit[0].category == AlertCategory.THERMAL
    assert events_crit[0].severity == AlertSeverity.CRITICAL


def test_memory_alerts() -> None:
    """Memory thresholds trigger below 100MB and 50MB."""
    # Warning
    events_warn = evaluate_alerts(SystemMetrics(battery_percent=80.0, thermal_celsius=50.0, available_ram_mb=75.0))
    assert len(events_warn) == 1
    assert events_warn[0].category == AlertCategory.MEMORY
    assert events_warn[0].severity == AlertSeverity.WARNING

    # Critical
    events_crit = evaluate_alerts(SystemMetrics(battery_percent=80.0, thermal_celsius=50.0, available_ram_mb=35.0))
    assert len(events_crit) == 1
    assert events_crit[0].category == AlertCategory.MEMORY
    assert events_crit[0].severity == AlertSeverity.CRITICAL


def test_alert_sensory_profile_governance() -> None:
    """Audible alerts are muted in classroom profile or under sensory overload."""
    metrics = SystemMetrics(battery_percent=4.0, thermal_celsius=85.0, available_ram_mb=30.0)

    # In commute (loud) stance -> audible & haptic are true
    loud_state = {
        "profile": "commute",
        "buzzer_volume": 100,
        "haptics_enabled": True,
        "alerts_audible": True,
        "overload_active": False,
    }
    loud_events = evaluate_alerts(metrics, loud_state)
    assert len(loud_events) == 3
    assert all(e.audible for e in loud_events)
    assert all(e.haptic for e in loud_events)
    assert all(not e.suppressed_by_profile for e in loud_events)

    # In classroom (silent) stance -> audible is muted
    classroom_state = {
        "profile": "classroom",
        "buzzer_volume": 0,
        "haptics_enabled": False,
        "alerts_audible": False,
        "overload_active": False,
    }
    silent_events = evaluate_alerts(metrics, classroom_state)
    assert len(silent_events) == 3
    assert all(not e.audible for e in silent_events)
    assert all(not e.haptic for e in silent_events)
    assert all(e.suppressed_by_profile for e in silent_events)

    # In sensory overload mode -> audible is strictly suppressed
    overload_state = {
        "profile": "commute",
        "buzzer_volume": 0,
        "haptics_enabled": False,
        "alerts_audible": False,
        "overload_active": True,
    }
    overload_events = evaluate_alerts(metrics, overload_state)
    assert all(not e.audible for e in overload_events)
    assert all(e.suppressed_by_profile for e in overload_events)


def test_check_system_health() -> None:
    """Live health check executes without crashing."""
    events, metrics = check_system_health()
    assert isinstance(metrics.battery_percent, float)
    assert isinstance(metrics.thermal_celsius, float)
    assert isinstance(metrics.available_ram_mb, float)
    assert isinstance(events, list)
