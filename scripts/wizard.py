# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "typer",
#     "rich",
#     "questionary",
#     "pydantic",
#     "pyyaml",
#     "python-dotenv",
# ]
# ///

import os
import re
import sys
import yaml
import tempfile
import subprocess
from pathlib import Path
from typing import List, Optional, Tuple

import typer
import questionary
from rich.console import Console

console = Console()
app = typer.Typer(help="Whiskerframe Setup Wizard")

ENV_FILE = Path(".env")
ENV_EXAMPLE = Path(".env.example")
YAML_FILE = Path(".whiskerframe.yaml")
YAML_EXAMPLE = Path(".whiskerframe.example.yaml")
VAULT_FILE = Path("ansible/host_vars/cyberdeck/vault.yml")
VAULT_PASS = Path(os.path.expanduser("~/.config/whiskerframe/vault-pass"))

def represents_private_key(content: str) -> bool:
    if re.search(r"BEGIN .* PRIVATE " + "KEY", content):
        return True
    return False

def validate_ssh_key(content: str) -> Tuple[bool, str, str]:
    if represents_private_key(content):
        return False, "", "Rejected: Input contains a private key (BEGIN ... PRIV KEY)."
    
    with tempfile.NamedTemporaryFile(mode="w", delete=False) as tmp:
        tmp.write(content)
        tmp_name = tmp.name
    
    try:
        # Run ssh-keygen -l -f
        result = subprocess.run(["ssh-keygen", "-l", "-f", tmp_name], capture_output=True, text=True)
        if result.returncode != 0:
            return False, "", "Invalid SSH public key format."
        
        fingerprint = result.stdout.strip()
        
        # Dedupe/strip junk
        parts = content.strip().split()
        if len(parts) >= 2:
            clean_key = f"{parts[0]} {parts[1]}"
            if len(parts) > 2:
                clean_key += f" {parts[2]}"
        else:
            clean_key = content.strip()
            
        return True, clean_key, fingerprint
    finally:
        os.remove(tmp_name)

def encrypt_to_vault(key: str, value: str):
    if not VAULT_PASS.exists():
        console.print("[red]Error: Vault password file not found.[/red]")
        sys.exit(1)
        
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    
    # Decrypt if exists
    vault_data = {}
    if VAULT_FILE.exists():
        res = subprocess.run(["ansible-vault", "decrypt", str(VAULT_FILE), "--vault-password-file", str(VAULT_PASS)], capture_output=True)
        if res.returncode == 0:
            with open(VAULT_FILE, 'r') as f:
                vault_data = yaml.safe_load(f) or {}
                
    vault_data[key] = value
    
    with open(VAULT_FILE, 'w') as f:
        yaml.safe_dump(vault_data, f)
        
    subprocess.run(["ansible-vault", "encrypt", str(VAULT_FILE), "--vault-password-file", str(VAULT_PASS)], capture_output=True)

