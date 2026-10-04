#!/usr/bin/env python3
"""Doctor script: validates Python version, dependencies, FFmpeg, fonts, paths, and environment."""

import sys
import os
import shutil
import importlib.metadata
from pathlib import Path

# Add backend to sys.path so config can be imported
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

def check_python():
    print(f"[*] Python version: {sys.version.split()[0]}")
    if sys.version_info < (3, 11):
        print("    [!] Error: Python 3.11+ is required.")
        return False
    print("    [+] Python version OK.")
    return True

def check_binaries():
    ok = True
    for binary in ["ffmpeg", "ffprobe"]:
        path = shutil.which(binary)
        if path:
            print(f"[*] {binary} found: {path}")
        else:
            print(f"    [!] Error: {binary} not found on PATH.")
            ok = False
    return ok

def check_fonts():
    font_dir = Path("backend/assets/fonts")
    if not font_dir.exists():
        print(f"    [!] Error: Font directory {font_dir} does not exist.")
        return False
    
    ttf_files = list(font_dir.glob("*.ttf")) + list(font_dir.glob("*.otf"))
    license_files = list(font_dir.glob("*OFL*.txt")) + list(font_dir.glob("LICENSE*"))
    print(f"[*] Found {len(ttf_files)} font file(s) and {len(license_files)} license file(s) in {font_dir}")
    if not ttf_files:
        print("    [!] Error: No font files (.ttf/.otf) found in font directory.")
        return False
    if not license_files:
        print("    [!] Error: No license files (OFL.txt) found in font directory.")
        return False
    return True

def check_directories():
    ok = True
    dirs = ["logs/api_calls", "logs/app", "storage"]
    for d in dirs:
        p = Path(d)
        p.mkdir(parents=True, exist_ok=True)
        test_file = p / ".doctor_write_test"
        try:
            test_file.write_text("ok", encoding="utf-8")
            test_file.unlink()
            print(f"[*] Writable directory: {p}")
        except Exception as e:
            print(f"    [!] Error writing to directory {p}: {e}")
            ok = False
    return ok

def check_packages():
    required_packages = [
        "fastapi",
        "uvicorn",
        "starlette",
        "pydantic",
        "pydantic_settings",
        "httpx",
        "edge_tts",
        "PIL",
        "numpy",
        "moviepy",
        "aiosqlite",
        "sqlalchemy",
        "structlog",
        "imagehash",
        "sse_starlette",
    ]
    ok = True
    for pkg in required_packages:
        try:
            # Package name vs import name mapping
            mod_name = "PIL" if pkg == "PIL" else pkg
            __import__(mod_name)
            print(f"[*] Module imported: {pkg}")
        except ImportError as e:
            print(f"    [!] Error: Missing required package '{pkg}': {e}")
            ok = False
    return ok

def check_settings():
    try:
        from app.config import get_settings
        settings = get_settings()
        print("[*] Settings loaded successfully.")
        print(f"    LLM Sequence: {settings.llm_models}")
        print(f"    Stock Providers: {settings.stock_providers}")
        print(f"    Gemini key configured: {settings.is_secret_set(settings.GEMINI_API_KEY)}")
        print(f"    Pexels key configured: {settings.is_secret_set(settings.PEXELS_API_KEY)}")
        print(f"    Pixabay key configured: {settings.is_secret_set(settings.PIXABAY_API_KEY)}")
        return True
    except Exception as e:
        print(f"    [!] Error loading settings: {e}")
        return False

def main():
    print("=" * 60)
    print("AutoShorts System Doctor")
    print("=" * 60)

    checks = [
        ("Python Version", check_python),
        ("FFmpeg / ffprobe", check_binaries),
        ("Fonts & Licenses", check_fonts),
        ("Storage & Logs Directories", check_directories),
        ("Python Packages", check_packages),
        ("Configuration & Settings", check_settings),
    ]

    results = []
    for name, fn in checks:
        print(f"\n--- Checking {name} ---")
        passed = fn()
        results.append((name, passed))

    print("\n" + "=" * 60)
    print("Summary:")
    all_passed = True
    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"  {name:30} : {status}")
        if not passed:
            all_passed = False
    print("=" * 60)

    if all_passed:
        print("All system doctor checks PASSED!")
        return 0
    else:
        print("Doctor detected issues. Please check the log above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
