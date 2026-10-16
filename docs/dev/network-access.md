# WhiskerFrame Cyberdeck Network Access & Operations Guide

## 1. Overview & Screen Constraints

This document defines the network architecture, operational procedures, field connectivity methods, and troubleshooting protocols for the WhiskerFrame Cyberdeck (Raspberry Pi Zero 2W).

### Display Constraint (53 Columns)
The primary physical console of the cyberdeck is driven by the Cheap Yellow Display (CYD / ESP32-2432S028R) running the `cyd-terminal` bridge over high-speed UART. In default font size 1, the hardware character grid is **53 columns wide by 30 rows high**.

All on-device network management tools, scripts, and status monitors (specifically `/opt/cyd-display-link/pi/bin/wifi` or `pi/bin/wifi`) **strictly enforce a 53-column line ceiling**. Any output exceeding 53 characters will wrap onto subsequent display lines, destroying tabular layout and scrolling critical status indicators off screen.

---

## 2. Hardware Radio Reality (Raspberry Pi Zero 2W)

### RF Transceiver: Broadcom BCM43436
The Raspberry Pi Zero 2W integrates a Broadcom BCM43436 wireless chip handled by the upstream Linux `brcmfmac` kernel driver.

```
+-------------------------------------------------------------+
|                 Broadcom BCM43436 (brcmfmac)                |
|                                                             |
|  Supported Bands:   2.4 GHz ONLY (802.11b/g/n)              |
|  Channel Range:     Channels 1 to 13 (2412 MHz - 2472 MHz)  |
|  PH Regdomain:      PH (Philippines) 2400-2483.5 MHz        |
|  5 GHz Support:     NONE (Hardware lacks 5 GHz RF mixer)    |
|  6 GHz Support:     NONE                                    |
+-------------------------------------------------------------+
```

### Critical Field Limitations
1. **5 GHz Invisibility**: The BCM43436 hardware physically lacks a 5 GHz RF front-end mixer, filter, and antenna switch. It **cannot scan, detect, or connect** to 5 GHz (802.11a/ac/ax) Wi-Fi networks.
2. **Dual-Band SSID Traps**: Access points broadcasting a single SSID across both 2.4 GHz and 5 GHz with aggressive band steering may attempt to push the client to 5 GHz by dropping 2.4 GHz probe responses or sending deauth frames. The `pi/bin/wifi` helper explicitly discriminates BSSIDs and selects 2.4 GHz entries.
3. **5 GHz Hotspot Invisibility**: Modern smartphones and laptops default to 5 GHz for hotspot sharing. If a hotspot is configured on 5 GHz, the cyberdeck will see zero beacons and report no networks found.
4. **2.4 GHz Congestion & Co-existence**: High density of Bluetooth (including onboard Bluetooth) and overlapping Wi-Fi signals causes packet drops. Disabling 802.11 power saving (`powersave=2`) prevents the radio from missing frames during DTIM sleep windows.

---

## 3. Venue Network Edge Cases & Hardened Mitigations

Venue Wi-Fi networks (conferences, hackathons, university campuses such as CvSU, hotels, transit hubs) present hostile environments for headless or embedded devices. The following edge cases and concrete mitigations are codified for WhiskerFrame operations:

### Edge Case 1: WPA2/WPA3-Enterprise (802.1X / EAP-PEAP / MSCHAPv2 / eduroam)
* **The Trap**: University and corporate venues enforce IEEE 802.1X Network Access Control requiring Phase 2 inner authentication (e.g. PEAP/MSCHAPv2, TTLS, or TLS client certificates). A standard interactive passphrase prompt (`wifi join`) cannot negotiate enterprise identity exchanges.
* **Concrete Mitigations**:
  1. **Hotspot Bridge (Recommended Field Method)**: Connect smartphone or laptop to the 802.1X network, then share connection via 2.4 GHz tethering (Method A / Method B). The mobile device terminates 802.1X and delivers simple WPA2-PSK to the cyberdeck.
  2. **Pre-staged NetworkManager Profile**: For frequent venues (e.g. CvSU campus), pre-configure an enterprise connection profile in `/etc/NetworkManager/system-connections/CvSU-Enterprise.nmconnection`:
     ```ini
     [connection]
     id=CvSU-Enterprise
     type=wifi
     interface-name=wlan0

     [wifi]
     mode=infrastructure
     ssid=CvSU-WiFi

     [wifi-security]
     key-mgmt=wpa-eap

     [802-1x]
     eap=peap;
     identity=<student-or-staff-id>
     password=<password>
     phase2-auth=mschapv2
     ```
  3. **Automated Detection**: `pi/bin/wifi join` detects `802.1X` or `EAP` flags during scanning and alerts the operator on screen to use pre-configured profiles or hotspot tethering.

