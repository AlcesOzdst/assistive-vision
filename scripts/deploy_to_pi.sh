#!/usr/bin/env bash
set -Eeuo pipefail

usage() {
    cat <<'EOF'
Usage:
  ./scripts/deploy_to_pi.sh PI_USER PI_HOST MODEL_PATH

Example:
  ./scripts/deploy_to_pi.sh pi 192.168.1.80 ./yolov8n.pt

Run this from the project root on the laptop. The laptop camera server is
intentionally not copied to the Pi; it remains on the laptop.
EOF
}

if [[ $# -ne 3 ]]; then
    usage >&2
    exit 2
fi

PI_USER="$1"
PI_HOST="$2"
MODEL_PATH="$3"
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

echo "Creating ${REMOTE_DIR} on ${PI_HOST}..."
if ! ssh "${PI_USER}@${PI_HOST}" "true"; then
    echo "Error: cannot reach ${PI_USER}@${PI_HOST} over SSH." >&2
    echo "Confirm that the Pi is powered on and use its current IP address." >&2
    exit 1
fi

if ! ssh "${PI_USER}@${PI_HOST}" "sudo -n true" 2>/dev/null; then
    echo "Error: passwordless sudo is not currently authorized on the Pi." >&2
    echo "SSH into the Pi and run 'sudo -v' once, then rerun this script." >&2
    exit 1
fi

ssh "${PI_USER}@${PI_HOST}" "mkdir -p '${REMOTE_DIR}'"

echo "Copying Pi-side application files..."
scp -r \
    "${PROJECT_DIR}/src" \
    "${PROJECT_DIR}/pyproject.toml" \
    "${MODEL_PATH}" \
    "${PI_USER}@${PI_HOST}:${REMOTE_DIR}/"

echo "Installing Raspberry Pi dependencies..."
ssh "${PI_USER}@${PI_HOST}" "PI_EXTRA='${PI_EXTRA}' bash -s" <<'REMOTE_SETUP'
set -Eeuo pipefail
cd "$HOME/assistive-vision"

if ! command -v python3 >/dev/null 2>&1; then
    echo "python3 is required. Install it with: sudo apt update && sudo apt install -y python3"
    exit 1
fi

if ! python3 -m venv --help >/dev/null 2>&1; then
    echo "Installing Python virtual-environment support..."
    sudo -n apt update
    sudo -n apt install -y python3-venv python3-pip
fi

if [[ "${PI_EXTRA}" == "pi" ]]; then
    sudo -n apt update
    sudo -n apt install -y python3-opencv python3-numpy espeak-ng libspa-0.2-bluetooth pipewire-alsa
    systemctl --user restart pipewire wireplumber 2>/dev/null || true
fi

if [[ ! -d .venv ]]; then
    if [[ "${PI_EXTRA}" == "pi" ]]; then
        python3 -m venv --system-site-packages .venv
    else
        python3 -m venv .venv
    fi
fi

source .venv/bin/activate
python -m pip install -e ".[${PI_EXTRA}]"
python -m assistive_vision --demo --scans 3
REMOTE_SETUP

echo
echo "Deployment complete."
echo
echo "1. On the laptop, start the camera stream:"
echo "   python tools/laptop_camera_server.py --camera 0 --port 8765"
echo
echo "2. Find the laptop IPv4 address with 'ipconfig'."
echo
echo "3. On the Pi, run:"
echo "   ssh ${PI_USER}@${PI_HOST}"
echo "   cd ${REMOTE_DIR}"
echo "   source .venv/bin/activate"
echo "   python -m assistive_vision --stream-url http://LAPTOP_IP:8765/video --model ./${MODEL_NAME} --speak --interval 5"
