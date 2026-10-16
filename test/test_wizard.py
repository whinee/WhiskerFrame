import pytest

from scripts.wizard import validate_ssh_key


def test_private_key_rejection():
    fake_private = (
        "-----BEGIN RSA PRIVATE "
        + "KEY-----\nMIICXQIBAAKBgQDC...\n-----END RSA PRIVATE "
        + "KEY-----"
    )
    valid, _key, err = validate_ssh_key(fake_private)
    assert not valid
    assert "private key" in err.lower()


def test_public_key_validation():
    # Use a real format fake key (valid 32-byte ed25519 pubkey wire format)
    fake_pub = (
        "ssh-ed25519 "
        "AAAAC3NzaC1lZDI1NTE5AAAAIEFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFB "
        "fake@test"
    )
    valid, key, fingerprint = validate_ssh_key(fake_pub)
    assert valid
    assert key == fake_pub
    # Fingerprint should exist
    assert "fake@test" in fingerprint or "SHA256" in fingerprint


if __name__ == "__main__":
    pytest.main([__file__])
