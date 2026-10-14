# Whiskerframe Cyberdeck Demo-Day Checklist & Field Guide

## 1. Overview

This document specifies the operational checklist, demonstration script, runtime measurements, and post-demo security teardown for showcasing the **Whiskerframe Cyberdeck v0.1** (Raspberry Pi Zero 2W + Cheap Yellow Display + CardKB + 3S UPS Module).

---

## 2. Pre-Flight Morning Checklist (Before Handing to Anyone)

Complete these verification checks on AC power before disconnecting for field demonstration:

- [ ] **Battery State:**
  - Verify pack voltage is >= 12.3V (~90-100% capacity) via:
    ```bash
    cat /run/battery_monitor/status.json
    ```
  - Ensure battery cells are balanced and charge current settles to float (~0.0 to 0.3mA).
- [ ] **Thermal Baseline:**
  - Ensure idle temperature is < 62°C in fanless enclosure:
    ```bash
    vcgencmd measure_temp
    ```
- [ ] **Health & Throttling Status:**
  - Verify zero historical undervoltage or thermal throttling:
    ```bash
    vcgencmd get_throttled
    # MUST return: throttled=0x0
    ```
- [ ] **Self-Healing & Watchdog Services:**
  - Confirm hardware watchdog and network self-healing timers are active:
    ```bash
    systemctl status cyberdeck-net-heal.timer cyberdeck-guest-reaper.service
    ```
- [ ] **Terminal Bridge & Display:**
  - Verify CYD display is lit, showing either the splash screen or the piiiiink a11y login gate (`whiskerframe login`).
- [ ] **Safety Backup on SSD:**
  - Confirm safety net backup exists in `/mnt/250GB-SSD/backup/2026-10-14/` with valid `SHA256SUMS`.
- [ ] **Guest Containment Active:**
  - Run the containment test suite:
    ```bash
    /usr/local/bin/test-guest-containment.sh
    # MUST report: 0 failed
    ```

---

## 3. Power Budget & Runtime Measurements

### Measured Electrical Characteristics
- **Battery Pack:** 3S 18650 Li-ion pack (11.1V nominal, ~12.6V peak, ~35 Wh capacity).
- **Idle Power Consumption (Display On, Radios Active, Terminal Idle):**
  - Voltage: ~12.40V
  - Current Draw: ~145 mA to 190 mA (~1.8W to 2.35W)
  - Estimated Continuous Runtime: **15 to 19 hours**.
- **Active Demo Load (Typing, Draw Commands, Cgroup Execution):**
  - Current Draw: ~220 mA to 290 mA (~2.7W to 3.5W)
  - Estimated Active Runtime: **10 to 13 hours**.
- **Safety Cutoff Threshold:**
  - Low-battery warning triggers at 10.8V (~15%).
  - Emergency shutdown threshold at 10.2V (~5% pack floor).

---

## 4. Live Demonstration Script (Step-by-Step)

When handing the cyberdeck to an observer or guest:

### Step 1: Boot & Splash Screen (Visual Aesthetic)
1. Power on the deck via the physical toggle switch.
2. Direct attention to the CYD screen:
   - Full-color 320x240 RGB565 splash graphic renders instantly.
   - Clean transition into the custom login gate with the piiiiink a11y retro theme.

### Step 2: The Login Experience (Multi-Tenant Security)
1. Show the CardKB keyboard (two-thumb typing posture).
2. Use `Tab` / Arrow keys to select the `guest` user.
3. Enter password `guest` (characters masked on-screen).
4. Point out the instant PTY fork and session initialization.

### Step 3: Deck Telemetry Banner
1. At the guest prompt, run:
   ```bash
   demo
   ```
2. Explain the live readings:
   - System uptime and Linux kernel version.
   - Live battery voltage and capacity via I2C INA219.
   - Current SoC temperature and available RAM.
   - Active security containment boundaries.

### Step 4: Proving Kernel-Level Containment (The "Hack Me" Challenge)
Invite the guest to attempt escaping the sandbox:
1. **Network Denial:**
   ```bash
   ping 1.1.1.1
   curl http://127.0.0.1:8080
   # Result: Operation not permitted / Destination unreachable (dropped by nftables skuid rule).
   ```
2. **Filesystem Privacy:**
   ```bash
   ls /home/neko
   ls /root
   cat /etc/NetworkManager/system-connections/*
   # Result: Permission denied (0700 permissions enforced).
   ```
3. **Privilege Escalation:**
   ```bash
   sudo su
   # Result: guest is not in sudoers file. Incident reported.
   ```
4. **Execution Reaper (Denial of Service Prevention):**
   ```bash
   # Try spawning a long-running process or infinite loop:
   sleep 30
   # Result: Terminated with SIGKILL after 5 seconds by cyberdeck-guest-reaper.
   ```

### Step 5: Clean Ephemeral Logout
1. Type `exit` to log out.
2. Explain that the PAM `close_session` hook immediately purges the 8MB tmpfs home directory.
3. Log back in as `guest` to demonstrate a pristine, zero-footprint environment.

---

## 5. Post-Demo Security Teardown (CRITICAL)

Immediately after concluding the public demonstration:

- [ ] **Rotate Temporary Passwords:**
  - Immediately rotate the root and neko account passwords.
  - Command:
    ```bash
    sudo passwd root
    sudo passwd neko
    ```
- [ ] **Audit Authentication Logs:**
  - Inspect journal for any unexpected privilege escalation attempts or anomalies:
    ```bash
    journalctl -u terminal.service -n 50 --no-pager
    grep "sudo:" /var/log/auth.log 2>/dev/null || journalctl _COMM=sudo
    ```
- [ ] **Stage Down Guest Access (Optional):**
  - If no further public demonstrations are scheduled, lock the guest account:
    ```bash
    sudo usermod -L guest
    ```
- [ ] **Connect External Charger:**
  - Reconnect the 12.6V DC barrel charger to bring the 3S pack back to 100% float charge.
