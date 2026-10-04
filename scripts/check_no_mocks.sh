#!/usr/bin/env bash
# Guard script: check for banned mocks and mock data fixtures
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

if command -v python3 &>/dev/null; then
    python3 "${SCRIPT_DIR}/check_no_mocks.py"
elif command -v python &>/dev/null; then
    python "${SCRIPT_DIR}/check_no_mocks.py"
else
    echo "Python is required to run check_no_mocks"
    exit 1
fi
