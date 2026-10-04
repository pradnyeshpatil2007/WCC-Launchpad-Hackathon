#!/usr/bin/env python3
import sys
from pathlib import Path
root_script = Path(__file__).resolve().parent.parent.parent / "scripts" / "doctor.py"
if root_script.exists():
    import runpy
    runpy.run_path(str(root_script), run_name="__main__")
else:
    print(f"Error: Could not find {root_script}")
    sys.exit(1)
