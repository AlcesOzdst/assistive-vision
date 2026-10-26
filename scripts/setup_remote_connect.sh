#!/usr/bin/env bash
# Quick shell shortcut for setting up Raspberry Pi Connect
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd -- "${SCRIPT_DIR}/.." && pwd)"

python3 "${PROJECT_DIR}/tools/setup_remote_connect.py" "$@"
