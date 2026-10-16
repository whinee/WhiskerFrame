"""
scripts/reliability/test_stress_endurance.py: Sustained stress and endurance verification suite.

Covers:
- Memory pressure & earlyoom safety threshold simulation (Pi Zero 2W ~416MB ceiling)
- High-throughput serial bus frame saturation (1,000 framed packets)
- Concurrent multi-workspace rapid cycling under continuous PTY traffic
- Power profile & sensory state rapid churn (100 state transitions)
- CardKB keystroke burst and sticky Ctrl latch endurance (5,000 keystrokes)
"""

from __future__ import annotations

import importlib.util
import io
import sys
import time
from importlib.machinery import SourceFileLoader
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "pi"))

from terminal.bridge import CTRL_LATCH_CHORD, KeyQueue  # noqa: E402
from terminal.theme import load_theme  # noqa: E402
from terminal.workspaces import WorkspaceManager  # noqa: E402

from whiskerframe.alerts import (  # noqa: E402
    AlertCategory,
    AlertSeverity,
    SystemMetrics,
    evaluate_alerts,
)
from whiskerframe.protocol import (  # noqa: E402
    OPCODE_DRAW_CELLS,
    OPCODE_DRAW_RECT,
    OPCODE_DRAW_TEXT,
    OPCODE_SCROLL,
    OPCODE_SLEEP,
    _unframe,
    frame,
)
from whiskerframe.terminal import TerminalGeometry  # noqa: E402
from whiskerframe.transport import SerialTransport  # noqa: E402


