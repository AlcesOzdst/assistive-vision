#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd -- "${SCRIPT_DIR}/.." && pwd)"

if [[ -f "${PROJECT_DIR}/.venv/bin/activate" ]]; then
    source "${PROJECT_DIR}/.venv/bin/activate"
fi

python3 "${PROJECT_DIR}/tools/run_pi.py" "$@"
