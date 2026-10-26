#!/usr/bin/env bash
# Quick shell shortcut for configuring Pi Wi-Fi auto-connect
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd -- "${SCRIPT_DIR}/.." && pwd)"

sudo python3 "${PROJECT_DIR}/tools/setup_wifi.py" "$@"
