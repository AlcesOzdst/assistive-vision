#!/usr/bin/env python3
"""Raspberry Pi Connect (rpi-connect) Setup & Diagnostics Tool.

Installs, enables, and signs into official Raspberry Pi Connect so you can
access your Raspberry Pi remotely from anywhere in the world via web browser:
    https://connect.raspberrypi.com

Usage:
    python tools/setup_remote_connect.py
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys


def has_tool(name: str) -> bool:
    return shutil.which(name) is not None


def run_cmd(cmd: list[str], check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, check=check, text=True, capture_output=True)


def main() -> int:
    print("\n" + "=" * 65)
    print("  🌐 OFFICIAL RASPBERRY PI CONNECT (REMOTE ACCESS) SETUP")
    print("=" * 65 + "\n")

    # 1. Check if rpi-connect is installed
    if not has_tool("rpi-connect"):
        print("📦 Installing Raspberry Pi Connect...")
        # Prefer rpi-connect, fall back to rpi-connect-lite for headless
        install_res = subprocess.run(["sudo", "apt", "update"], check=False)
        install_res = subprocess.run(["sudo", "apt", "install", "-y", "rpi-connect"], check=False)
        if install_res.returncode != 0:
            print("   Retrying with headless package (rpi-connect-lite)...")
            subprocess.run(["sudo", "apt", "install", "-y", "rpi-connect-lite"], check=False)

    if not has_tool("rpi-connect"):
        print("❌ Could not install rpi-connect automatically via apt.")
        print("   Try running manually: sudo apt update && sudo apt install -y rpi-connect-lite")
        return 1

    # 2. Enable linger so the service stays active when not logged in
    user = os.environ.get("USER", "pi")
    print(f"⚙️  Enabling persistent background linger for user '{user}'...")
    subprocess.run(["sudo", "loginctl", "enable-linger", user], check=False)

    # 3. Enable and start user systemd service
    print("🚀 Starting Raspberry Pi Connect service...")
    subprocess.run(["systemctl", "--user", "daemon-reload"], check=False)
    subprocess.run(["systemctl", "--user", "enable", "--now", "rpi-connect"], check=False)

    # 4. Check status
    status_res = run_cmd(["rpi-connect", "status"])
    print(f"\n📊 Current Status:\n{status_res.stdout.strip() or status_res.stderr.strip()}\n")

    if "Signed in" in status_res.stdout and "yes" in status_res.stdout.lower():
        print("🎉 Raspberry Pi Connect is ALREADY signed in and active!")
        print("👉 You can connect anytime from: https://connect.raspberrypi.com\n")
        return 0

    # 5. Initiate sign-in flow
    print("=" * 65)
    print("  🔑 SIGN-IN & VERIFICATION")
    print("=" * 65)
    print("Requesting verification link from Raspberry Pi Connect...")
    signin_proc = subprocess.run(["rpi-connect", "signin"], check=False)

    print("\n" + "=" * 65)
    print("  👉 NEXT STEPS TO COMPLETE CONNECTION:")
    print("=" * 65)
    print("1. Open the URL shown above on your laptop or phone browser.")
    print("2. Sign in with (or create) your free Raspberry Pi ID.")
    print("3. Click 'Link device'.")
    print("4. Done! You can now access your Pi from anywhere in the world at:")
    print("   https://connect.raspberrypi.com")
    print("=" * 65 + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
