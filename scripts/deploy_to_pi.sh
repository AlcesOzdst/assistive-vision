#!/usr/bin/env bash
set -Eeuo pipefail

usage() {
    cat <<'EOF'
Usage:
  ./scripts/deploy_to_pi.sh [PI_USER] [PI_HOST] [MODEL_PATH]

Example:
  ./scripts/deploy_to_pi.sh pi 172.17.4.80 ./yolov8n.onnx

Run this from the project root on the laptop (macOS / Linux / Git Bash).
For Windows PowerShell, run: .\scripts\deploy_to_pi.ps1
For any OS via Python:       python tools/deploy_to_pi.py
EOF
}

PI_USER="${1:-pi}"
PI_HOST="${2:-}"
MODEL_PATH="${3:-./yolov8n.onnx}"

if [[ -z "${PI_HOST}" ]]; then
    read -rp "Enter Raspberry Pi IP address: " PI_HOST
    if [[ -z "${PI_HOST}" ]]; then
        usage >&2
        exit 1
    fi
fi

REMOTE_DIR="/home/${PI_USER}/assistive-vision"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd -- "${SCRIPT_DIR}/.." && pwd)"

if [[ ! -f "${MODEL_PATH}" && -f "${PROJECT_DIR}/${MODEL_PATH}" ]]; then
    MODEL_PATH="${PROJECT_DIR}/${MODEL_PATH}"
fi

for command_name in ssh scp; do
    if ! command -v "${command_name}" >/dev/null 2>&1; then
        echo "Error: ${command_name} is required." >&2
        exit 1
    fi
done

if [[ ! -f "${MODEL_PATH}" ]]; then
    echo "Error: YOLO model not found: ${MODEL_PATH}" >&2
    exit 1
fi

MODEL_NAME="$(basename -- "${MODEL_PATH}")"
if [[ "${MODEL_NAME,,}" == *.onnx ]]; then
    PI_EXTRA="pi"
else
    PI_EXTRA="camera"
fi

echo "================================================================="
echo "  🚀 ASSISTIVE VISION — PI DEPLOYMENT"
echo "================================================================="
echo "Target: ${PI_USER}@${PI_HOST}:${REMOTE_DIR}"
echo "Model:  ${MODEL_PATH}"
echo

echo "Testing connection to ${PI_HOST} over SSH..."
if ! ssh "${PI_USER}@${PI_HOST}" "true" 2>/dev/null; then
    echo "Error: cannot reach ${PI_USER}@${PI_HOST} over SSH." >&2
    echo "Confirm that the Pi is powered on and check its IP address." >&2
    exit 1
fi

ssh "${PI_USER}@${PI_HOST}" "mkdir -p '${REMOTE_DIR}'"

echo "Copying application files and model to Pi..."
scp -r \
    "${PROJECT_DIR}/src" \
    "${PROJECT_DIR}/tools" \
    "${PROJECT_DIR}/scripts" \
    "${PROJECT_DIR}/pyproject.toml" \
    "${PROJECT_DIR}/README.md" \
    "${PROJECT_DIR}/QUICKSTART.md" \
    "${MODEL_PATH}" \
    "${PI_USER}@${PI_HOST}:${REMOTE_DIR}/"

echo "Configuring Raspberry Pi environment..."
ssh "${PI_USER}@${PI_HOST}" "PI_EXTRA='${PI_EXTRA}' bash -s" <<'REMOTE_SETUP'
set -Eeuo pipefail
cd "$HOME/assistive-vision"

chmod +x scripts/*.sh tools/*.py 2>/dev/null || true

# Try installing system packages if apt is available and sudo is permitted
if sudo -n true 2>/dev/null; then
    sudo -n apt update -qq 2>/dev/null || true
    sudo -n apt install -y -qq python3-opencv python3-numpy espeak-ng libspa-0.2-bluetooth pipewire-alsa 2>/dev/null || true
    systemctl --user restart pipewire wireplumber 2>/dev/null || true
fi

if [[ ! -d .venv ]]; then
    if [[ "${PI_EXTRA}" == "pi" ]]; then
        python3 -m venv --system-site-packages .venv 2>/dev/null || python3 -m venv .venv
    else
        python3 -m venv .venv
    fi
fi

source .venv/bin/activate
pip install -e ".[${PI_EXTRA}]" -q 2>/dev/null || pip install -e ".[${PI_EXTRA}]"
REMOTE_SETUP

echo
echo "================================================================="
echo "  🎉 DEPLOYMENT COMPLETE!"
echo "================================================================="
echo "1. On this laptop, start the camera stream:"
echo "   python tools/laptop_camera_server.py --camera 0 --port 8765"
echo
echo "2. SSH into the Pi:"
echo "   ssh ${PI_USER}@${PI_HOST}"
echo
echo "3. Run the autonomous assistant on the Pi:"
echo "   cd ${REMOTE_DIR}"
echo "   source .venv/bin/activate"
echo "   python tools/run_pi.py --auto"
echo
echo "   (Or interactive menu: python tools/run_pi.py)"
echo "================================================================="