### Edge Case 2: Captive Portals (Hotels, Coffee Shops, Guest Networks)
* **The Trap**: Guest networks grant a DHCP lease and local IP, but hijack DNS and intercept HTTP/HTTPS traffic with an HTTP 302 redirect to a captive web login / Terms-of-Service portal. Because the cyberdeck lacks a full browser on the physical console, internet routing remains blocked.
* **Concrete Mitigations**:
  1. **Connectivity Check on Console**: `pi/bin/wifi status` invokes `nmcli networking connectivity check` and explicitly displays `Portal: CAPTIVE PORTAL DETECTED!` or `Internet: connected (full)` within the 53-column boundary.
  2. **MAC Address Cloning**: If a venue captive portal requires browser authentication:
     - Connect smartphone or laptop to the venue Wi-Fi and complete portal login.
     - Note the authorized device's MAC address.
     - Clone that MAC onto the cyberdeck `wlan0`:
       ```bash
       sudo nmcli connection modify <SSID> 802-11-wireless.cloned-mac-address <AUTH_MAC>
       sudo nmcli connection up <SSID>
       ```
  3. **Terminal Browser / Curl Fallback**: For simple forms without complex JavaScript:
     ```bash
     curl -s -L http://neverssl.com | head -n 30
     ```
  4. **Bypass via Phone Hotspot**: Avoid captive portal entirely by tethering via phone mobile data.

### Edge Case 3: AP Client Isolation (Station Isolation / Private VLAN)
* **The Trap**: The access point drops Layer 2 and Layer 3 peer-to-peer traffic between stations. Even if laptop and cyberdeck are on the same Wi-Fi, SSH and pings fail silently.
* **Concrete Mitigations**:
  1. **NetBird Mesh VPN**: WireGuard overlay over outbound UDP to external relays traverses isolation effortlessly.
  2. **USB Serial Gadget**: Direct zero-network access via `/dev/ttyACM0` on the laptop.
  3. **Hardware CYD/CardKB**: Full console access directly on physical hardware.

### Edge Case 4: 2.4 GHz Spectrum Congestion & Band Steering
* **The Trap**: High noise floor, overlapping BSSIDs on channels 1, 6, 11, and aggressive AP band steering trying to push dual-band clients to 5 GHz.
* **Concrete Mitigations**:
  1. **Deduplication Favoring 2.4 GHz**: `pi/bin/wifi scan` groups APs by SSID and picks the strongest 2.4 GHz BSSID, ignoring 5 GHz entries that would otherwise fail.
  2. **Wi-Fi Power Save Disabled**: NetworkManager default Wi-Fi powersave is set to `2` (disabled) via `/etc/NetworkManager/conf.d/default-wifi-powersave.conf` (managed by `wifi_persistence` role).
  3. **Regulatory Domain Lockdown**: Fixed to `country=PH` in both wpa_supplicant and kernel regdomain to enable valid transmission on channels 1-13 without channel hopping delays.

---

## 3. Field Access Methods

When operating in the field (hackathons, conferences, transit, or client sites), use the following methods to establish a network uplink.

### Method A: Android Phone Hotspot (Redmi Note 12 / MIUI / Xiaomi HyperOS)
Modern MIUI and Xiaomi HyperOS builds enable 5 GHz Wi-Fi tethering by default. To connect the cyberdeck, force the hotspot to 2.4 GHz.

#### Configuration Steps
1. Open Android **Settings** -> **Portable hotspot**.
2. Tap **Set up portable hotspot**.
3. Locate **Select AP Band**:
   - Change from **5.0 GHz band** to **2.4 GHz band**.
4. *On newer HyperOS builds*: If explicit band selection is replaced by a toggle, turn **ON** the switch labeled **Maximize compatibility** (this forces 2.4 GHz 802.11b/g/n mode).
5. Set **Security** to **WPA2-Personal** (avoid WPA3-Personal / SAE-only modes to ensure compatibility with `brcmfmac` wpa_supplicant handshakes).
6. Enable the hotspot and connect from the cyberdeck:
   ```bash
   wifi scan
   wifi join <N|SSID>
   ```

