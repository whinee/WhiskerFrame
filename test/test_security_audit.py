"""
Pytest test suite for WhiskerFrame security audit verification.

Tests:
1. Guest containment sandbox: account definition, credentials, privacy boundaries,
   ulimits, staged sshd deny, abuse suite template.
2. Kernel nftables configuration: inet guest_isolation table, egress drop, persistence.
3. Process reaper daemon: 5s execution ceiling, login shell preservation, systemd unit.
4. Ephemeral PAM session cleanup: close_session wipe, open_session demo setup, seteuid hook.
5. Ephemeral tmpfs 8MB boundary: nodev/nosuid/mode=0700 options, 1.9% memory budget.
6. Secrets audit: gitleaks commit scan, git log pattern diff audit, tracked files hygiene.
"""

from __future__ import annotations

from scripts.verify_security_audit import (
    ALL_AUDIT_CHECKS,
    AuditResult,
    check_git_log_pattern_audit,
    check_gitleaks_zero_findings,
    check_guest_abuse_suite_template,
    check_guest_account_definition,
    check_guest_privacy_boundaries,
    check_guest_resource_limits,
    check_guest_staged_sshd_deny,
    check_nftables_persistence,
    check_nftables_ruleset,
    check_pam_cleanup_script,
    check_pam_common_session,
    check_reaper_script,
    check_reaper_systemd_unit,
    check_tmpfs_memory_budget,
    check_tmpfs_mount_options,
    check_untracked_sensitive_files,
    run_all_security_audits,
)


def test_guest_account_definition() -> None:
    """Assert guest account definition and credentials match security specs."""
    res = check_guest_account_definition()
    assert res.passed is True
    assert "SHA-512 crypt" in res.details


def test_guest_privacy_boundaries() -> None:
    """Assert /home/neko, /root, and NetworkManager connections locked to 0700."""
    res = check_guest_privacy_boundaries()
    assert res.passed is True
    assert "0700" in res.details


def test_guest_resource_limits() -> None:
    """Assert strict ulimits for guest user (nofile, fsize, core 0)."""
    res = check_guest_resource_limits()
    assert res.passed is True
    assert "core=0" in res.details


def test_guest_staged_sshd_deny() -> None:
    """Assert SSHD deny config is staged without live reload per Rule 3."""
    res = check_guest_staged_sshd_deny()
    assert res.passed is True
    assert "Rule 3" in res.details


def test_guest_abuse_suite_template() -> None:
    """Assert 11/11 abuse tests in test-guest-containment.sh.j2."""
    res = check_guest_abuse_suite_template()
    assert res.passed is True
    assert "11/11 abuse tests" in res.details


def test_nftables_ruleset() -> None:
    """Assert kernel-level nftables table and output chain drop rule."""
    res = check_nftables_ruleset()
    assert res.passed is True
    assert "skuid 'guest' counter drop" in res.details


def test_nftables_persistence() -> None:
    """Assert nftables drop-in parsing in nftables.conf and service enabled."""
    res = check_nftables_persistence()
    assert res.passed is True
    assert "nftables.service enabled" in res.details


def test_reaper_script() -> None:
    """Assert 5s process reaper script logic and login shell exclusion."""
    res = check_reaper_script()
    assert res.passed is True
    assert "5s wall-clock timeout" in res.details


def test_reaper_systemd_unit() -> None:
    """Assert cyberdeck-guest-reaper.service definition and restart policy."""
    res = check_reaper_systemd_unit()
    assert res.passed is True
    assert "Restart=always" in res.details


def test_pam_cleanup_script() -> None:
    """Assert PAM close_session wipe and open_session demo setup."""
    res = check_pam_cleanup_script()
    assert res.passed is True
    assert "close_session purges" in res.details


def test_pam_common_session() -> None:
    """Assert PAM configuration in common-session uses pam_exec.so seteuid."""
    res = check_pam_common_session()
    assert res.passed is True
    assert "seteuid" in res.details


def test_tmpfs_mount_options() -> None:
    """Assert tmpfs mount options: nodev, nosuid, size=8M, mode=0700."""
    res = check_tmpfs_mount_options()
    assert res.passed is True
    assert "nodev" in res.details
    assert "nosuid" in res.details


def test_tmpfs_memory_budget() -> None:
    """Assert 8MB tmpfs is <= 2% of RAM and protects earlyoom 50MB floor."""
    res = check_tmpfs_memory_budget()
    assert res.passed is True
    assert "earlyoom" in res.details


def test_gitleaks_zero_findings() -> None:
    """Assert Gitleaks scans all commits with 0 leaks found."""
    res = check_gitleaks_zero_findings()
    assert res.passed is True
    assert "0 leaks found" in res.details


def test_git_log_pattern_audit() -> None:
    """Assert zero private keys, AWS tokens, GitHub PATs in git log."""
    res = check_git_log_pattern_audit()
    assert res.passed is True
    assert "Zero private keys" in res.details


def test_untracked_sensitive_files() -> None:
    """Assert .env excluded from git index and zero private keys tracked."""
    res = check_untracked_sensitive_files()
    assert res.passed is True
    assert ".env excluded from git index" in res.details


def test_all_security_audits_pass() -> None:
    """Assert all 16 security audit checks pass without failure."""
    results: list[AuditResult] = run_all_security_audits()
    assert len(results) == len(ALL_AUDIT_CHECKS)
    failed = [r for r in results if not r.passed]
    assert not failed, f"Failed security checks: {[f.name for f in failed]}"
