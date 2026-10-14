"""
Unit tests for the WhiskerFrame Cyberdeck Wi-Fi helper (pi/bin/wifi).

Validates:
1. Strictly fitting within 53 columns on all formatted lines.
2. nmcli terse output parsing with colon escaping and band detection.
3. SSID deduplication preferring 2.4 GHz and strongest signal.
4. Join target resolution and 5 GHz warnings for Pi Zero 2W.
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
from importlib.machinery import SourceFileLoader
from pathlib import Path

# Load pi/bin/wifi script dynamically (extensionless executable)
WIFI_PATH = Path(__file__).resolve().parent.parent / "pi" / "bin" / "wifi"
loader = SourceFileLoader("wifi", str(WIFI_PATH))
spec = importlib.util.spec_from_loader("wifi", loader)
if spec is None or spec.loader is None:
    msg = f"Cannot load wifi script from {WIFI_PATH}"
    raise ImportError(msg)
wifi = importlib.util.module_from_spec(spec)
loader.exec_module(wifi)


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        print(f"FAIL: {msg}")
        sys.exit(1)


# Mock nmcli scan output containing:
# - Multiple BSSIDs for "Home-WiFi" (one 2.4GHz at 70%, one 5GHz at 95%)
# - Multiple BSSIDs for "CoffeeShop" (both 2.4GHz, signals 65% and 80%)
# - Long SSID name exceeding 25 characters
# - Hidden network (empty SSID)
# - Escaped colons in BSSID and SSID
# - 5GHz-only network
# - More than 10 networks to verify top-10 truncation
MOCK_NMCLI_SCAN = r"""
AA\:BB\:CC\:11\:22\:33:Home-WiFi:70:WPA2:2412 MHz
AA\:BB\:CC\:11\:22\:34:Home-WiFi:95:WPA2:5180 MHz
BB\:CC\:DD\:22\:33\:44:CoffeeShop:65:WPA1 WPA2:2437 MHz
BB\:CC\:DD\:22\:33\:45:CoffeeShop:80:WPA1 WPA2:2437 MHz
CC\:DD\:EE\:33\:44\:55:ExtremelyLongNetworkSSIDNameThatWillExceedFiftyThreeCols:88:WPA2 WPA3 802.1X:2462 MHz
DD\:EE\:FF\:44\:55\:66::40:WPA2:2412 MHz
EE\:FF\:00\:55\:66\:77:--:35:OPEN:2412 MHz
11\:22\:33\:66\:77\:88:Colon\:Shop\:Special:60:WPA2:2437 MHz
22\:33\:44\:77\:88\:99:FiveG-FastOnly:85:WPA3:5240 MHz
33\:44\:55\:88\:99\:00:OpenNet:90:--:2412 MHz
44\:55\:66\:99\:00\:11:NetFour:55:WPA2:2412 MHz
55\:66\:77\:00\:11\:22:NetFive:50:WPA2:2412 MHz
66\:77\:88\:11\:22\:33:NetSix:45:WPA2:2412 MHz
77\:88\:99\:22\:33\:44:NetSeven:40:WPA2:2412 MHz
88\:99\:00\:33\:44\:55:NetEight:35:WPA2:2412 MHz
99\:00\:11\:44\:55\:66:NetNine:30:WPA2:2412 MHz
"""


def check_nmcli_terse_split() -> None:
    """Verify split_nmcli_terse handles escaped colons and backslashes."""
    line = r"AA\:BB\:CC\:11\:22\:33:My\:Custom\:SSID:85:WPA2:2412 MHz"
    fields = wifi.split_nmcli_terse(line)
    _assert(len(fields) == 5, f"Expected 5 fields, got {len(fields)}")
    _assert(fields[0] == "AA:BB:CC:11:22:33", f"BSSID unescape failed: {fields[0]}")
    _assert(fields[1] == "My:Custom:SSID", f"SSID unescape failed: {fields[1]}")
    _assert(fields[2] == "85", f"Signal mismatch: {fields[2]}")
    _assert(fields[4] == "2412 MHz", f"Freq mismatch: {fields[4]}")


def check_band_and_freq_detection() -> None:
    """Verify frequency parsing and 2.4 GHz vs 5 GHz categorization."""
    _assert(wifi.parse_freq_mhz("2412 MHz") == 2412, "Parse 2412 MHz")
    _assert(wifi.parse_freq_mhz("5180 MHz") == 5180, "Parse 5180 MHz")
    _assert(wifi.parse_freq_mhz("2462") == 2462, "Parse 2462 without MHz")
    _assert(wifi.parse_freq_mhz("") == 0, "Parse empty freq")

    _assert(not wifi.is_5ghz_freq(2412), "2412 is 2.4 GHz")
    _assert(not wifi.is_5ghz_freq(2462), "2462 is 2.4 GHz")
    _assert(not wifi.is_5ghz_freq(2484), "2484 is 2.4 GHz (Ch 14)")
    _assert(wifi.is_5ghz_freq(5180), "5180 is 5 GHz")
    _assert(wifi.is_5ghz_freq(5745), "5745 is 5 GHz")
    _assert(wifi.is_5ghz_freq(6000), "6000 is 6 GHz (non-2.4 GHz)")


def check_scan_parsing_and_deduplication() -> None:
    """Verify deduplication, sorting, 5 GHz detection, and top 10 limit."""
    nets, has_5g = wifi.parse_nmcli_scan(MOCK_NMCLI_SCAN)

    _assert(has_5g, "Must detect 5 GHz networks in raw scan")
    _assert(len(nets) <= 10, f"Must return at most 10 networks, got {len(nets)}")

    # Check deduplication for Home-WiFi:
    # 2.4GHz at 70% vs 5GHz at 95% -> must PREFER 2.4 GHz for Pi Zero 2W compatibility
    home_wifi = next((n for n in nets if n["ssid"] == "Home-WiFi"), None)
    _assert(home_wifi is not None, "Home-WiFi must be present")
    _assert(
        home_wifi["signal"] == 70,
        f"Expected 2.4GHz signal (70), got {home_wifi['signal']}",
    )
    _assert(not home_wifi["is_5ghz"], "Home-WiFi must pick 2.4 GHz AP over 5 GHz AP")

    # Check CoffeeShop deduplication: two 2.4 GHz APs (65% vs 80%) -> keeps 80%
    coffee = next((n for n in nets if n["ssid"] == "CoffeeShop"), None)
    _assert(coffee is not None, "CoffeeShop must be present")
    _assert(
        coffee["signal"] == 80,
        f"Expected highest signal (80), got {coffee['signal']}",
    )

    # Check 5G-only network: FiveG-FastOnly must be flagged is_5ghz
    five_g = next((n for n in nets if n["ssid"] == "FiveG-FastOnly"), None)
    _assert(five_g is not None, "FiveG-FastOnly must be present")
    _assert(five_g["is_5ghz"], "FiveG-FastOnly must be flagged as 5 GHz")

    # Check that empty and '--' SSIDs were filtered
    _assert(
        all(n["ssid"] not in ("", "--") for n in nets),
        "Hidden networks filtered from list",
    )

    # Check sorting order: signals must be monotonically non-increasing
    signals = [n["signal"] for n in nets]
    _assert(
        signals == sorted(signals, reverse=True),
        "Networks must be sorted by signal descending",
    )

    # Check 1-based indexing
    for i, n in enumerate(nets, 1):
        _assert(n["index"] == i, f"Index must be {i}, got {n['index']}")


def check_column_fitting_scan_table() -> None:
    """Verify that every formatted line in scan table strictly fits <= 53 columns."""
    nets, has_5g = wifi.parse_nmcli_scan(MOCK_NMCLI_SCAN)
    lines = wifi.format_scan_table(nets, has_5ghz=has_5g)

    _assert(len(lines) > 0, "Scan table produced lines")
    for i, line in enumerate(lines):
        _assert(
            len(line) <= 53,
            f"Line {i} exceeds 53 columns ({len(line)} chars): {line!r}",
        )

    # Also test empty scan results
    empty_lines = wifi.format_scan_table([], has_5ghz=False)
    for i, line in enumerate(empty_lines):
        _assert(
            len(line) <= 53,
            f"Empty line {i} exceeds 53 columns ({len(line)} chars): {line!r}",
        )


def check_column_fitting_status() -> None:
    """Verify status formatting with long active SSIDs, multiple IPs, and saved nets."""
    dev_status = (
        "wlan0:wifi:connected:SuperLongActiveConnectionNameToTestColumnFittingBoundary\n"
        "eth0:ethernet:unavailable:--\n"
    )
    dev_show = "IP4.ADDRESS[1]:192.168.100.254/24\n" "IP4.ADDRESS[2]:10.0.0.123/24\n"
    wifi_list = "*:SuperLongActiveConnectionNameToTestColumnFittingBoundary:92:WPA2 802.1X:2412 MHz\n"
    conn_show = (
        "SuperLongActiveConnectionNameToTestColumnFittingBoundary:wifi:wlan0\n"
        "AnotherSavedNetworkWithLongName:802-11-wireless:--\n"
        "ThirdSavedNetwork:wifi:--\n"
    )

    data = wifi.parse_status_data(
        dev_status_out=dev_status,
        dev_show_out=dev_show,
        wifi_list_out=wifi_list,
        conn_show_out=conn_show,
    )
    lines = wifi.format_status(data)

    _assert(len(lines) > 0, "Status produced lines")
    for i, line in enumerate(lines):
        _assert(
            len(line) <= 53,
            f"Status line {i} exceeds 53 columns ({len(line)} chars): {line!r}",
        )


def check_column_fitting_text_wrapper() -> None:
    """Verify wrap_text guarantees all lines <= 53 columns."""
    long_text = (
        "This is a very long error message returned from nmcli connection up id MySSID "
        "stating that secrets were required but not provided or 802.1X authentication failed."
    )
    wrapped = wifi.wrap_text(long_text, width=53)
    for i, line in enumerate(wrapped):
        _assert(
            len(line) <= 53,
            f"Wrapped line {i} exceeds 53 columns ({len(line)} chars): {line!r}",
        )


def check_join_target_resolution() -> None:
    """Verify index mapping from cache and fallback behavior."""
    with tempfile.NamedTemporaryFile("w+", delete=False) as tf:
        cache_file = tf.name

    try:
        nets, _ = wifi.parse_nmcli_scan(MOCK_NMCLI_SCAN)
        wifi.save_scan_cache(nets, path=cache_file)

        # Resolve index 1
        net1, err1 = wifi.resolve_join_target("1", cache_path=cache_file)
        _assert(err1 is None, f"Index 1 resolution error: {err1}")
        _assert(
            net1 is not None and net1.get("index") == 1,
            "Index 1 resolution failed",
        )

        # Resolve index 2
        net2, err2 = wifi.resolve_join_target("2", cache_path=cache_file)
        _assert(err2 is None, f"Index 2 resolution error: {err2}")
        _assert(
            net2 is not None and net2.get("index") == 2,
            "Index 2 resolution failed",
        )

        # Resolve out of bounds index (e.g. 99)
        net99, err99 = wifi.resolve_join_target("99", cache_path=cache_file)
        _assert(net99 is None, "Index 99 should return None")
        _assert(
            "not in scan" in str(err99),
            f"Expected out of bounds error, got: {err99}",
        )

        # Resolve direct SSID string
        net_ssid, err_ssid = wifi.resolve_join_target(
            "CoffeeShop",
            cache_path=cache_file,
        )
        _assert(err_ssid is None, f"SSID resolution error: {err_ssid}")
        _assert(
            net_ssid is not None and net_ssid.get("ssid") == "CoffeeShop",
            "SSID lookup failed",
        )

        # Resolve unseen SSID string
        net_new, err_new = wifi.resolve_join_target(
            "BrandNewSSID",
            cache_path=cache_file,
        )
        _assert(err_new is None, f"New SSID error: {err_new}")
        _assert(
            net_new is not None and net_new.get("ssid") == "BrandNewSSID",
            "New SSID failed",
        )

    finally:
        Path(cache_file).unlink(missing_ok=True)
        Path(f"{cache_file}.tmp").unlink(missing_ok=True)


def check_cache_save_and_load() -> None:
    """Verify save_scan_cache and load_scan_cache roundtrip."""
    with tempfile.NamedTemporaryFile("w+", delete=False) as tf:
        cache_file = tf.name

    try:
        test_data = [
            {
                "index": 1,
                "ssid": "TestNet",
                "signal": 90,
                "security": "WPA2",
                "is_5ghz": False,
            },
        ]
        wifi.save_scan_cache(test_data, path=cache_file)
        loaded = wifi.load_scan_cache(path=cache_file)
        _assert(len(loaded) == 1, f"Expected 1 item, got {len(loaded)}")
        _assert(loaded[0]["ssid"] == "TestNet", "SSID mismatch")
        _assert(loaded[0]["signal"] == 90, "Signal mismatch")
    finally:
        Path(cache_file).unlink(missing_ok=True)
        Path(f"{cache_file}.tmp").unlink(missing_ok=True)


def main() -> None:
    check_nmcli_terse_split()
    check_band_and_freq_detection()
    check_scan_parsing_and_deduplication()
    check_column_fitting_scan_table()
    check_column_fitting_status()
    check_column_fitting_text_wrapper()
    check_join_target_resolution()
    check_cache_save_and_load()
    print("PASS")


if __name__ == "__main__":
    main()
