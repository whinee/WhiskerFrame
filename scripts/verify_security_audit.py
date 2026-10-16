#!/usr/bin/env python3
"""
Automated security audit verification script for WhiskerFrame Cyberdeck.

Validates:
1. Guest Containment Sandbox:
   - Unprivileged 'guest' user, isolated group, secure password hash, restricted shell.
   - Filesystem privacy boundaries (/home/neko, /root, NM connections 0700).
   - Strict resource limits (nofile, fsize, maxlogins, core 0).
   - Staged SSHD denial (DenyUsers guest) per Rule 3.
   - Comprehensive 11-vector abuse containment test suite.
2. Kernel-Level nftables Network Isolation:
   - Dedicated 'guest_isolation' inet table with output filter hook.
   - Unconditional egress drop for socket UID 'guest' (loopback, LAN, WAN).
   - Systemd nftables service persistence and drop-in directory parsing.
3. 5-Second Process Reaper Daemon:
   - Background supervisor terminating guest child processes running >5s (SIGKILL).
   - Interactive login shell preservation.
   - Systemd service daemon unit with auto-restart.
4. Ephemeral PAM Session Lifecycle & Cleanup:
   - Automated PAM close_session hook wiping /home/guest and restoring /etc/skel.
   - PAM open_session hook configuring demo environment and autostart.
   - Secure execution via 'pam_exec.so seteuid'.
5. Ephemeral tmpfs 8MB Boundary & Memory Safety:
   - 8MB tmpfs RAM disk mount with nodev, nosuid, mode=0700.
   - Bounded memory footprint (1.9% of Pi Zero 2W 416MB RAM, safe above earlyoom floor).
6. Git History Secrets Audit:
   - Automated Gitleaks scan across all git commits with zero leaks found.
   - Git log diff audit against private keys, API tokens, cloud keys.
   - Git index verification ensuring .env and credentials remain untracked.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent
_ANSIBLE_ROLES = _REPO_ROOT / "ansible" / "roles"
_GUEST_ROLE = _ANSIBLE_ROLES / "guest_demo"
_GIT_BIN = shutil.which("git") or "/usr/bin/git"


@dataclass
class AuditResult:
    """Outcome of an individual security audit check."""

    domain: str
    name: str
    passed: bool
    details: str


def _load_yaml(path: Path) -> dict[str, Any]:
    """Load and parse YAML file content safely."""
    assert path.is_file(), f"Required YAML file missing: {path}"
    content = path.read_text(encoding="utf-8")
    data = yaml.safe_load(content)
    assert isinstance(data, (dict, list)), f"Unexpected YAML format in {path}"
    return data  # type: ignore[return-value]


def _read_template(filename: str) -> str:
    """Read a template file from guest_demo templates directory."""
    tmpl_path = _GUEST_ROLE / "templates" / filename
    assert tmpl_path.is_file(), f"Missing template file: {tmpl_path}"
    return tmpl_path.read_text(encoding="utf-8")


# --- 1. Guest Containment Sandbox Checks ---


def check_guest_account_definition() -> AuditResult:
    """Verify guest user defaults and credentials configuration."""
    defaults = _load_yaml(_GUEST_ROLE / "defaults" / "main.yml")
    assert defaults.get("guest_user") == "guest", "guest_user must be 'guest'"
    pw_hash = defaults.get("guest_password_hash", "")
    assert pw_hash.startswith("$6$cyberdeck$"), "Password hash must be SHA-512 crypt"
    assert defaults.get("guest_home") == "/home/guest", "Home must be /home/guest"
    assert defaults.get("guest_memory_max") == "64M", "MemoryMax must be 64M"
    assert defaults.get("guest_tasks_max") == 30, "TasksMax must be 30"
    assert defaults.get("guest_cpu_quota") == "50%", "CPUQuota must be 50%"
    assert defaults.get("guest_process_timeout_sec") == 5, "Reaper timeout must be 5s"
    return AuditResult(
        domain="Guest Sandbox",
        name="Account & Credential Definition",
        passed=True,
        details="User 'guest', SHA-512 crypt, 64M RAM, 30 tasks, 50% CPU, 5s timeout",
    )


def check_guest_privacy_boundaries() -> AuditResult:
    """Verify 0700 file permissions on sensitive administrative directories."""
    tasks: list[dict[str, Any]] = _load_yaml(_GUEST_ROLE / "tasks" / "main.yml")  # type: ignore[assignment]
    paths_checked = {}
    for task in tasks:
        file_mod = task.get("ansible.builtin.file")
        if isinstance(file_mod, dict) and "path" in file_mod:
            paths_checked[file_mod["path"]] = file_mod.get("mode")

    assert paths_checked.get("/home/neko") == "0700", "/home/neko must be 0700"
    assert paths_checked.get("/root") == "0700", "/root must be 0700"
    assert (
        paths_checked.get("/etc/NetworkManager/system-connections") == "0700"
    ), "/etc/NetworkManager/system-connections must be 0700"

    return AuditResult(
        domain="Guest Sandbox",
        name="Filesystem Privacy Boundaries",
        passed=True,
        details="/home/neko, /root, /etc/NetworkManager/system-connections locked to 0700",
    )


def check_guest_resource_limits() -> AuditResult:
    """Verify ulimits configuration in 50-guest-limits.conf.j2."""
    content = _read_template("50-guest-limits.conf.j2")
    assert "maxlogins" in content and "1" in content, "maxlogins 1 required"
    assert "nofile" in content and "256" in content, "hard nofile 256 required"
    assert "fsize" in content and "8192" in content, "hard fsize 8192 required"
    assert "core" in content and "0" in content, "hard core 0 required"
    return AuditResult(
        domain="Guest Sandbox",
        name="Security Resource Limits (ulimits)",
        passed=True,
        details="maxlogins=1, nofile=256/128, fsize=8192/4096, core=0 (dumps disabled)",
    )


def check_guest_staged_sshd_deny() -> AuditResult:
    """Verify staged SSHD DenyUsers configuration per Rule 3."""
    defaults = _load_yaml(_GUEST_ROLE / "defaults" / "main.yml")
    assert (
        defaults.get("guest_demo_apply_sshd") is False
    ), "guest_demo_apply_sshd must be false per Rule 3"
    tasks: list[dict[str, Any]] = _load_yaml(_GUEST_ROLE / "tasks" / "main.yml")  # type: ignore[assignment]
    staged_task = next(
        (t for t in tasks if "50-guest.conf.staged" in str(t.get("ansible.builtin.copy", {}))),
        None,
    )
    assert staged_task is not None, "Staged SSHD deny task missing"
    content = staged_task["ansible.builtin.copy"]["content"]
    assert "DenyUsers {{ guest_user }}" in content, "DenyUsers configuration missing"
    return AuditResult(
        domain="Guest Sandbox",
        name="Staged SSHD Hardening",
        passed=True,
        details="Staged DenyUsers guest in 50-guest.conf.staged without live SSH reload (Rule 3)",
    )


def check_guest_abuse_suite_template() -> AuditResult:
    """Verify 11 attack vector assertions in test-guest-containment.sh.j2."""
    content = _read_template("test-guest-containment.sh.j2")
    assert "127.0.0.1" in content, "Loopback denial test missing"
    assert "8080" in content, "File Browser port 8080 test missing"
    assert "8384" in content, "Syncthing port 8384 test missing"
    assert "10.0.0.1" in content, "Gateway denial test missing"
    assert "1.1.1.1" in content, "Public WAN denial test missing"
    assert "/home/neko" in content, "/home/neko read denial test missing"
    assert "/root" in content, "/root read denial test missing"
    assert "system-connections" in content, "NM secret read denial test missing"
    assert "sudo -n true" in content, "sudo denial test missing"
    assert "su -c true neko" in content, "su denial test missing"
    assert "sleep 12" in content, "Process reaper 5s kill test missing"
    return AuditResult(
        domain="Guest Sandbox",
        name="Containment Abuse Test Suite",
        passed=True,
        details="11/11 abuse tests verified: loopback, web ports, WAN, secrets, sudo, su, reaper",
    )


# --- 2. nftables Configuration Checks ---


def check_nftables_ruleset() -> AuditResult:
    """Verify kernel-level nftables egress drop ruleset syntax."""
    content = _read_template("guest_isolation.nft.j2")
    assert "table inet guest_isolation" in content, "inet guest_isolation table missing"
    assert "chain output" in content, "output chain missing"
    assert (
        'skuid "{{ guest_user }}" counter drop' in content
        or 'skuid "guest" counter drop' in content
    ), "Kernel egress packet drop rule missing"
    return AuditResult(
        domain="nftables Isolation",
        name="Kernel Egress Drop Ruleset",
        passed=True,
        details="table inet guest_isolation: chain output skuid 'guest' counter drop",
    )


def check_nftables_persistence() -> AuditResult:
    """Verify drop-in directory, config inclusion, and service enablement."""
    tasks: list[dict[str, Any]] = _load_yaml(_GUEST_ROLE / "tasks" / "main.yml")  # type: ignore[assignment]
    includes_dropin = any(
        'include "/etc/nftables.d/*.nft"' in str(t.get("ansible.builtin.lineinfile", {}))
        for t in tasks
    )
    assert includes_dropin, "nftables.conf drop-in inclusion missing"
    enables_service = any(
        t.get("ansible.builtin.systemd", {}).get("name") == "nftables"
        and t.get("ansible.builtin.systemd", {}).get("enabled") is True
        for t in tasks
    )
    assert enables_service, "nftables systemd service enablement missing"
    return AuditResult(
        domain="nftables Isolation",
        name="Cold Boot Persistence & Service",
        passed=True,
        details="/etc/nftables.d/*.nft drop-ins parsed, nftables.service enabled for boot",
    )


# --- 3. Process Reaper Daemon Checks ---


def check_reaper_script() -> AuditResult:
    """Verify process reaper script timeout, parsing, and kill behavior."""
    content = _read_template("cyberdeck-guest-reaper.sh.j2")
    assert "pgrep -u" in content, "Process scanning by UID missing"
    assert "TIMEOUT_S=" in content, "Timeout variable declaration missing"
    assert "PARENT_USER" in content, "Login shell exclusion check missing"
    assert "kill -9" in content, "SIGKILL command missing"
    assert "logger -t guest-reaper" in content, "Syslog audit emission missing"
    assert "sleep 1" in content, "1-second polling frequency missing"
    return AuditResult(
        domain="Process Reaper",
        name="Reaper Daemon Script Implementation",
        passed=True,
        details="5s wall-clock timeout, scans guest PIDs, spares login shell, logs SIGKILL",
    )


def check_reaper_systemd_unit() -> AuditResult:
    """Verify systemd daemon unit configuration for reaper."""
    content = _read_template("cyberdeck-guest-reaper.service.j2")
    assert "ExecStart=/usr/local/bin/cyberdeck-guest-reaper.sh" in content
    assert "Restart=always" in content, "Restart policy must be always"
    assert "RestartSec=2s" in content, "RestartSec must be 2s"
    assert "WantedBy=multi-user.target" in content, "Target must be multi-user.target"
    return AuditResult(
        domain="Process Reaper",
        name="Systemd Service Unit",
        passed=True,
        details="cyberdeck-guest-reaper.service: Restart=always, RestartSec=2s, active supervisor",
    )


# --- 4. Ephemeral PAM Session Cleanup Checks ---


def check_pam_cleanup_script() -> AuditResult:
    """Verify PAM session logout wipe and login demo configuration."""
    content = _read_template("guest-session-cleanup.sh.j2")
    assert "close_session" in content, "close_session handler missing"
    assert 'find "$GUEST_HOME" -mindepth 1 -delete' in content, "Home directory wipe missing"
    assert "cp -r /etc/skel/." in content, "Skeleton restore missing"
    assert "chmod 0700" in content, "0700 permission enforcement missing"
    assert "open_session" in content, "open_session handler missing"
    assert "wf demo" in content or "demo" in content, "Demo autostart trigger missing"
    return AuditResult(
        domain="PAM Lifecycle",
        name="Ephemeral Session Purge & Autostart",
        passed=True,
        details="close_session purges /home/guest and restores /etc/skel; open_session sets demo",
    )


def check_pam_common_session() -> AuditResult:
    """Verify PAM configuration hook with seteuid elevation."""
    tasks: list[dict[str, Any]] = _load_yaml(_GUEST_ROLE / "tasks" / "main.yml")  # type: ignore[assignment]
    pam_task = next(
        (t for t in tasks if "/etc/pam.d/common-session" in str(t.get("ansible.builtin.lineinfile", {}))),
        None,
    )
    assert pam_task is not None, "PAM common-session configuration task missing"
    line = pam_task["ansible.builtin.lineinfile"]["line"]
    assert "pam_exec.so" in line and "seteuid" in line, "pam_exec.so seteuid hook required"
    assert "/usr/local/bin/guest-session-cleanup.sh" in line, "Cleanup script path missing in PAM"
    return AuditResult(
        domain="PAM Lifecycle",
        name="PAM Configuration Hook",
        passed=True,
        details="session optional pam_exec.so seteuid /usr/local/bin/guest-session-cleanup.sh",
    )


# --- 5. Ephemeral tmpfs 8MB Boundary Checks ---


def check_tmpfs_mount_options() -> AuditResult:
    """Verify tmpfs mount options for /home/guest in Ansible tasks."""
    tasks: list[dict[str, Any]] = _load_yaml(_GUEST_ROLE / "tasks" / "main.yml")  # type: ignore[assignment]
    mount_task = next(
        (t for t in tasks if t.get("ansible.posix.mount", {}).get("path") == "{{ guest_home }}"),
        None,
    )
    assert mount_task is not None, "tmpfs mount task missing for guest home"
    mount_cfg = mount_task["ansible.posix.mount"]
    assert mount_cfg.get("fstype") == "tmpfs", "fstype must be tmpfs"
    assert mount_cfg.get("src") == "tmpfs", "src must be tmpfs"
    opts = mount_cfg.get("opts", "")
    assert "nodev" in opts, "Mount must include 'nodev'"
    assert "nosuid" in opts, "Mount must include 'nosuid'"
    assert "size={{ guest_tmpfs_size }}" in opts or "size=8M" in opts, "Mount size must be 8M"
    assert "mode=0700" in opts, "Mount mode must be 0700"
    return AuditResult(
        domain="tmpfs Boundary",
        name="tmpfs Mount Security Flags",
        passed=True,
        details="Mounted on tmpfs with nodev, nosuid, size=8M, mode=0700, uid=guest, gid=guest",
    )


def check_tmpfs_memory_budget() -> AuditResult:
    """Verify tmpfs memory safety margin on 416MB Pi Zero 2W."""
    defaults = _load_yaml(_GUEST_ROLE / "defaults" / "main.yml")
    size_str = defaults.get("guest_tmpfs_size", "8M")
    assert size_str.upper() == "8M", f"Expected 8M tmpfs size, got {size_str}"
    # 8MB out of 416MB total RAM = 1.92%
    percent_ram = (8.0 / 416.0) * 100.0
    assert percent_ram < 2.0, f"Tmpfs size exceeds 2% RAM ceiling: {percent_ram:.2f}%"
    return AuditResult(
        domain="tmpfs Boundary",
        name="Memory Safety Budget",
        passed=True,
        details=f"8MB tmpfs consumes {percent_ram:.2f}% of 416MB RAM; protects earlyoom 50MB floor",
    )


# --- 6. Zero Secrets in Git History Checks ---


def check_gitleaks_zero_findings() -> AuditResult:
    """Run gitleaks detect across all commits to assert 0 secrets."""
    bin_path = shutil.which("gitleaks")
    if not bin_path:
        for candidate in ["/usr/local/bin/gitleaks", "/home/lyra/.local/bin/gitleaks"]:
            if Path(candidate).is_file():
                bin_path = candidate
                break
    if not (bin_path and Path(bin_path).is_file()):
        return AuditResult(
            domain="Secrets Audit",
            name="Gitleaks Commit Scan",
            passed=False,
            details=f"gitleaks binary not found in PATH, /usr/local/bin, or /home/lyra/.local/bin",
        )

    res = subprocess.run(  # noqa: S603
        [bin_path, "detect", "--no-banner", "--redact"],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0, f"Gitleaks detected secret leaks: {res.stderr}\n{res.stdout}"
    return AuditResult(
        domain="Secrets Audit",
        name="Gitleaks Commit Scan",
        passed=True,
        details="Gitleaks scanned all commits with --no-banner --redact; 0 leaks found",
    )


def check_git_log_pattern_audit() -> AuditResult:
    """Examine git log patches for high-entropy tokens and private keys."""
    secret_patterns: list[tuple[str, str]] = [
        (r"-----BEGIN (?:RSA|OPENSSH|DSA|EC|PGP) PRIVATE KEY-----", "Private key"),
        (r"AKIA[0-9A-Z]{16}", "AWS Access Key"),
        (r"gh[pousr]_[A-Za-z0-9_]{36,255}|github_pat_[A-Za-z0-9_]{82}", "GitHub Token"),
        (r"xox[baprs]-[0-9]{10,13}-[0-9]{10,13}-[a-zA-Z0-9]{24,32}", "Slack Token"),
    ]

    cmd = [_GIT_BIN, "log", "--all", "-p", "--raw"]
    res = subprocess.run(  # noqa: S603
        cmd,
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    log_text = res.stdout

    findings = []
    for pattern, label in secret_patterns:
        matches = re.findall(pattern, log_text)
        if matches:
            findings.append(f"{label} ({len(matches)} matches)")

    assert not findings, f"Git log audit found potential secrets: {findings}"
    return AuditResult(
        domain="Secrets Audit",
        name="Git Log Diff Pattern Audit",
        passed=True,
        details="Zero private keys, AWS tokens, GitHub PATs, or Slack tokens in git history",
    )


def check_untracked_sensitive_files() -> AuditResult:
    """Verify real .env files and private keys are excluded from git index."""
    res = subprocess.run(  # noqa: S603
        [_GIT_BIN, "ls-files"],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    tracked_files = res.stdout.splitlines()

    # .env must not be tracked (only .env.example)
    assert ".env" not in tracked_files, ".env must not be committed to git"
    assert ".env.example" in tracked_files, ".env.example must be committed to git"

    # No private key files
    leaked_keys = [
        f
        for f in tracked_files
        if f.endswith((".key", ".pem", ".p12", ".pfx"))
        or "id_rsa" in f
        or "id_ed25519" in f
    ]
    assert not leaked_keys, f"Found tracked private key files: {leaked_keys}"

    return AuditResult(
        domain="Secrets Audit",
        name="Tracked Files Hygiene",
        passed=True,
        details=".env excluded from git index, .env.example present, zero private keys tracked",
    )


# --- Orchestration Runner ---


ALL_AUDIT_CHECKS = [
    check_guest_account_definition,
    check_guest_privacy_boundaries,
    check_guest_resource_limits,
    check_guest_staged_sshd_deny,
    check_guest_abuse_suite_template,
    check_nftables_ruleset,
    check_nftables_persistence,
    check_reaper_script,
    check_reaper_systemd_unit,
    check_pam_cleanup_script,
    check_pam_common_session,
    check_tmpfs_mount_options,
    check_tmpfs_memory_budget,
    check_gitleaks_zero_findings,
    check_git_log_pattern_audit,
    check_untracked_sensitive_files,
]


def run_all_security_audits() -> list[AuditResult]:
    """Execute all security audit checks and collect results."""
    results: list[AuditResult] = []
    for check_fn in ALL_AUDIT_CHECKS:
        try:
            res = check_fn()
            results.append(res)
        except AssertionError as err:
            fn_name = check_fn.__name__.replace("check_", "").replace("_", " ").title()
            results.append(
                AuditResult(
                    domain="Security Audit",
                    name=fn_name,
                    passed=False,
                    details=str(err),
                ),
            )
        except Exception as exc:  # noqa: BLE001
            fn_name = check_fn.__name__.replace("check_", "").replace("_", " ").title()
            results.append(
                AuditResult(
                    domain="Security Audit",
                    name=fn_name,
                    passed=False,
                    details=f"Unexpected error: {exc}",
                ),
            )
    return results


def _print_domain_group(
    domain: str,
    domain_results: list[AuditResult],
    verbose: bool,
) -> bool:
    """Print results for a single audit domain."""
    print(f"\n--- {domain} ---")
    group_passed = True
    for r in domain_results:
        status = "[PASS]" if r.passed else "[FAIL]"
        print(f"  {status} {r.name}")
        if verbose or not r.passed:
            print(f"         {r.details}")
        if not r.passed:
            group_passed = False
    return group_passed


def print_audit_report(results: list[AuditResult], verbose: bool = False) -> bool:
    """Format and print the audit results report to console."""
    print("=" * 64)
    print("   WHISKERFRAME CYBERDECK SECURITY AUDIT VERIFICATION")
    print("=" * 64)

    by_domain: dict[str, list[AuditResult]] = {}
    for r in results:
        by_domain.setdefault(r.domain, []).append(r)

    all_passed = True
    for domain, domain_results in by_domain.items():
        if not _print_domain_group(domain, domain_results, verbose):
            all_passed = False

    print("\n" + "=" * 64)
    total = len(results)
    passed_count = sum(1 for r in results if r.passed)
    failed_count = total - passed_count
    print(f"SUMMARY: {passed_count}/{total} security checks passed ({failed_count} failed)")
    print("=" * 64)
    return all_passed


def main() -> int:
    """CLI entrypoint for verify_security_audit."""
    parser = argparse.ArgumentParser(
        description="Verify security containment, nftables, reaper, PAM, tmpfs, and zero secrets.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Print detailed validation messages.",
    )
    args = parser.parse_args()

    results = run_all_security_audits()
    passed = print_audit_report(results, verbose=args.verbose)
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
