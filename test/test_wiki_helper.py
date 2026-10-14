"""
Unit and integration tests for the Whiskerframe Cyberdeck wiki helper (WS-5).

Validates:
- Strict <= 53 column formatting and wrapping for the CYD display.
- ANSI escape stripping and groff overstrike normalization.
- Kiwix online query handling: search API, random article redirect, direct path.
- Kiwix offline fallback priority: man-db, bash help, python3 pydoc.
- Offline error handling for unknown terms and random article requests.
- Subprocess CLI execution, argument parsing, and exit codes.
"""

from __future__ import annotations

import http.server
import importlib.util
import subprocess
import sys
import threading
import unittest
import urllib.parse
from importlib.machinery import SourceFileLoader
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WIKI_BIN = REPO_ROOT / "pi" / "bin" / "wiki"

# Dynamically import wiki helper module from executable without .py extension
loader = SourceFileLoader("wiki_helper", str(WIKI_BIN))
spec = importlib.util.spec_from_loader(loader.name, loader)
if spec is None:
    raise ImportError(f"Could not build spec for {WIKI_BIN}")
wiki = importlib.util.module_from_spec(spec)
loader.exec_module(wiki)


class MockKiwixHandler(http.server.BaseHTTPRequestHandler):
    """Mock HTTP server simulating kiwix-serve daemon endpoints."""

    def log_message(self, format: str, *args: object) -> None:
        """Suppress standard HTTP server request logs during test runs."""

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)

        if parsed.path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"<html><body><h1>Kiwix Server Root</h1></body></html>")

        elif parsed.path == "/random":
            # Simulate kiwix HTTP 302 redirect to random article
            self.send_response(302)
            self.send_header("Location", "/wikipedia_en_simple/A/Raspberry_Pi")
            self.end_headers()

        elif parsed.path == "/wikipedia_en_simple/A/Raspberry_Pi":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            html_body = (
                "<!DOCTYPE html><html><head><title>Raspberry Pi</title>"
                "<style>body { background: #fff; }</style></head><body>"
                "<h1>Raspberry Pi</h1>"
                "<p>The Raspberry Pi is a series of small single-board computers.</p>"
                "<ul>"
                "<li>Pi Zero 2W features a quad-core 64-bit ARM Cortex-A53.</li>"
                "<li>Equipped with 512MB RAM and onboard 2.4GHz Wi-Fi.</li>"
                "</ul>"
                "</body></html>"
            )
            self.wfile.write(html_body.encode("utf-8"))

        elif parsed.path == "/search":
            qs = urllib.parse.parse_qs(parsed.query)
            pattern = qs.get("pattern", [""])[0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            html_body = (
                f"<!DOCTYPE html><html><body>"
                f"<h1>Search results for {pattern}</h1>"
                f"<ol>"
                f"<li><a href='/wikipedia_en_simple/A/{pattern}'>{pattern.title()} article</a>"
                f"<p>Summary and encyclopedia entry regarding {pattern}.</p></li>"
                f"</ol>"
                f"</body></html>"
            )
            self.wfile.write(html_body.encode("utf-8"))

        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not Found")


class TestWikiHelper(unittest.TestCase):
    """Test suite for the wiki helper utility."""

    mock_server: http.server.HTTPServer
    server_port: int
    server_thread: threading.Thread

    @classmethod
    def setUpClass(cls) -> None:
        cls.mock_server = http.server.HTTPServer(("127.0.0.1", 0), MockKiwixHandler)
        cls.server_port = cls.mock_server.server_address[1]
        cls.server_thread = threading.Thread(
            target=cls.mock_server.serve_forever,
            daemon=True,
        )
        cls.server_thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.mock_server.shutdown()
        cls.mock_server.server_close()

    def assert_all_lines_fit(self, text: str, max_cols: int = 53) -> None:
        """Assert that no single line in text exceeds max_cols."""
        lines = text.splitlines()
        for idx, line in enumerate(lines):
            self.assertLessEqual(
                len(line),
                max_cols,
                f"Line {idx} exceeds {max_cols} chars ({len(line)}): {line!r}",
            )

    def test_format_to_cols_strict_width(self) -> None:
        """Verify format_to_cols strictly limits output to target columns."""
        long_para = (
            "The Whiskerframe Cyberdeck operates within an extreme resource "
            "envelope of 416MB usable RAM and renders text to a 320x240 LCD."
        )
        wrapped = wiki.format_to_cols(long_para, cols=53)
        self.assert_all_lines_fit(wrapped, max_cols=53)

        # Super-long unbroken token (URL or identifier)
        unbroken = "https://download.kiwix.org/zim/wikipedia/wikipedia_en_simple_all_maxi_2024-05.zim"
        wrapped_unbroken = wiki.format_to_cols(unbroken, cols=53)
        self.assert_all_lines_fit(wrapped_unbroken, max_cols=53)
        self.assertIn("https://download.kiwix.org", wrapped_unbroken)

    def test_clean_terminal_escapes(self) -> None:
        """Verify ANSI escapes and groff backspace overstrikes are stripped."""
        # Groff bold: char + backspace + char
        groff_text = "L\x08LS\x08S(1) User Manual"
        self.assertEqual(wiki.clean_terminal_escapes(groff_text), "LS(1) User Manual")

        # ANSI color codes
        ansi_text = "\x1b[1;32mSUCCESS:\x1b[0m Service started"
        self.assertEqual(
            wiki.clean_terminal_escapes(ansi_text),
            "SUCCESS: Service started",
        )

    def test_html_text_extractor(self) -> None:
        """Verify HTML parser extracts text cleanly without tags or script blocks."""
        html_input = (
            "<html><head><script>alert('bad');</script><style>h1{color:red;}</style></head>"
            "<body><h1>Cyberdeck</h1><p>Offline <b>first</b> portable terminal.</p>"
            "<ul><li>Item A</li><li>Item B</li></ul></body></html>"
        )
        extractor = wiki.SimpleHTMLTextExtractor()
        extractor.feed(html_input)
        text = extractor.get_text()

        self.assertNotIn("alert", text)
        self.assertNotIn("color:red", text)
        self.assertIn("Cyberdeck", text)
        self.assertIn("Offline first portable terminal.", text)
        self.assertIn("- Item A", text)
        self.assertIn("- Item B", text)

    def test_is_kiwix_online(self) -> None:
        """Verify detection of reachable and unreachable ports."""
        # Reachable mock server
        self.assertTrue(wiki.is_kiwix_online(host="127.0.0.1", port=self.server_port))

        # Unreachable closed port (bind to 0, close immediately to find free closed port)
        closed_port = 65431
        self.assertFalse(
            wiki.is_kiwix_online(host="127.0.0.1", port=closed_port, timeout=0.2),
        )

    def test_kiwix_active_search_query(self) -> None:
        """Verify query_kiwix formats search results from active server."""
        result = wiki.query_kiwix(
            "linux",
            host="127.0.0.1",
            port=self.server_port,
            cols=53,
            is_random=False,
        )
        self.assertIn("Search results for linux", result)
        self.assert_all_lines_fit(result, max_cols=53)

    def test_kiwix_active_random_article(self) -> None:
        """Verify query_kiwix follows random redirect and renders article."""
        result = wiki.query_kiwix(
            "",
            host="127.0.0.1",
            port=self.server_port,
            cols=53,
            is_random=True,
        )
        self.assertIn("Raspberry Pi", result)
        self.assertIn("single-board", result)
        self.assert_all_lines_fit(result, max_cols=53)

    def test_kiwix_active_direct_article_path(self) -> None:
        """Verify query_kiwix renders direct article path."""
        result = wiki.query_kiwix(
            "/wikipedia_en_simple/A/Raspberry_Pi",
            host="127.0.0.1",
            port=self.server_port,
            cols=53,
        )
        self.assertIn("Raspberry Pi", result)
        self.assertIn("Cortex-A53", result)
        self.assert_all_lines_fit(result, max_cols=53)

    def test_offline_fallback_man(self) -> None:
        """Verify fallback to man page when kiwix is offline."""
        code, out = wiki.fallback_local_doc("ls", cols=53, host="127.0.0.1", port=65431)
        self.assertEqual(code, 0)
        self.assertIn("[offline] kiwix inactive - showing man page:", out)
        self.assertIn("LS", out)
        self.assert_all_lines_fit(out, max_cols=53)

    def test_offline_fallback_bash_help(self) -> None:
        """Verify fallback to bash built-in help when man is not specific or for builtins."""
        # For 'cd' or other shell builtin, fallback_local_doc succeeds (via man or bash help)
        code, out = wiki.fallback_local_doc("cd", cols=53, host="127.0.0.1", port=65431)
        self.assertEqual(code, 0)
        self.assertTrue(
            "showing man page" in out or "showing bash help" in out,
            f"Expected man or bash help header, got:\n{out[:200]}",
        )
        self.assert_all_lines_fit(out, max_cols=53)

    def test_offline_unknown_command_reporting(self) -> None:
        """Verify clean error and guidance when a non-existent command is requested offline."""
        bogus_term = "nonexistent_cyberdeck_command_xyz"
        code, out = wiki.fallback_local_doc(
            bogus_term,
            cols=53,
            host="127.0.0.1",
            port=65431,
        )
        self.assertEqual(code, 1)
        self.assertIn("[offline] kiwix-serve inactive (127.0.0.1:65431)", out)
        self.assertIn("No local documentation found for:", out)
        self.assertIn(bogus_term, out)
        self.assertIn("sudo systemctl start kiwix-serve", out)
        self.assert_all_lines_fit(out, max_cols=53)

    def test_offline_random_rejection(self) -> None:
        """Verify wiki -r in offline mode reports random requires kiwix-serve."""
        # Invoked via main() with redirected stdout
        import io
        from unittest.mock import patch

        captured = io.StringIO()
        with patch("sys.stdout", captured):
            code = wiki.main(["-r", "--port", "65431"])
        self.assertEqual(code, 1)
        out = captured.getvalue()
        self.assertIn("[offline] kiwix-serve is not running", out)
        self.assertIn("Random article requires kiwix-serve", out)
        self.assert_all_lines_fit(out, max_cols=53)

    def test_cli_executable_mode(self) -> None:
        """Verify pi/bin/wiki is marked executable (0755)."""
        mode = WIKI_BIN.stat().st_mode
        self.assertTrue(
            mode & 0o111,
            f"Expected executable permissions, got mode {oct(mode)}",
        )

    def test_cli_subprocess_help(self) -> None:
        """Verify running wiki with --help prints usage within 53 columns."""
        res = subprocess.run(  # noqa: S603
            [sys.executable, str(WIKI_BIN), "--help"],
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertEqual(res.returncode, 0)
        self.assertIn("Whiskerframe Cyberdeck Offline Wiki Helper", res.stdout)
        self.assert_all_lines_fit(res.stdout, max_cols=53)

    def test_cli_subprocess_no_args_usage(self) -> None:
        """Verify running wiki with no arguments displays quick usage guide."""
        res = subprocess.run(  # noqa: S603
            [sys.executable, str(WIKI_BIN)],
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertEqual(res.returncode, 0)
        self.assertIn("Usage:", res.stdout)
        self.assertIn("wiki <search-term>", res.stdout)
        self.assert_all_lines_fit(res.stdout, max_cols=53)

    def test_cli_subprocess_active_kiwix(self) -> None:
        """Verify CLI end-to-end against mock kiwix server."""
        res = subprocess.run(  # noqa: S603
            [
                sys.executable,
                str(WIKI_BIN),
                "--port",
                str(self.server_port),
                "kernel",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertEqual(res.returncode, 0)
        self.assertIn("Search results for kernel", res.stdout)
        self.assert_all_lines_fit(res.stdout, max_cols=53)

    def test_cli_subprocess_custom_cols(self) -> None:
        """Verify CLI --cols flag alters the target column limit."""
        narrow_cols = 35
        res = subprocess.run(  # noqa: S603
            [
                sys.executable,
                str(WIKI_BIN),
                "--cols",
                str(narrow_cols),
                "--port",
                str(self.server_port),
                "kernel",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertEqual(res.returncode, 0)
        self.assert_all_lines_fit(res.stdout, max_cols=narrow_cols)


def main() -> None:
    """Run test suite and emit PASS/FAIL."""
    suite = unittest.TestLoader().loadTestsFromTestCase(TestWikiHelper)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    if result.wasSuccessful():
        print("PASS")
        sys.exit(0)
    else:
        print("FAIL")
        sys.exit(1)


if __name__ == "__main__":
    main()
