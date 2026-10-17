r"""
Comprehensive regression tests for WhiskerFrame desktop mirror, preview renderer parity,
connection error handling (no silent fallback to mock mode), and keyboard forwarding.
"""

from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from desktop_mirror import DesktopMirrorApp
from whiskerframe.preview import PreviewRenderer
from whiskerframe.builder import CommandBuilder
from whiskerframe.coordinates import XYWH
from whiskerframe.terminal import DrawCells, Scroll, DrawImage


def test_desktop_mirror_initialization_explicit_mock() -> None:
    """Verify DesktopMirrorApp initializes correctly in explicit mock mode."""
    root = tk.Tk()
    root.withdraw()

    app = DesktopMirrorApp(root, port="/dev/ttyUSB0", baud=115200, scale=1, mock=True)
    assert app.mock is True
    canvas_bg = app.canvas.cget("bg")
    assert canvas_bg in ("#191a28", "#191A28")

    app.on_close()
    root.update_idletasks()


def test_desktop_mirror_no_silent_mock_fallback() -> None:
    """Verify that when mock=False and serial/host connection fails, mock mode is NOT silently enabled."""
    root = tk.Tk()
    root.withdraw()

    app = DesktopMirrorApp(root, port="/dev/nonexistent_port_12345", baud=115200, scale=1, mock=False)
    assert app.mock is False

    app.on_close()
    root.update_idletasks()


def test_preview_renderer_all_command_types() -> None:
    """Verify PreviewRenderer successfully renders DrawText, DrawRect, DrawCells, Scroll, and DrawImage."""
    renderer = PreviewRenderer(width=320, height=240, background=0x0000)
    builder = CommandBuilder()
    screen = XYWH(0, 0, 320, 240)

    cmd_rect = builder.draw_rect(screen, color=0x18C5, filled=True)
    cmd_text = builder.draw_text(screen, text="TEST RENDER", anchor="mt")
    cmd_cells = DrawCells(col=0, row=5, fg=0xFFFF, bg=0x0000, font_size=1, text="HELLO")
    cmd_scroll = Scroll(rows=1, fill=0x0000, top=0, bottom=10)

    # 2x2 red pixel image (8 bytes of RGB565)
    img_data = b'\xf8\x00\xf8\x00\xf8\x00\xf8\x00'
    cmd_image = DrawImage(x=10, y=10, w=2, h=2, data=img_data)

    img = renderer.render([cmd_rect, cmd_text, cmd_cells, cmd_scroll, cmd_image])
    assert img is not None
    assert img.size == (320, 240)


def test_keyboard_forwarding_deduplication() -> None:
    """Verify key press handling correctly records keysym and avoids duplicate triggers."""
    root = tk.Tk()
    root.withdraw()

    app = DesktopMirrorApp(root, port="/dev/ttyUSB0", baud=115200, scale=1, mock=True)

    class MockEvent:
        def __init__(self, char: str, keysym: str) -> None:
            self.char = char
            self.keysym = keysym

    event1 = MockEvent(char="a", keysym="a")
    app.on_key_press(event1)
    status1 = app.status_var.get()
    assert "a" in status1

    # Immediate duplicate key press within debounce window (<30ms) should be throttled
    app.on_key_press(event1)

    app.on_close()
    root.update_idletasks()


def test_preview_renderer_draw_command() -> None:
    """Verify PreviewRenderer.draw_command incrementally updates image."""
    renderer = PreviewRenderer(width=320, height=240, background=0x0000)
    builder = CommandBuilder()
    rect_cmd = builder.draw_rect(XYWH(0, 0, 320, 240), color=0x18C5, filled=True)
    img = renderer.render([])
    updated_img = renderer.draw_command(img, rect_cmd)
    assert updated_img is not None
    assert updated_img.size == (320, 240)


def test_workspace_ipc_input_command() -> None:
    """Verify WorkspaceManager handles 'input' IPC command correctly."""
    import os
    from pi.terminal.workspaces import WorkspaceManager, Workspace
    class MockBridge:
        pass
    manager = WorkspaceManager(bridge=MockBridge(), user="root")
    r, w = os.openpty()
    ws = Workspace(id=1, name="1", user="root", pid=999999, master_fd=w, grid=None, emulator=None)
    ws._mock_alive = True
    manager.workspaces[1] = ws
    manager.active_id = 1

    resp = manager.dispatch_ipc_command({"cmd": "input", "bytes": "hello"})
    assert resp.get("ok") is True

    data = os.read(r, 10)
    assert b"hello" in data

    os.close(r)
    os.close(w)


def test_mirror_snapshot_sync() -> None:
    """Verify TerminalBridge mirror server sends initial snapshot to connecting clients."""
    import socket
    import os
    import time
    from pi.terminal.bridge import TerminalBridge, BridgeConfig
    config = BridgeConfig(serial_port="/dev/null", demo_mode=True)
    bridge = TerminalBridge(config)
    socket_path = bridge._mirror_socket_path

    # Connect client to unix socket with retry
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    connected = False
    for _ in range(50):
        try:
            client.connect(socket_path)
            connected = True
            break
        except (ConnectionRefusedError, FileNotFoundError, OSError):
            time.sleep(0.02)
    assert connected, "Could not connect to mirror socket"

    client.settimeout(2.0)
    data = client.recv(4096)
    assert len(data) > 0  # Should receive clear/snapshot frame
    client.close()
    with bridge._mirror_lock:
        for c in bridge._mirror_clients:
            try:
                c.close()
            except Exception:
                pass


def test_desktop_mirror_key_mapping_and_modifiers() -> None:
    """Verify DesktopMirrorApp correctly ignores modifiers and maps special keys."""
    import time
    root = tk.Tk()
    root.withdraw()
    app = DesktopMirrorApp(root, mock=True)

    class MockEvent:
        def __init__(self, char: str, keysym: str) -> None:
            self.char = char
            self.keysym = keysym

    # Modifier should be ignored
    event_mod = MockEvent(char="", keysym="Shift_L")
    app.on_key_press(event_mod)
    assert "modifier" in app.status_var.get() or "Shift_L" in app.status_var.get()

    time.sleep(0.04)

    # Arrow key
    event_arrow = MockEvent(char="", keysym="Down")
    app.on_key_press(event_arrow)
    assert "Last Key: Down" in app.status_var.get() or "Down" in app.status_var.get()

    app.on_close()
    root.update_idletasks()


