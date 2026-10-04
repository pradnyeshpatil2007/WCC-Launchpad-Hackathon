#!/usr/bin/env python3
"""Guard script: verifies no secrets, AIza... patterns, or secret-leaking NEXT_PUBLIC_* vars appear in files."""

import sys
import os
import re
from pathlib import Path

AIZA_PATTERN = re.compile(r"\bAIza[0-9A-Za-z_\-]{20,}\b")
NEXT_PUBLIC_SECRET_PATTERN = re.compile(r"NEXT_PUBLIC_[A-Z0-9_]*(?:KEY|SECRET|TOKEN)", re.IGNORECASE)

IGNORE_DIRS = {
    ".git",
    "node_modules",
    ".next",
    "__pycache__",
    ".pytest_cache",
    ".venv",
    "venv",
}

IGNORE_FILES = {
    ".env",
    ".env.example",
    "check_secrets.py",
    "check_secrets.sh",
    "01_AutoShorts_PRD.md",
    "02_AutoShorts_Frontend_Spec.md",
    "03_AutoShorts_Backend_Architecture_Spec.md",
    "IMPLEMENTATION_PLAN.md",
}

def load_configured_keys(env_path: Path) -> list[str]:
    keys = []
    if not env_path.exists():
        return keys
    
    for line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip().upper()
        v = v.strip().strip("'\"")
        # Only check variables that represent actual secret keys/tokens
        if any(term in k for term in ["KEY", "SECRET", "TOKEN", "PASSWORD"]):
            if v and not v.startswith("PASTE_") and not v.startswith("SET_") and len(v) >= 8:
                keys.append(v)
    return keys

def scan_files(root_path: Path, configured_keys: list[str]) -> list[str]:
    violations = []
    
    for root, dirs, files in os.walk(root_path):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        
        for f in files:
            if f in IGNORE_FILES or f.endswith((".env", ".tmp", ".log.swp")):
                continue
            
            file_path = Path(root) / f
            rel_path = file_path.relative_to(root_path)
            
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                
                # Check for Google API key patterns
                aiza_match = AIZA_PATTERN.search(content)
                if aiza_match:
                    violations.append(f"AIza key pattern detected in {rel_path}")
                
                # Check for NEXT_PUBLIC secret leaking vars
                np_match = NEXT_PUBLIC_SECRET_PATTERN.search(content)
                if np_match:
                    violations.append(f"Forbidden NEXT_PUBLIC secret var '{np_match.group(0)}' in {rel_path}")
                
                # Check for configured secret literal leak
                for secret in configured_keys:
                    if secret in content:
                        violations.append(f"Configured API key value found exposed in {rel_path}")
                        
            except Exception as e:
                # Binary files or unreadable files can be skipped
                pass

    return violations

def main():
    root = Path(__file__).resolve().parent.parent
    print(f"[*] Scanning for secret leaks at {root}...")
    
    env_file = root / "backend" / ".env"
    configured_keys = load_configured_keys(env_file)
    if configured_keys:
        print(f"[*] Checking against {len(configured_keys)} configured secrets from backend/.env")
    else:
        print("[*] No active secrets configured in backend/.env yet (placeholders present).")
        
    violations = scan_files(root, configured_keys)
    
    if violations:
        print("\n[!] SECRET LEAK DETECTED:")
        for v in violations:
            print(f"  - {v}")
        return 1
        
    print("[+] PASS: Zero secrets or forbidden patterns detected.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