### Method B: Laptop-Hosted 2.4 GHz Hotspot Fallback
When phone tethering is unavailable, mobile data is exhausted, or venue captive portals block device-to-device sharing, create an ad-hoc 2.4 GHz hotspot directly on the developer laptop.

#### NetworkManager Hotspot Command
Run on the developer laptop:
```bash
nmcli device wifi hotspot ifname wlan0 ssid WhiskerDeck password "<secure-passphrase>" band bg
```

#### Why `band bg` is Mandatory
* `band bg`: Restricts the software AP to the 2.4 GHz spectrum (802.11b/g).
* If `band` is omitted or set to `band a`, NetworkManager will select a 5 GHz channel on dual-band laptop cards, rendering the hotspot invisible to the Raspberry Pi Zero 2W.

#### Teardown
To shut down the laptop hotspot:
```bash
nmcli connection down WhiskerDeck
```

---

## 4. Client Isolation & Peer-to-Peer Access Workarounds

### The Venue Network Trap
Hotel, conference, university, and public Wi-Fi networks (including campus environments like CvSU) frequently configure **AP Client Isolation** (Private VLAN / Station Isolation).

* Under client isolation, wireless stations associated with the same SSID cannot transmit Layer 2 or Layer 3 packets to one another.
* Laptop and cyberdeck may both receive valid DHCP IP addresses (e.g. `10.x.x.x`), but direct ping, SSH (`ssh neko@whiskerdeck.local`), and HTTP connections will be dropped silently at the AP switch fabric.

```
                    [Venue Access Point]
                    (Client Isolation ON)
                     /                 \
             Drop P2P /                 \ Drop P2P
                     X                   X
                    /                     \
       [Developer Laptop]             [Cyberdeck]
       10.20.30.45                    10.20.30.88
       (Cannot SSH)                   (Cannot ping)
```

### Workaround 1: NetBird Mesh VPN (Overlay Tunnel)
NetBird provides an encrypted WireGuard-based mesh overlay. Because peers connect outbound over UDP to external STUN/TURN relays, traffic traverses venue firewalls and client-isolated access points transparently.

```
       [Developer Laptop]             [Cyberdeck]
          100.86.2.10                   100.86.1.20
               \                             /
                \--- Outbound UDP Tun ---/
                            |
                 [NetBird Relay / STUN]
```

* **Ansible Role**: Dedicated `ansible/roles/netbird` role (also accessible via `native_services` tags) installs client binary and supervises `netbird.service` with memory safety ceiling (`MemoryMax=150M`).
* **Current Status**: **BLOCKED-ON-OPERATOR**. Unattended enrollment requires `vault_netbird_setup_key` populated in Ansible vault (`ansible/host_vars/cyberdeck/vault.yml`). If key is omitted, deployment gracefully stages the service with a skip notice.
* **Operator Action**: Once the setup key is provided in vault, run:
  ```bash
  cd ansible && uvx --from ansible-core ansible-playbook -i inventory.ini site.yml --tags netbird
  ```
* **Manual Enrollment (Emergency CLI)**:
  ```bash
  sudo netbird up --setup-key <OPERATOR_SETUP_KEY>
  ```

### Workaround 2: Direct USB Serial Gadget (Zero-Infrastructure)
When all wireless options fail or client isolation blocks SSH, connect the cyberdeck directly via USB OTG.

1. Connect a micro-USB data cable from the developer laptop to the Pi Zero 2W **USB data port** (inner micro-USB port, labeled `USB`, not `PWR IN`).
2. The Pi exposes a CDC ACM serial gadget (`g_serial`).
3. Connect from the laptop terminal:
   ```bash
   screen /dev/ttyACM0 115200
   ```
4. Authenticate as user `neko`. Full root and shell access is immediately available without any network dependencies.

### Workaround 3: Direct Console via Onboard CYD Terminal & CardKB
The WhiskerFrame cyberdeck includes an onboard 320x240 LCD and CardKB keyboard. Type directly on the device console:
```bash
wifi status
wifi scan
wifi join 1
```

---

## 5. Multicast DNS (mDNS / .local) Caveats

The cyberdeck advertises its hostname via Avahi (`whiskerdeck.local` on `224.0.0.251:5353` / `ff02::fb:5353`).

### Failure Modes on 2.4 GHz Congested Networks
1. **Multicast Packet Dropping**: Wi-Fi access points in high-density environments aggressively drop or de-prioritize 802.11 multicast frames to prevent broadcast storms from exhausting airtime.
2. **DTIM Power Save Sleeping**: Low-power stations sleeping during DTIM intervals frequently miss mDNS beacon queries.
3. **Name Resolution Failure**: Running `ssh neko@whiskerdeck.local` will frequently hang or report `Host not found` even while the Pi has a valid IP address.

