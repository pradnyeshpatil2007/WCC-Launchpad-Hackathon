#!/usr/bin/env python3
"""Guard script: verifies no mock libraries, fixtures, or fabricated data exist in codebase."""

import sys
import os
import re
from pathlib import Path

BANNED_PATTERNS = [
    r"\bunittest\.mock\b",
    r"\bpytest[-_]mock\b",
    r"\bresponses\b",
    r"\brespx\b",
    r"\bhttpretty\b",
    r"\bvcrpy\b",
    r"\bfaker\b",
    r"@faker-js",
    r"\bmsw\b",
    r"\bnock\b",
]

BANNED_DIRS = [
    "fixtures",
    "mock",
    "mocks",
    "fake",
    "fakes",
]

IGNORE_DIRS = {
    ".git",
    "node_modules",
    ".next",
    "__pycache__",
    ".pytest_cache",
    ".venv",
    "venv",
    "logs",
    "storage",
}

IGNORE_FILES = {
    "check_no_mocks.py",
    "check_no_mocks.sh",
    "01_AutoShorts_PRD.md",
    "02_AutoShorts_Frontend_Spec.md",
    "03_AutoShorts_Backend_Architecture_Spec.md",
    "IMPLEMENTATION_PLAN.md",
}

def scan_codebase(root_path: Path):
    violations = []
    
    # 1. Check directory names
    for root, dirs, files in os.walk(root_path):
        # Modify dirs in-place to skip ignored directories
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        
        current_dir_rel = Path(root).relative_to(root_path)
        for d in dirs:
            if d.lower() in BANNED_DIRS:
                violations.append(f"Banned fixture/mock directory found: {current_dir_rel / d}")
                
        # 2. Check file contents
        for f in files:
            if f in IGNORE_FILES:
                continue
            if f.endswith((".py", ".ts", ".tsx", ".js", ".jsx", ".json")):
                file_path = Path(root) / f
                try:
                    content = file_path.read_text(encoding="utf-8", errors="ignore")
                    for pattern in BANNED_PATTERNS:
                        match = re.search(pattern, content)
                        if match:
                            violations.append(f"Banned mock reference '{match.group(0)}' in {file_path.relative_to(root_path)}")
                except Exception as e:
                    violations.append(f"Could not read {file_path}: {e}")

    return violations

def main():
    root = Path(__file__).resolve().parent.parent
    print(f"[*] Scanning codebase for banned mocks at {root}...")
    violations = scan_codebase(root)
    
    if violations:
        print("\n[!] VIOLATIONS DETECTED (No-Mock Policy):")
        for v in violations:
            print(f"  - {v}")
        return 1
    
    print("[+] PASS: Zero mocks, fixtures, or fabricated data detected.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