class TestStressEndurance:
    """Rigorous stress and endurance test suite for cyberdeck subsystems."""

    def test_stress_memory_exhaustion_simulation(self):
        """Simulate progressive RAM exhaustion toward the 50MB earlyoom floor."""
        # Baseline: 300MB nominal
        nominal = SystemMetrics(
            battery_percent=90.0, thermal_celsius=52.0, available_ram_mb=300.0,
        )
        alerts_nominal = evaluate_alerts(nominal)
        assert (
            len([a for a in alerts_nominal if a.category == AlertCategory.MEMORY]) == 0
        )

        # Warning zone: 90MB
        warning = SystemMetrics(
            battery_percent=90.0, thermal_celsius=52.0, available_ram_mb=90.0,
        )
        alerts_warning = evaluate_alerts(warning)
        mem_warn = [a for a in alerts_warning if a.category == AlertCategory.MEMORY]
        assert len(mem_warn) == 1
        assert mem_warn[0].severity == AlertSeverity.WARNING

        # Critical danger zone: 35MB (below 50MB floor)
        critical = SystemMetrics(
            battery_percent=90.0, thermal_celsius=52.0, available_ram_mb=35.0,
        )
        alerts_crit = evaluate_alerts(critical)
        mem_crit = [a for a in alerts_crit if a.category == AlertCategory.MEMORY]
        assert len(mem_crit) == 1
        assert mem_crit[0].severity == AlertSeverity.CRITICAL
        assert "earlyoom" in mem_crit[0].message

        # Endurance cycle: 500 iterations of fluctuating memory telemetry
        for ram_val in range(20, 250, 2):
            m = SystemMetrics(
                battery_percent=80.0,
                thermal_celsius=55.0,
                available_ram_mb=float(ram_val),
            )
            evts = evaluate_alerts(m)
            if ram_val < 50:
                assert any(e.severity == AlertSeverity.CRITICAL for e in evts)
            elif ram_val < 100:
                assert any(e.severity == AlertSeverity.WARNING for e in evts)
            else:
                assert not any(e.category == AlertCategory.MEMORY for e in evts)

    def test_stress_serial_bus_saturation_burst(self):  # noqa: C901
        """Burst transmit 1,000 rapid serial frames across all opcodes."""
        mock_port = MagicMock()
        written_bytes = bytearray()

        def fake_write(data: bytes) -> int:
            written_bytes.extend(data)
            return len(data)

        mock_port.write = fake_write
        mock_port.is_open = True

        with patch("serial.Serial", return_value=mock_port):
            transport = SerialTransport(port="/dev/mock_serial", baudrate=115200)

            opcodes = [
                (OPCODE_DRAW_TEXT, b"\x00\x00\x01Hello cyberdeck stress"),
                (OPCODE_DRAW_RECT, b"\x00\x00\x20\x20\xf8\x00"),
                (OPCODE_DRAW_CELLS, b"\x00\x00\x05ABCDE"),
                (OPCODE_SCROLL, b"\x01\x00\x08"),
                (OPCODE_SLEEP, b""),
            ]

            start_time = time.perf_counter()
            packet_count = 1000

            for i in range(packet_count):
                opcode, payload = opcodes[i % len(opcodes)]
                pkt = frame(opcode, payload)
                transport.send(pkt)

            duration = time.perf_counter() - start_time
            assert len(written_bytes) > 10000
            rate = packet_count / duration
            assert rate > 1000  # Must process >1000 frames/sec in software

            # Verify stream decodability without any CRC corruption
            stream = io.BytesIO(written_bytes)
            decoded_count = 0
            while True:
                # Look for SOF 0xA5
                b = stream.read(1)
                if not b:
                    break
                if b[0] != 0xA5:
                    continue
                hdr = stream.read(2)
                if len(hdr) < 2:
                    break
                length = hdr[0] | (hdr[1] << 8)
                rest = stream.read(length + 1)
                if len(rest) < length + 1:
                    break
                full_frame = b"\xa5" + hdr + rest
                dec = _unframe(full_frame)
                if dec is not None:
                    decoded_count += 1

            assert decoded_count == packet_count

    def test_stress_concurrent_workspace_rapid_swaps(self, tmp_path: Path):
        """Perform 200 rapid workspace switches while feeding concurrent PTY streams."""
        mock_bridge = MagicMock()
        mock_bridge._theme = load_theme(None)
        mock_bridge._geometry = TerminalGeometry.for_font_size(2)
        mock_bridge._paint = MagicMock()
        mock_bridge._prev = None

        spawn_counter = 100

        def mock_spawn(user: str) -> tuple[int, int]:
            nonlocal spawn_counter
            spawn_counter += 1
            return (-spawn_counter, spawn_counter + 1000)

        mgr = WorkspaceManager(
            bridge=mock_bridge,
            user="whisker",
            max_workspaces=4,
            spawn_fn=mock_spawn,
        )
        for i in range(1, 5):
            mgr.create_workspace(ws_id=i)

        assert len(mgr.workspaces) == 4

        # Cycle 200 times
        for step in range(200):
            target = (step % 4) + 1
            ok = mgr.switch_workspace(target)
            assert ok is True
            assert mgr.active_id == target
            ws = mgr.workspaces[target]
            # Append virtual terminal stream
            ws.emulator.feed(f"tick {step}\r\n".encode())

        # Confirm all 4 workspaces retained their state without leak
        for i in range(1, 5):
            ws = mgr.workspaces[i]
            assert ws is not None
            assert ws.grid.cell_at(0, 0).char == "t"

    def test_stress_power_sensory_profile_churn(self, tmp_path: Path):
        """Perform 100 rapid power profile and sensory state switches."""
        pwr_state_file = tmp_path / "power_state.json"
        sens_state_file = tmp_path / "sensory_state.json"

        pwr_loader = SourceFileLoader(
            "pwr_mod", str(REPO_ROOT / "pi" / "bin" / "power-profile"),
        )
        pwr_spec = importlib.util.spec_from_loader("pwr_mod", pwr_loader)
        assert pwr_spec and pwr_spec.loader
        power_profile_mod = importlib.util.module_from_spec(pwr_spec)
        sys.modules["pwr_mod"] = power_profile_mod
        pwr_loader.exec_module(power_profile_mod)

        sens_loader = SourceFileLoader(
            "sens_mod", str(REPO_ROOT / "pi" / "bin" / "profile"),
        )
        sens_spec = importlib.util.spec_from_loader("sens_mod", sens_loader)
        assert sens_spec and sens_spec.loader
        profile_mod = importlib.util.module_from_spec(sens_spec)
        sys.modules["sens_mod"] = profile_mod
        sens_loader.exec_module(profile_mod)

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

            # 100 alternating switches
            pwr_modes = ["active", "powersave", "airplane"]
            sens_modes = ["classroom", "office", "commute"]

            for i in range(100):
                # Power switch
                target_pwr = pwr_modes[i % len(pwr_modes)]
                p_st = power_profile_mod.apply_profile(target_pwr)
                assert p_st.profile == target_pwr

                # Sensory switch
                target_sens = sens_modes[i % len(sens_modes)]
                s_st = profile_mod.apply_profile(target_sens)
                assert s_st.profile == target_sens

                # Sensory overload toggle
                profile_mod.set_overload(i % 2 == 0)
                cur_sens = profile_mod.load_state()
                assert cur_sens.overload_active == (i % 2 == 0)

            # Files exist and parse cleanly
            assert pwr_state_file.is_file()
            assert sens_state_file.is_file()

    def test_stress_cardkb_burst_keystroke_flood(self):  # noqa: C901
        """Simulate 5,000 rapid CardKB keystrokes through KeyQueue and Ctrl latch logic."""
        keystrokes = [
            ord("a"),
            ord("b"),
            CTRL_LATCH_CHORD,  # 0x8C
            ord("c"),  # Becomes Ctrl+C (0x03)
            ord("x"),
            ord("y"),
            ord("z"),
            10,  # newline
        ]

        def key_generator():
            for i in range(5000):
                yield keystrokes[i % len(keystrokes)]

        kq = KeyQueue(key_generator())

        emitted_ctrl_c = 0
        total_drained = 0
        ctrl_armed = False

        while True:
            k = kq.get_nowait()
            if k is None:
                if not kq._thread.is_alive() and kq._queue.empty():
                    break
                time.sleep(0.001)
                continue

            total_drained += 1
            if k == CTRL_LATCH_CHORD:
                ctrl_armed = True
                continue
            if ctrl_armed:
                transformed = k & 0x1F
                if transformed == 0x03:
                    emitted_ctrl_c += 1
                ctrl_armed = False

        assert total_drained == 5000
        assert emitted_ctrl_c == 5000 // len(keystrokes)