### Mitigations
* **Check Onboard Screen**: Run `wifi` on the cyberdeck CardKB terminal to read the assigned IP address directly:
  ```
  === Wi-Fi Status ===
  Interface:  wlan0
  State:      connected
  SSID:       Venue-Guest
  Signal:     78% (2.4GHz)
  IP Address: 192.168.1.145/24
  ```
* **SSH Directly by IP**: Use `ssh neko@192.168.1.145` instead of mDNS hostname.
* **Router Static Reservation**: In home/lab environments, bind the Pi Zero 2W MAC address to a static DHCP lease.
* **NetBird IP**: Connect using the static NetBird overlay IP (e.g. `100.86.1.x`).

---

## 6. Offline Network Automation Status (TSK-05)

### Component State
* **Ansible Role**: `ansible/roles/network_automation` (packages `iwd`, `dnsmasq`, `hostapd`, and `network-arbiter`).
* **Deployment Setting**: Staged with `network_automation_apply: false` in `ansible/site.yml`.

### Rationale
Automated network failover (switching between Wi-Fi client mode and a standalone fallback AP when connections drop) requires replacing `wpa_supplicant` with `iwd` and stopping NetworkManager.

Executing this switch remotely over SSH on a headless cyberdeck introduces a **severe lockout risk** if `iwd` fails to negotiate with the venue AP. Consequently, TSK-05 is deliberately staged and gated:
* The configuration templates and systemd units are installed on disk.
* The migration is **NOT applied** live until verified via physical serial console.

---

## 7. Cyberdeck Wi-Fi CLI Reference (`pi/bin/wifi`)

The `wifi` utility is an executable Python helper located at `pi/bin/wifi` (deployed to `/opt/cyd-display-link/pi/bin/wifi` on the Pi). It wraps `nmcli` while guaranteeing 53-column screen fitting and 2.4 GHz radio safety.

### Command Matrix

| Command | Arguments | Description |
|---|---|---|
| `wifi` or `wifi status` | None | Displays active interface, connection state, SSID, signal %, band, IP address, and saved connection profiles. |
| `wifi scan` | None | Performs active scan (`--rescan yes`), deduplicates BSSIDs by SSID (preferring 2.4 GHz), sorts by signal strength, and displays top 10 networks formatted <= 53 columns. Saves scan to `/tmp/wifi-scan.json`. Warns if 5 GHz APs are detected. |
| `wifi join <N>` | Index number `1..10` | Connects to the Nth network from the previous `wifi scan`. Prompts securely for password if secured. Warns before attempting 5 GHz connection. |
| `wifi join <SSID>` | Network SSID | Connects directly to named SSID. Prompts for password if not saved or open. |
| `wifi join ... --hidden` | Flag | Connects to hidden network (`hidden yes` in nmcli). |
| `wifi join ... -p <PWD>` | Password string | Passphrase passed directly (avoids interactive prompt in scripts). |
| `wifi forget <SSID>` | Profile name | Deletes the saved connection profile from NetworkManager. |

### Example CLI Workflows

#### 1. Checking Status
```
$ wifi
=== Wi-Fi Status ===
Interface:  wlan0
State:      connected
SSID:       WhiskerDeck
Signal:     82% (2.4GHz)
Security:   WPA2
IP Address: 10.0.0.123/24

=== Saved Networks ===
* WhiskerDeck (active)
  Home-WiFi
  PhoneHotspot
```

#### 2. Scanning Networks
```
$ wifi scan
WARN: 5GHz APs found (Zero 2W is 2.4GHz only)
N   SSID                    SIG  SEC               
--------------------------------------------------
 1  Redmi-Note-12           92%  WPA2              
 2  WhiskerDeck             85%  WPA2              
 3  CoffeeShop-2.4G         72%  WPA1 WPA2         
 4  FastNet-5G              65%  WPA3 [5G]         
 5  Venue-Public            58%  OPEN              
```

#### 3. Joining by Index
```
$ wifi join 1
Password for 'Redmi-Note-12': 
Connecting to 'Redmi-Note-12'...
Successfully connected to 'Redmi-Note-12'.
```

#### 4. Forgetting a Saved Network
```
$ wifi forget CoffeeShop-2.4G
Forgot connection 'CoffeeShop-2.4G'.
```
