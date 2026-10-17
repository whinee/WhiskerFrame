#!/usr/bin/env python3
r"""
Desktop screen mirror and keyboard input bridge for the WhiskerFrame Cyberdeck.

Connects to the cyberdeck via live SSH socket stream or serial (or runs in explicit
mock mode when --mock is passed) to mirror the 320x240 display live using
`whiskerframe.protocol.decode` and `whiskerframe.preview.PreviewRenderer`, while
capturing local window keystrokes and forwarding them to the cyberdeck input bridge.
Never silently falls back to mock mode on connection failure; connection status and
automatic reconnection attempts are explicitly surfaced.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
import tkinter as tk
from tkinter import messagebox

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "pi"))

from whiskerframe.preview import PreviewRenderer
from whiskerframe.protocol import decode, SOF
from whiskerframe.builder import CommandBuilder
from whiskerframe.coordinates import XYWH
from whiskerframe.terminal import DrawCells, Scroll, DrawImage

try:
    from PIL import Image, ImageTk
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


class DesktopMirrorApp:
    def __init__(
        self,
        root: tk.Tk,
        port: str = "/dev/ttyUSB0",
        baud: int = 115200,
        scale: int = 2,
        mock: bool = False,
        host: str = "",
        user: str = "root",
        key: str = "",
        socket_path: str = "/tmp/whiskerframe_mirror.sock",
    ) -> None:
        self.root = root
        self.mock = mock
        if self.mock:
            self.root.title("WhiskerFrame Cyberdeck Desktop Mirror — EXPLICIT MOCK / DEMO MODE")
        else:
            self.root.title("WhiskerFrame Cyberdeck Desktop Mirror & Input Bridge")

        self.port = port
        self.baud = baud
        self.scale = max(1, scale)
        self.host = host
        self.user = user
        self.key = key
        self.socket_path = socket_path

        self.width = 320
        self.height = 240
        self.scaled_width = self.width * self.scale
        self.scaled_height = self.height * self.scale

        self.renderer = PreviewRenderer(width=self.width, height=self.height)
        self.commands = []
        self.preview_image = self.renderer.render([])
        self.serial_conn = None
        self.ssh_proc = None
        self.running = True
        self.last_key_time = 0.0

        # Initialize UI widgets
        self.canvas = tk.Canvas(root, width=self.scaled_width, height=self.scaled_height, bg="#191a28")
        self.canvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        if self.mock:
            initial_status = "Status: EXPLICIT MOCK MODE [Demo Art Active - No Hardware Connected]"
        elif self.host:
            initial_status = f"Status: Connecting to LIVE DEVICE via SSH ({self.host})..."
        else:
            initial_status = f"Status: Connecting to SERIAL DEVICE ({self.port})..."

        self.status_var = tk.StringVar(value=initial_status)
        self.status_bar = tk.Label(root, textvariable=self.status_var, bd=1, relief=tk.SUNKEN, anchor=tk.W, fg="#fd7da6" if self.mock else "#ffffff", bg="#191a28")
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        # Bind keyboard events (KeyPress only to prevent duplicate/release events)
        self.root.bind("<KeyPress>", self.on_key_press)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # Initial demo render or screen
        self.render_demo_screen()

        # Start background worker for live SSH stream, serial, or explicit mock loop
        self.thread = threading.Thread(target=self.worker_loop, daemon=True)
        self.thread.start()

    def render_demo_screen(self) -> None:
        builder = CommandBuilder()
        screen = XYWH(0, 0, self.width, self.height)
        box = XYWH(10, 10, self.width - 20, self.height - 20)

        mode_str = "EXPLICIT MOCK MODE" if self.mock else ("LIVE SSH DEVICE" if self.host else "SERIAL DEVICE")
        c1 = builder.draw_rect(screen, color=0x18C5, filled=True)
        c2 = builder.draw_rect(box, color=0x50DC, filled=False)
        c3 = builder.draw_text(
            screen,
            text=f"WHISKERFRAME CYBERDECK\nDesktop Mirror [{mode_str}]\nTracking physical device output\nPress keys to test bridge",
            anchor="mt",
            multiline=True,
        )
        self.commands = [c1, c2, c3]
        self.preview_image = self.renderer.render(self.commands)
        self.update_display()

    def update_display(self) -> None:
        try:
            pil_img = self.preview_image
            if self.scale > 1:
                pil_img = pil_img.resize((self.scaled_width, self.scaled_height), Image.Resampling.NEAREST)
            if HAS_PIL:
                self.tk_img = ImageTk.PhotoImage(pil_img)
                self.canvas.create_image(0, 0, anchor=tk.NW, image=self.tk_img)
        except Exception as e:
            print(f"Render error: {e}", file=sys.stderr)

    def worker_loop(self) -> None:
        if self.mock:
            while self.running:
                time.sleep(1.0)
            return

        backoff = 0.5
        while self.running:
            if self.host:
                # Live SSH Stream Mode via UNIX domain socket mirror
                ssh_cmd = [
                    "ssh",
                    "-i", self.key,
                    "-o", "BatchMode=yes",
                    "-o", "ConnectTimeout=5",
                    f"{self.user}@{self.host}",
                    f"python3 -c 'import socket, sys; s=socket.socket(socket.AF_UNIX, socket.SOCK_STREAM); s.connect(\"{self.socket_path}\"); f=s.makefile(\"rb\"); [sys.stdout.buffer.write(chunk) for chunk in iter(lambda: f.read(4096), b\"\")]'"
                ]
                try:
                    self.ssh_proc = subprocess.Popen(ssh_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    self.root.after(0, lambda: self.status_var.set(f"Status: LIVE DEVICE [CONNECTED] ({self.host})"))
                    backoff = 0.5
                except Exception as e:
                    err_msg = str(e)
                    self.root.after(0, lambda msg=err_msg: self.status_var.set(f"Status: SSH connection error ({msg}). Retrying in {backoff}s... [NO SILENT FALLBACK]"))
                    time.sleep(backoff)
                    backoff = min(5.0, backoff * 2)
                    continue

                buffer = bytearray()
                while self.running and self.ssh_proc.poll() is None:
                    try:
                        data = self.ssh_proc.stdout.read(4096)
                        if data:
                            buffer.extend(data)
                            while len(buffer) > 4:
                                if buffer[0] != SOF:
                                    buffer.pop(0)
                                    continue
                                length = buffer[1] | (buffer[2] << 8)
                                total_len = 3 + length + 1
                                if len(buffer) < total_len:
                                    break
                                frame_bytes = bytes(buffer[:total_len])
                                del buffer[:total_len]
                                try:
                                    cmd = decode(frame_bytes)
                                    self.commands.append(cmd)
                                    if len(self.commands) > 500:
                                        self.commands.pop(0)
                                    self.renderer.draw_command(self.preview_image, cmd)
                                    self.root.after(0, self.update_display)
                                except Exception as ex:
                                    print(f"Frame decode error: {ex}", file=sys.stderr)
                        else:
                            time.sleep(0.1)
                    except Exception as ex:
                        print(f"Live stream read error: {ex}", file=sys.stderr)
                        break

                if self.ssh_proc:
                    try:
                        self.ssh_proc.terminate()
                    except Exception:
                        pass
                    self.ssh_proc = None
                self.root.after(0, lambda: self.status_var.set(f"Status: LIVE DEVICE [DISCONNECTED]. Reconnecting..."))
                time.sleep(1.0)

            else:
                # Serial Mode
                try:
                    import serial
                    self.serial_conn = serial.Serial(self.port, self.baud, timeout=0.1)
                    self.root.after(0, lambda: self.status_var.set(f"Status: SERIAL MODE [CONNECTED] @ {self.port}"))
                    backoff = 0.5
                except Exception as e:
                    err_msg = str(e)
                    self.root.after(0, lambda msg=err_msg: self.status_var.set(f"Status: Serial error ({msg}). Retrying in {backoff}s... [NO SILENT FALLBACK]"))
                    time.sleep(backoff)
                    backoff = min(5.0, backoff * 2)
                    continue

                buffer = bytearray()
                while self.running and self.serial_conn:
                    try:
                        data = self.serial_conn.read(256)
                        if data:
                            buffer.extend(data)
                            while len(buffer) > 4:
                                if buffer[0] != SOF:
                                    buffer.pop(0)
                                    continue
                                length = buffer[1] | (buffer[2] << 8)
                                total_len = 3 + length + 1
                                if len(buffer) < total_len:
                                    break
                                frame_bytes = bytes(buffer[:total_len])
                                del buffer[:total_len]
                                try:
                                    cmd = decode(frame_bytes)
                                    self.commands.append(cmd)
                                    if len(self.commands) > 500:
                                        self.commands.pop(0)
                                    self.renderer.draw_command(self.preview_image, cmd)
                                    self.root.after(0, self.update_display)
                                except Exception as ex:
                                    print(f"Frame decode error: {ex}", file=sys.stderr)
                        else:
                            time.sleep(0.05)
                    except Exception as ex:
                        print(f"Serial read error: {ex}", file=sys.stderr)
                        break

                if self.serial_conn:
                    try:
                        self.serial_conn.close()
                    except Exception:
                        pass
                    self.serial_conn = None
                self.root.after(0, lambda: self.status_var.set(f"Status: SERIAL [DISCONNECTED]. Reconnecting..."))
                time.sleep(1.0)

    def on_key_press(self, event: tk.Event) -> None:
        # Debounce rapid duplicate key events (within 30ms)
        now = time.time()
        if now - self.last_key_time < 0.03:
            return
        self.last_key_time = now

        key_char = event.char
        keysym = event.keysym
        print(f"Key pressed: {keysym!r} (char: {key_char!r})")

        payload = None
        if keysym in ("Shift_L", "Shift_R", "Control_L", "Control_R", "Alt_L", "Alt_R", "Caps_Lock", "Super_L", "Super_R", "Meta_L", "Meta_R"):
            payload = None
        elif keysym == "Return" or keysym == "KP_Enter":
            payload = b"\r"
        elif keysym == "BackSpace":
            payload = b"\x7f"
        elif keysym == "Tab":
            payload = b"\t"
        elif keysym == "Escape":
            payload = b"\x1b"
        elif keysym == "Up":
            payload = b"\x1b[A"
        elif keysym == "Down":
            payload = b"\x1b[B"
        elif keysym == "Right":
            payload = b"\x1b[C"
        elif keysym == "Left":
            payload = b"\x1b[D"
        elif key_char and ord(key_char) >= 32:
            payload = key_char.encode("utf-8")
        elif keysym and len(keysym) == 1:
            payload = keysym.encode("utf-8")

        if payload:
            if self.serial_conn and not self.mock:
                try:
                    self.serial_conn.write(payload)
                    self.status_var.set(f"Status: Key {keysym!r} [SERIAL ACK]")
                except Exception as e:
                    self.status_var.set(f"Status: Serial write error ({e})")
            elif self.host and not self.mock:
                try:
                    payload_hex = payload.hex()
                    remote_script = (
                        "import socket, json\n"
                        "paths = ['/run/whiskerframe/workspaces.sock', '/tmp/whiskerframe_workspaces.sock']\n"
                        "s = None\n"
                        "for p in paths:\n"
                        "    try:\n"
                        "        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)\n"
                        "        s.connect(p)\n"
                        "        break\n"
                        "    except Exception:\n"
                        "        s = None\n"
                        "if s:\n"
                        f"    s.sendall(json.dumps({{\"cmd\": \"input\", \"hex\": {payload_hex!r}}}).encode() + b'\\n')\n"
                        "    s.settimeout(1.0)\n"
                        "    res = s.recv(4096).decode()\n"
                        "    print(res)\n"
                        "    s.close()\n"
                        "else:\n"
                        "    print(json.dumps({'ok': False, 'error': 'socket not found'}))\n"
                    )
                    ssh_cmd = [
                        "ssh",
                        "-i", self.key,
                        "-o", "BatchMode=yes",
                        "-o", "ConnectTimeout=2",
                        f"{self.user}@{self.host}",
                        f"python3 -c {remote_script!r}"
                    ]
                    res = subprocess.run(
                        ssh_cmd,
                        timeout=2.0,
                        capture_output=True,
                        text=True,
                    )
                    out = res.stdout.strip()
                    ack_ok = False
                    err_str = ""
                    for line in out.splitlines():
                        if "{" in line:
                            try:
                                data = json.loads(line)
                                if data.get("ok"):
                                    ack_ok = True
                                else:
                                    err_str = data.get("error", "unknown error")
                            except Exception:
                                pass
                    if ack_ok:
                        self.status_var.set(f"Status: Key {keysym!r} [REMOTE ACK]")
                    else:
                        self.status_var.set(f"Status: Input error ({err_str or out or 'no response'})")
                except Exception as e:
                    self.status_var.set(f"Status: SSH input forwarding error ({e})")
            else:
                self.status_var.set(f"Last Key: {keysym} ({repr(key_char)}) [LOCAL LOG ONLY]")
        else:
            self.status_var.set(f"Last Key: {keysym} (modifier / ignored)")

    def on_close(self) -> None:
        self.running = False
        if self.serial_conn:
            try:
                self.serial_conn.close()
            except Exception:
                pass
        if self.ssh_proc:
            try:
                self.ssh_proc.terminate()
                self.ssh_proc.wait(timeout=1.0)
            except Exception:
                pass
        self.root.destroy()


def main() -> int:
    parser = argparse.ArgumentParser(description="WhiskerFrame Desktop Mirror & Input Bridge")
    parser.add_argument("--port", default="/dev/ttyUSB0", help="Serial port to cyberdeck")
    parser.add_argument("--baud", type=int, default=115200, help="Serial baud rate")
    parser.add_argument("--scale", type=int, default=2, help="Display scale factor for preview window")
    parser.add_argument("--mock", action="store_true", help="Run in explicit mock/demo mode without physical device")
    parser.add_argument("--host", default="", help="Remote Pi host (e.g. 10.0.0.212) for live SSH mirror streaming")
    parser.add_argument("--user", default="root", help="SSH user for live mirror")
    parser.add_argument("--key", default=os.path.expanduser("~/.ssh/id_rsa"), help="SSH private key path")
    parser.add_argument("--socket-path", default="/tmp/whiskerframe_mirror.sock", help="Remote mirror socket path on Pi")
    args = parser.parse_args()

    if not HAS_PIL:
        print("Error: Pillow is required for desktop mirror. Install with 'pip install whiskerframe[preview]'", file=sys.stderr)
        return 1

    root = tk.Tk()
    app = DesktopMirrorApp(
        root,
        port=args.port,
        baud=args.baud,
        scale=args.scale,
        mock=args.mock,
        host=args.host,
        user=args.user,
        key=args.key,
        socket_path=args.socket_path,
    )
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