@app.command()
def run_wizard(
    dry_run: bool = typer.Option(False, "--dry-run", help="Dry run: print diff, do not write"),
    non_interactive: bool = typer.Option(False, "--non-interactive", help="Fail if interaction needed")
):
    console.print("[bold cyan]Starting Whiskerframe Setup Wizard[/bold cyan]")
    
    # Process ENV
    env_data = {}
    if ENV_FILE.exists():
        with open(ENV_FILE, 'r') as f:
            for line in f:
                if '=' in line and not line.startswith('#'):
                    k, v = line.strip().split('=', 1)
                    env_data[k] = v.strip('"\'')
    elif ENV_EXAMPLE.exists():
        with open(ENV_EXAMPLE, 'r') as f:
            for line in f:
                if '=' in line and not line.startswith('#'):
                    k, v = line.strip().split('=', 1)
                    if v == 'CHANGEME': v = ''
                    env_data[k] = v.strip('"\'')
                    
    # Process YAML
    yaml_data = {}
    if YAML_FILE.exists():
        with open(YAML_FILE, 'r') as f:
            yaml_data = yaml.safe_load(f) or {}
    elif YAML_EXAMPLE.exists():
        with open(YAML_EXAMPLE, 'r') as f:
            yaml_data = yaml.safe_load(f) or {}

    changes_yaml = False
    changes_env = False
    
    if not env_data.get("PI_HOST"):
        if non_interactive: sys.exit("PI_HOST is empty")
        ans = questionary.text("Enter PI_HOST:").ask()
        if ans: 
            env_data["PI_HOST"] = ans
            changes_env = True

    if not env_data.get("PI_USER"):
        if non_interactive: sys.exit("PI_USER is empty")
        ans = questionary.text("Enter PI_USER:").ask()
        if ans: 
            env_data["PI_USER"] = ans
            changes_env = True
            
    # Check NetBird secret
    vault_data = {}
    if VAULT_FILE.exists() and VAULT_PASS.exists():
        # Decrypt to check
        subprocess.run(["ansible-vault", "decrypt", str(VAULT_FILE), "--vault-password-file", str(VAULT_PASS)], capture_output=True)
        with open(VAULT_FILE, 'r') as f:
            vault_data = yaml.safe_load(f) or {}
        subprocess.run(["ansible-vault", "encrypt", str(VAULT_FILE), "--vault-password-file", str(VAULT_PASS)], capture_output=True)
        
    if not vault_data.get("netbird_setup_key"):
        if not non_interactive:
            ans = questionary.password("Enter NetBird Setup Key (will be saved encrypted in vault):").ask()
            if ans:
                if not dry_run:
                    encrypt_to_vault("netbird_setup_key", ans)
                console.print("[green]NetBird setup key pending for vault via ansible-vault.[/green]")

    # SSH Keys mapping
    git_keys = vault_data.get('operator_git_public_key', '')
    if not git_keys:
        if not non_interactive:
            console.print("We need an SSH public key for the remote.")
            key_input = questionary.text("Path to .pub file OR pasted contents:").ask()
            if key_input:
                content = ""
                if Path(os.path.expanduser(key_input)).exists():
                    pt = Path(os.path.expanduser(key_input))
                    if not pt.name.endswith(".pub"):
                        # Ensure it doesn't parse as private
                        with open(pt, 'r') as f: content = f.read()
                        if represents_private_key(content):
                            console.print("[red]Rejected: File parses as a private key.[/red]")
                            content = ""
                    else:
                        with open(pt, 'r') as f: content = f.read()
                else:
                    content = key_input
                    
                if content:
                    valid, clean_k, fingerprint = validate_ssh_key(content)
                    if valid:
                        console.print(f"Validated key: {fingerprint}")
                        if not dry_run:
                            encrypt_to_vault("operator_git_public_key", clean_k)
                    else:
                        console.print(f"[red]{fingerprint}[/red]")
                        
    # CYD Port
    if 'cyd' in yaml_data and yaml_data['cyd'].get('port') == 'CHANGEME':
        if not non_interactive:
            ans = questionary.text("Enter CYD serial port (e.g. /dev/ttyUSB0):").ask()
            if ans:
                yaml_data['cyd']['port'] = ans
                changes_yaml = True
                
    if 'terminal' in yaml_data and yaml_data['terminal'].get('serial_port') == 'CHANGEME':
        if yaml_data.get('cyd', {}).get('port') != 'CHANGEME':
            yaml_data['terminal']['serial_port'] = yaml_data['cyd']['port']
            changes_yaml = True

    if dry_run:
        console.print("\n[bold yellow]DRY RUN: Proposed ENV modifications[/bold yellow]")
        for k,v in env_data.items(): console.print(f"{k}={v}")
        console.print("[bold yellow]DRY RUN: Proposed YAML modifications[/bold yellow]")
        console.print(yaml.safe_dump(yaml_data))
    else:
        if changes_env:
            with open(ENV_FILE, 'w') as f:
                for k,v in env_data.items(): f.write(f'{k}="{v}"\n')
            console.print("[green]Updated .env[/green]")
            
        if changes_yaml:
            with open(YAML_FILE, 'w') as f:
                yaml.safe_dump(yaml_data, f)
            console.print("[green]Updated .whiskerframe.yaml[/green]")

if __name__ == "__main__":
    app()
