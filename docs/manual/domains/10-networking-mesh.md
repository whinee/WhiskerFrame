# Domain 10: Networking, Wi-Fi Persistence & Mesh Overlays (REQ-NET)

**Specification Prefix:** `REQ-NET`  
**System Layer:** Wireless Radios, Wi-Fi Management, Self-Healing Watchdogs & Mesh VPN  
**Primary Implementations:** `pi/bin/wifi`, `ansible/roles/wifi_persistence/`, `ansible/roles/self_heal_watchdog/`, `ansible/roles/netbird/`  
**Acceptance Test Plans:** `ATP-06-NET-WIFI-HELPER`, `ATP-08-NET-SELF-HEAL`  
**Target Milestone:** `v0` (Demo Prototype) / `v1` (Field Hardened)  

---

## 1. Scope & Domain Objectives

The Networking, Wi-Fi Persistence & Mesh Overlays domain defines wireless radio configuration, regulatory domain enforcement, cold-boot Wi-Fi reconnection, 53-column network administration, three-tier self-healing network recovery, captive portal handling, and peer-to-peer sovereign mesh VPN connectivity.

---

## 2. Formal Requirements & Normative Specifications

### REQ-NET-01 [v0]: 53-Column Terminal Wi-Fi Helper
- **Requirement:** The deck MUST provide a dedicated CLI utility (`wifi`) formatted for 53-column displays wrapping NetworkManager (`status`, `scan`, `join`, `forget`), with profile lookup and `wpa-psk` validation.
- **Rationale:** Standard `nmcli` and `ip` outputs produce wide tables that wrap unreadably across the 53-column CYD display.
- **Traceability:** `WS-4`, `DEC-W29`, `DEC-W30`, `TSK-14`, `ATP-06-NET-WIFI-HELPER`.

### REQ-NET-02 [v0]: Wi-Fi Cold Boot Persistence & Radio Unblock
- **Requirement:** The networking subsystem MUST automatically restore Wi-Fi connectivity within 2.0 seconds of cold boot by setting `options rfkill default_state=1` in `/etc/modprobe.d/rfkill_default.conf`, enforcing `cfg80211.ieee80211_regdom=PH`, setting `wifi.powersave=2` (disabled), and assigning priority 100 to known connections.
- **Rationale:** Prevents default soft-blocking of wireless radios on boot and stabilizes 2.4 GHz link latency by disabling aggressive 802.11 power saving.
- **Traceability:** `DEC-W25`, `TSK-08`.

### REQ-NET-03 [v1]: NetBird Zero-Config Mesh VPN
- **Requirement:** The deck MUST integrate a native NetBird client connecting to the operator's self-hosted coordination server (`100.86.0.0/16`), allowing seamless peer-to-peer SSH access across roaming networks without opening firewall ports.
- **Rationale:** Operators can securely manage and sync the deck across coffee shop Wi-Fi, campus networks, and cellular hotspots without exposing SSH to the public Internet.
- **Traceability:** Section 5.49, Section 8.06, `DEC-W11`, `DEC-W14`.

### REQ-NET-04 [v1]: Dual-Band Wi-Fi Upgrade
- **Requirement:** The networking subsystem MUST support an optional USB dual-band (2.4 GHz / 5 GHz) Wi-Fi adapter to enable connectivity with 5 GHz-only mobile hotspots (such as Redmi Note 12).
- **Rationale:** The internal Pi Zero 2W Broadcom BCM43436 chip supports 2.4 GHz only; external dual-band dongles bridge the gap when 2.4 GHz is unavailable.
- **Traceability:** Section 8.02, `F-08.01`, `DEC-W29`.

---

## 3. Actual Implementation Architecture

### 3.1 The 53-Column Wi-Fi Manager (`pi/bin/wifi`)
- Directly wraps `nmcli -t -f ...` with custom parsers:
  - `wifi status`: Emits compact radio status, SSID, signal strength, IP, and captive portal warning.
  - `wifi scan`: Formats AP list into a clean table showing Index, SSID, Signal bars, and Band (2.4GHz / 5GHz).
  - `wifi join <N|SSID> -p <PASS>`: Connects by scan index or name; prompts for password if omitted.
  - `wifi forget <SSID>`: Deletes stored connection profile.

### 3.2 Wi-Fi Persistence & Power Optimization
Managed via `ansible/roles/wifi_persistence/`:
1. `/etc/modprobe.d/rfkill_default.conf`:
   ```ini
   options rfkill default_state=1
   ```
2. `/etc/default/crda`:
   ```ini
   REGDOMAIN=PH
   ```
3. `/etc/NetworkManager/conf.d/default-wifi-powersave-on.conf`:
   ```ini
   [connection]
   wifi.powersave = 2
   ```

### 3.3 3-Tier Self-Healing Network Watchdog
`/usr/local/bin/cyberdeck-net-heal.sh` runs every 30 seconds via `cyberdeck-net-heal.timer`:
- Tests connectivity by pinging the default gateway.
- If gateway fails for 3 consecutive checks (90 seconds), escalation begins:
  - **Tier 1 (0–5 min):** Issues `rfkill unblock wifi` and reconnects to known SSIDs.
  - **Tier 2 (5–15 min):** Restarts `NetworkManager.service`.
  - **Tier 3 (>15 min):** Forcefully unloads and reloads `brcmfmac` kernel module.
  - *Hard Rule:* Never issues a system reboot.

### 3.4 NetBird WireGuard Overlay (`ansible/roles/netbird/`)
- Connects to operator mesh at `100.86.0.0/16`.
- Binds to interface `wt0` with persistent keepalive (25 seconds).
- Active edge node: `100.86.0.15` (DigitalFyre Kuro Neko Edge Node).

---

## 4. Verification & Acceptance Criteria

- **`ATP-06-NET-WIFI-HELPER`:** Validates 53-column output constraints, scan parsing, captive portal detection, and network joining.
- **`ATP-08-NET-SELF-HEAL`:** Validates cold boot persistence flags, rfkill default state, and 3-tier recovery simulation.
