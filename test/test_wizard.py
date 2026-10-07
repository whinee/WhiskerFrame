import sys
import subprocess
import pytest
import tempfile
import os

from scripts.wizard import validate_ssh_key

def test_private_key_rejection():
    fake_private = "-----BEGIN RSA PRIVATE " + "KEY-----\nMIICXQIBAAKBgQDC...\n-----END RSA PRIVATE " + "KEY-----"
    valid, key, err = validate_ssh_key(fake_private)
    assert not valid
    assert "private key" in err.lower()

def test_public_key_validation():
    # Use a real format fake key
    fake_pub = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIK+WlG0w6Vp7I1y+kG6k4DqLcXw2G7/3z1q/wz5rP fake@test"
    valid, key, fingerprint = validate_ssh_key(fake_pub)
    assert valid
    assert key == fake_pub
    # Fingerprint should exist
    assert "fake@test" in fingerprint or "SHA256" in fingerprint
    
if __name__ == "__main__":
    pytest.main([__file__])
