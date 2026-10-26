#!/usr/bin/env python3
"""Cross-platform laptop-to-Pi deployment tool.

Works on ANY laptop OS: Windows, macOS, and Linux.
Requires only standard Python 3 and native ssh/scp (preinstalled on Windows 10/11, macOS, and Linux).

Usage:
    python tools/deploy_to_pi.py [PI_USER] [PI_HOST] [MODEL_PATH]
    python tools/deploy_to_pi.py pi 172.17.4.80 ./yolov8n.onnx
    python tools/deploy_to_pi.py    (interactive mode)
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys


def find_project_root() -> Path:
    """Locate the repository root directory."""
    here = Path(__file__).resolve().parent
    if (here.parent / "pyproject.toml").is_file():
        return here.parent
    return Path.cwd()


def check_tool(name: str) -> bool:
    """Verify an executable is present in PATH."""
    return shutil.which(name) is not None


def run_cmd(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    """Execute a subprocess command with clean output."""
    return subprocess.run(cmd, check=check, text=True)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Deploy assistive-vision to a Raspberry Pi from any laptop (Windows/macOS/Linux)."
    )
    parser.add_argument("pi_user", nargs="?", default="", help="Raspberry Pi username (default: pi)")
    parser.add_argument("pi_host", nargs="?", default="", help="Raspberry Pi IP address or hostname")
    parser.add_argument(
        "model_path",
        nargs="?",
        default="",
        help="Path to YOLO model (e.g., ./yolov8n.onnx)",
    )
    args = parser.parse_args()

    project_root = find_project_root()

    print("\n" + "=" * 65)
    print("  🚀 ASSISTIVE VISION — UNIVERSAL PI DEPLOYMENT TOOL")
    print("=" * 65)
    print(f"Project root: {project_root}")
    print(f"Laptop OS:    {sys.platform} ({os.name})\n")

    # 1. Check tools
    for tool in ("ssh", "scp"):
        if not check_tool(tool):
            print(f"❌ Error: Required command '{tool}' was not found in PATH.")
            if sys.platform == "win32":
                print("   On Windows: Open Settings -> Apps -> Optional Features -> Add 'OpenSSH Client'.")
            sys.exit(1)

    # 2. Collect arguments (interactive if missing)
    pi_user = args.pi_user.strip()
    if not pi_user:
        entered = input("Enter Raspberry Pi username [default: pi]: ").strip()
        pi_user = entered or "pi"

    pi_host = args.pi_host.strip()
    if not pi_host:
        entered = input("Enter Raspberry Pi IP address (e.g., 172.17.4.80): ").strip()
        if not entered:
            print("❌ Error: Raspberry Pi IP address is required.")
            return 1
        pi_host = entered

    model_arg = args.model_path.strip()
    if not model_arg:
        default_model = project_root / "yolov8n.onnx"
        if default_model.is_file():
            entered = input(f"Enter model path [default: {default_model.name}]: ").strip()
            model_path = Path(entered) if entered else default_model
        else:
            entered = input("Enter model path (e.g. ./yolov8n.onnx): ").strip()
            model_path = Path(entered)
    else:
        model_path = Path(model_arg)

    if not model_path.is_absolute():
        candidate = project_root / model_path
        if candidate.is_file():
            model_path = candidate

    if not model_path.is_file():
        print(f"❌ Error: Model file not found at: {model_path}")
        return 1

    remote_dir = f"/home/{pi_user}/assistive-vision"
    remote_target = f"{pi_user}@{pi_host}"

    print(f"\n📡 Target:   {remote_target}:{remote_dir}")
    print(f"📦 Model:    {model_path} ({model_path.stat().st_size / (1024*1024):.1f} MB)\n")

    # 3. Test SSH connectivity
    print(f"🔍 Testing SSH connection to {remote_target}...")
    test_ssh = subprocess.run(["ssh", remote_target, "echo 'SSH Connected'"], capture_output=True, text=True)
    if test_ssh.returncode != 0:
        print(f"❌ Cannot connect to {remote_target} over SSH:")
        print(f"   {test_ssh.stderr.strip()}")
        print("\nSuggestions:")
        print("   1. Verify your Pi is powered on and both devices are on the same Wi-Fi.")
        print(f"   2. Verify the IP address: ping {pi_host}")
        print(f"   3. Ensure SSH is enabled on the Pi (raspi-config -> Interface Options -> SSH).")
        return 1
    print("✅ SSH connection successful.\n")

    # 4. Create remote directory
    subprocess.run(["ssh", remote_target, f"mkdir -p '{remote_dir}'"], check=True)

    # 5. Copy files
    print("📦 Synchronizing project files to Raspberry Pi...")
    files_to_copy = [
        project_root / "src",
        project_root / "tools",
        project_root / "scripts",
        project_root / "pyproject.toml",
        model_path,
    ]

    for opt_doc in ("README.md", "QUICKSTART.md"):
        doc_path = project_root / opt_doc
        if doc_path.is_file():
            files_to_copy.append(doc_path)

    scp_cmd = ["scp", "-r"] + [str(p) for p in files_to_copy] + [f"{remote_target}:{remote_dir}/"]
    print(f"   Copying {len(files_to_copy)} items via scp...")
    scp_res = subprocess.run(scp_cmd)
    if scp_res.returncode != 0:
        print("❌ Error: Failed to copy files to Pi.")
        return 1
    print("✅ Files copied successfully.\n")

    # 6. Remote Pi setup script
    is_onnx = model_path.name.lower().endswith(".onnx")
    pi_extra = "pi" if is_onnx else "camera"

    setup_script = f"""set -Eeuo pipefail
cd "{remote_dir}"

chmod +x scripts/*.sh tools/*.py 2>/dev/null || true

# Try installing system packages if apt is accessible
if sudo -n true 2>/dev/null; then
    sudo -n apt update -qq 2>/dev/null || true
    sudo -n apt install -y -qq python3-opencv python3-numpy espeak-ng libspa-0.2-bluetooth pipewire-alsa 2>/dev/null || true
fi

# Create virtual environment if missing
if [ ! -d .venv ]; then
    python3 -m venv --system-site-packages .venv 2>/dev/null || python3 -m venv .venv
fi

source .venv/bin/activate
pip install -e ".[{pi_extra}]" --no-warn-script-location -q 2>/dev/null || pip install -e ".[{pi_extra}]"

echo "PI_SETUP_COMPLETE"
"""

    print("⚙️  Configuring environment on Raspberry Pi...")
    remote_setup = subprocess.run(
        ["ssh", remote_target, setup_script],
        capture_output=True,
        text=True,
    )
    if "PI_SETUP_COMPLETE" in remote_setup.stdout:
        print("✅ Pi environment configured successfully!\n")
    else:
        print("⚠️  Remote configuration finished with notes:")
        if remote_setup.stdout:
            print(remote_setup.stdout.strip())
        if remote_setup.stderr:
            print(remote_setup.stderr.strip())

    # 7. Print next steps
    print("=" * 65)
    print("  🎉 DEPLOYMENT COMPLETE!")
    print("=" * 65)
    print("Next steps:")
    print("1. On this laptop, start the camera server:")
    print("   python tools/laptop_camera_server.py --camera 0 --port 8765\n")
    print(f"2. SSH into your Pi:")
    print(f"   ssh {remote_target}\n")
    print("3. Start the autonomous assistant on the Pi:")
    print("   cd assistive-vision")
    print("   source .venv/bin/activate")
    print("   python tools/run_pi.py --auto\n")
    print("   (Or for the interactive menu: python tools/run_pi.py)\n")
    print("=" * 65 + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
