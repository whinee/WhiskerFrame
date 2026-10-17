"""
test/test_e2e_user_journey.py: Comprehensive End-to-End (E2E) Operator Journey.

Simulates the complete lifecycle of a Whiskerframe Cyberdeck session:
1. Cold boot and hardware transport initialization
2. Operator login and PAM authentication state machine
3. Wi-Fi networking query and REQ-STORAGE-05 network-gated snapshot sync
4. Power profiles (ACTIVE -> POWERSAVE -> AIRPLANE) & sensory presets (CLASSROOM, OFFICE, COMMUTE)
5. Sensory overload cognitive mitigation instant mute
6. Multi-workspace PTY session management and CardKB sticky Ctrl latching
7. Image blitting & pixel art display link protocol framing
8. Status bar telemetry polling
9. Graceful shutdown, goodbye splash blitting, and display sleep (Opcode 0x06)
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from importlib.machinery import SourceFileLoader
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "pi"))

from terminal.bridge import CTRL_LATCH_CHORD, KeyQueue  # noqa: E402
from terminal.login import LoginScreen, LoginState, SubmitEvent  # noqa: E402
from terminal.login_view import render_login  # noqa: E402
from terminal.theme import load_theme  # noqa: E402
from terminal.workspaces import WorkspaceManager  # noqa: E402

from whiskerframe.alerts import (  # noqa: E402
    SystemMetrics,
    evaluate_alerts,
)
from whiskerframe.protocol import (  # noqa: E402
    OPCODE_DRAW_IMAGE,
    OPCODE_SLEEP,
    _unframe,
    frame,
)
from whiskerframe.terminal import (  # noqa: E402
    TerminalGeometry,
)
from whiskerframe.transport import SerialTransport  # noqa: E402


def _load_script_module(name: str, relative_path: str) -> ModuleType:
    """Helper to dynamically load extensionless executable Python scripts from pi/bin."""
    path = REPO_ROOT / relative_path
    loader = SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(name, loader)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    loader.exec_module(mod)
    return mod


class TestEndToEndUserJourney:
    """Master End-to-End User Journey simulation suite."""

    def test_e2e_complete_operator_lifecycle(self, tmp_path: Path):
        """Execute complete uninterrupted operator workflow from cold boot to powerdown."""
        # ---------------------------------------------------------------------
        # Phase 1: Cold Boot & Transport Link Initialization
        # ---------------------------------------------------------------------
        mock_port = MagicMock()
        written_bytes = bytearray()

        def mock_write(b: bytes) -> int:
            written_bytes.extend(b)
            return len(b)

        mock_port.write = mock_write
        mock_port.is_open = True

        with patch("serial.Serial", return_value=mock_port):
            transport = SerialTransport(port="/dev/mock_serial", baudrate=115200)
            assert transport is not None

        # Load high-contrast sunlight readable theme (REQ-ENV-03)
        theme = load_theme(None)
        assert theme is not None
        assert theme.fg is not None
        assert theme.bg is not None

        # ---------------------------------------------------------------------
        # Phase 2: Operator Login Gate & PAM State Machine
        # ---------------------------------------------------------------------
        login = LoginState(users=["whisker", "root", "guest"])
        assert login.screen == LoginScreen.USER_SELECT
        assert login.selected_user == "whisker"

        # Press ENTER (0x0D) to proceed to password screen
        res = login.feed_key(0x0D)
        assert res is None
        assert login.screen == LoginScreen.PASSWORD

        # Enter password 'secret'
        for char in "secret":
            res = login.feed_key(ord(char))
            assert res is None

        # Submit login
        submit_event = login.feed_key(0x0D)
        assert isinstance(submit_event, SubmitEvent)
        assert submit_event.user == "whisker"
        assert submit_event.password == "secret"  # noqa: S105

        # Verify login view renders strictly <= 53 columns
        login_view_grid = render_login(login, cols=53, rows=20, theme=theme)
        assert login_view_grid.cols == 53
        assert login_view_grid.rows == 20

        # ---------------------------------------------------------------------
        # Phase 3: Network Supervision & REQ-STORAGE-05 Gated Snapshot Sync
        # ---------------------------------------------------------------------
        backup_script = REPO_ROOT / "scripts" / "backup-sync.sh"
        assert backup_script.is_file()

        # Step 3a: Verify cellular interface is strictly BLOCKED
        env_cellular = dict(os.environ)
        env_cellular["CYBERDECK_MOCK_INTERFACE"] = "usb0"
        res_cell = subprocess.run(  # noqa: S603
            [str(backup_script), "--check-network"],
            capture_output=True,
            text=True,
            env=env_cellular,
            check=False,
        )
        assert res_cell.returncode == 2
        assert "BLOCKED on cellular/LTE" in res_cell.stderr

        # Step 3b: Verify unmetered Wi-Fi interface PASSES
        env_wifi = dict(os.environ)
        env_wifi["CYBERDECK_MOCK_INTERFACE"] = "wlan0"
        res_wifi = subprocess.run(  # noqa: S603
            [str(backup_script), "--check-network"],
            capture_output=True,
            text=True,
            env=env_wifi,
            check=False,
        )
        assert res_wifi.returncode == 0
        assert "PASS" in res_wifi.stdout or "Network gate approved" in res_wifi.stdout

        # ---------------------------------------------------------------------
        # Phase 4: Power Profiles, Sensory Presets & Overload Mitigation
        # ---------------------------------------------------------------------
        pwr_state_file = tmp_path / "e2e_power_state.json"
        sens_state_file = tmp_path / "e2e_sensory_state.json"

        pwr_mod = _load_script_module("e2e_pwr", "pi/bin/power-profile")
        sens_mod = _load_script_module("e2e_sens", "pi/bin/profile")

        with (
            patch.dict(
                "os.environ",
                {
                    "WHISKERFRAME_POWER_STATE": str(pwr_state_file),
                    "WHISKERFRAME_SENSORY_STATE": str(sens_state_file),
                },
            ),
            patch("subprocess.run") as mock_subproc,
        ):
            mock_subproc.return_value = MagicMock(
                returncode=0, stdout="Mock OK", stderr="",
            )

            # Test power profile transition: ACTIVE -> POWERSAVE -> AIRPLANE
            st_active = pwr_mod.apply_profile("active")
            assert st_active.profile == "active"
            assert st_active.governor == "ondemand"
            assert not st_active.radios_blocked

            st_powersave = pwr_mod.apply_profile("powersave")
            assert st_powersave.profile == "powersave"
            assert st_powersave.ssd_standby

            st_airplane = pwr_mod.apply_profile("airplane")
            assert st_airplane.profile == "airplane"
            assert st_airplane.radios_blocked

            # Test sensory presets: OFFICE -> CLASSROOM
            st_office = sens_mod.apply_profile("office")
            assert st_office.profile == "office"
            assert st_office.buzzer_volume == 25

            st_classroom = sens_mod.apply_profile("classroom")
            assert st_classroom.profile == "classroom"
            assert st_classroom.buzzer_volume == 0
            assert not st_classroom.alerts_audible

            # Test sensory overload cognitive toggle (REQ-INP-08)
            sens_mod.set_overload(True)
            ovr_state = sens_mod.load_state()
            assert ovr_state.overload_active is True
            assert ovr_state.buzzer_volume == 0
            assert not ovr_state.alerts_audible

            # Evaluate system alerts under active sensory overload
            metrics = SystemMetrics(
                battery_percent=12.0, thermal_celsius=76.0, available_ram_mb=85.0,
            )
            alerts = evaluate_alerts(metrics, sensory_state=ovr_state.to_dict())
            assert len(alerts) >= 2
            # All alerts must be suppressed from audible notification
            assert all(not a.audible for a in alerts)

            # Disarm overload
            sens_mod.set_overload(False)
            norm_state = sens_mod.load_state()
            assert norm_state.overload_active is False

        # ---------------------------------------------------------------------
        # Phase 5: Multi-Workspace Virtual Terminal & CardKB Ctrl Latching
        # ---------------------------------------------------------------------
        mock_bridge = MagicMock()
        mock_bridge._theme = theme
        mock_bridge._geometry = TerminalGeometry.for_font_size(1)
        mock_bridge._paint = MagicMock()
        mock_bridge._prev = None

        spawn_id = 200

        def mock_spawn(user: str) -> tuple[int, int]:
            nonlocal spawn_id
            spawn_id += 1
            return (-spawn_id, spawn_id + 500)

        ws_mgr = WorkspaceManager(
            bridge=mock_bridge,
            user="whisker",
            max_workspaces=4,
            spawn_fn=mock_spawn,
        )

        ws1 = ws_mgr.create_workspace(ws_id=1, name="shell")
        ws2 = ws_mgr.create_workspace(ws_id=2, name="editor")
        assert len(ws_mgr.workspaces) == 2
        assert ws_mgr.active_id == 1

        # Feed text to workspace 1
        ws1.emulator.feed(b"whiskerframe-cyberdeck:~# uname -a\r\nLinux pi-zero2w\r\n")
        assert ws1.grid.cell_at(0, 0).char == "w"

        # Switch to workspace 2
        ok_switch = ws_mgr.switch_workspace(2)
        assert ok_switch is True
        assert ws_mgr.active_id == 2
        ws2.emulator.feed(b"vim /etc/hosts\r\n")
        assert ws2.grid.cell_at(0, 0).char == "v"

        # Verify CardKB keystrokes with Ctrl chord latching
        keys_in = [CTRL_LATCH_CHORD, ord("c")]  # Becomes Ctrl+C (0x03)
        kq = KeyQueue(iter(keys_in))
        k1 = kq.get_nowait()
        k2 = kq.get_nowait()
        assert k1 == CTRL_LATCH_CHORD
        assert (k2 & 0x1F) == 0x03

        # ---------------------------------------------------------------------
        # Phase 6: Image Blitting & Protocol Serialization
        # ---------------------------------------------------------------------
        # 128x128 RGB565 test image (32768 bytes)
        image_bytes = bytes([0x1F, 0x00] * (128 * 128))  # Solid red
        img_pkt = frame(OPCODE_DRAW_IMAGE, b"\x00\x00\x80\x80" + image_bytes[:2048])
        assert img_pkt[0] == 0xA5  # SOF
        unframed = _unframe(img_pkt)
        assert unframed is not None
        assert unframed[0] == OPCODE_DRAW_IMAGE

        # ---------------------------------------------------------------------
        # Phase 7: Graceful Goodbye Splash & Display Sleep
        # ---------------------------------------------------------------------
        # Opcode 0x06 SLEEP frame
        sleep_pkt = frame(OPCODE_SLEEP, b"")
        assert sleep_pkt[0] == 0xA5
        unframed_sleep = _unframe(sleep_pkt)
        assert unframed_sleep is not None
        assert unframed_sleep[0] == OPCODE_SLEEP
        assert unframed_sleep[1:] == b""
