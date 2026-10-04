#!/usr/bin/env bash
# Guard script: check for secrets, key patterns, and NEXT_PUBLIC leaks
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

if command -v python3 &>/dev/null; then
    python3 "${SCRIPT_DIR}/check_secrets.py"
elif command -v python &>/dev/null; then
    python "${SCRIPT_DIR}/check_secrets.py"
else
    echo "Python is required to run check_secrets"
    exit 1
fi
