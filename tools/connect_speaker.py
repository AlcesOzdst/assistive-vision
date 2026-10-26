#!/usr/bin/env python3
"""Interactive Bluetooth Speaker Setup Wizard for Raspberry Pi.

Automates the entire Bluetooth pairing, audio profile registration,
connection, and audio sink configuration process so users don't have
to struggle with manual bluetoothctl commands or profile errors.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "assistive_vision"
CONFIG_FILE = CONFIG_DIR / "speaker.json"


def run_cmd(cmd: list[str] | str, check: bool = False, shell: bool = False) -> subprocess.CompletedProcess[str]:
    """Run a shell or subprocess command and return the result."""
    return subprocess.run(
        cmd,
        shell=shell,
        check=check,
        text=True,
        capture_output=True,
    )


def print_banner() -> None:
    print("=" * 65)
    print("      🔊 ASSISTIVE VISION — BLUETOOTH SPEAKER WIZARD       ")
    print("=" * 65)
    print("This wizard will pair, configure, and test your Bluetooth speaker")
    print("automatically, handling all audio drivers and profile settings.")
    print("=" * 65 + "\n")


def check_and_install_dependencies() -> None:
    """Ensure required system packages and bluetooth tools exist without blocking on apt."""
    print("🔍 [1/4] Checking audio drivers and Bluetooth stack...")
    
    if not shutil.which("bluetoothctl"):
        print("   ❌ Error: bluetoothctl not found. Please install bluez.")
        sys.exit(1)

    if not shutil.which("espeak-ng") and not shutil.which("espeak"):
        print("   ⚠️ Note: espeak-ng not detected. Speech test may be silent.")
    else:
        print("   ✅ Bluetooth and audio drivers ready.")


def fix_audio_stack() -> None:
    """Restart bluetooth and PipeWire/WirePlumber to register A2DP profiles."""
    print("🔄 [2/4] Initializing Bluetooth and PipeWire audio services...")
    
    # Enable linger so user audio services stay active across SSH logouts
    user = os.environ.get("USER", "pi")
    run_cmd(f"sudo loginctl enable-linger {user}", shell=True)
    
    # Unblock rfkill
    run_cmd("sudo rfkill unblock all", shell=True)
    
    # Restart Bluetooth daemon
    run_cmd("sudo systemctl restart bluetooth", shell=True)
    time.sleep(1)
    
    # Restart PipeWire user audio stack
    run_cmd("systemctl --user restart pipewire pipewire-pulse wireplumber 2>/dev/null", shell=True)
    time.sleep(1.5)
    print("   ✅ Audio endpoints registered with Bluetooth.")


def get_saved_speaker() -> tuple[str | None, str | None]:
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, encoding="utf-8") as f:
                data = json.load(f)
                return data.get("mac"), data.get("name")
        except Exception:
            return None, None
    return None, None


def save_speaker(mac: str, name: str) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump({"mac": mac, "name": name}, f)


def scan_bluetooth_devices(duration: int = 8) -> list[tuple[str, str]]:
    """Scan for nearby Bluetooth devices and return a list of (mac, name)."""
    print(f"\n📡 [3/4] Scanning for Bluetooth devices ({duration} seconds)...")
    print("   👉 Make sure your speaker is in PAIRING MODE now!")
    print("   👉 (Disconnect it from your phone/laptop first)")

    try:
        proc = subprocess.Popen(
            ["bluetoothctl"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        # Turn power on and start scanning
        proc.stdin.write("power on\nscan on\n")
        proc.stdin.flush()

        for remaining in range(duration, 0, -1):
            sys.stdout.write(f"\r   Scanning... {remaining}s ")
            sys.stdout.flush()
            time.sleep(1)
        sys.stdout.write("\r   Scan complete!                   \n")

        # Request devices list and exit
        proc.stdin.write("devices\nexit\n")
        proc.stdin.flush()
        out, _ = proc.communicate(timeout=5)
    except Exception as exc:
        print(f"Error during scan: {exc}")
        out = ""

    devices: dict[str, str] = {}
    mac_pattern = re.compile(r"Device\s+([0-9A-Fa-f:]{17})\s+(.+)")

    for line in out.splitlines():
        match = mac_pattern.search(line)
        if match:
            mac = match.group(1).upper()
            name = match.group(2).strip()
            # If not a generic MAC-like name or already have a better name
            if mac not in devices or not devices[mac].replace("-", ":").upper() == mac:
                devices[mac] = name

    # Sort so named devices appear first
    sorted_devices = sorted(
        devices.items(),
        key=lambda item: (
            item[1].replace("-", ":").upper() == item[0],  # False (named) comes first
            item[1].lower(),
        ),
    )
    return [(mac, name) for mac, name in sorted_devices]


def pair_and_connect(mac: str, name: str) -> bool:
    """Pair, trust, and connect to a device via bluetoothctl."""
    print(f"\n🔗 Connecting to {name} ({mac})...")

    commands = [
        f"pair {mac}",
        f"trust {mac}",
        f"connect {mac}",
        "exit",
    ]

    try:
        proc = subprocess.Popen(
            ["bluetoothctl"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        out, err = proc.communicate(input="\n".join(commands) + "\n", timeout=25)
    except Exception as exc:
        print(f"❌ Subprocess error: {exc}")
        return False

    if "Connection successful" in out or "Connected: yes" in out:
        print(f"   🎉 Successfully connected to {name}!")
        save_speaker(mac, name)
        return True

    if "br-connection-profile-unavailable" in out:
        print("   ⚠️ Audio profile endpoint was missing. Applying auto-recovery...")
        fix_audio_stack()
        time.sleep(2)
        # Retry connect once
        retry = run_cmd(f"bluetoothctl connect {mac}", shell=True)
        if "Connection successful" in retry.stdout:
            print(f"   🎉 Recovered & successfully connected to {name}!")
            save_speaker(mac, name)
            return True

    print(f"❌ Failed to connect to {name}.")
    print(f"Details:\n{out}")
    return False


def set_default_sink_and_test() -> None:
    """Set the Bluetooth device as the default audio sink and test speech."""
    print("\n🔊 [4/4] Testing audio output through your speaker...")
    time.sleep(2)

    # Detect WirePlumber sink ID for Bluetooth
    wp_out = run_cmd("wpctl status", shell=True).stdout
    sink_id = None
    in_sinks = False
    for line in wp_out.splitlines():
        if "Sinks:" in line:
            in_sinks = True
            continue
        if in_sinks and ("Sink endpoints:" in line or "Sources:" in line or "Filters:" in line or "Streams:" in line):
            break
        if in_sinks and ("bluez" in line.lower() or "delight" in line.lower() or "speaker" in line.lower() or "headset" in line.lower()):
            match = re.search(r"│\s*\*?\s*(\d+)\.", line)
            if match:
                sink_id = match.group(1)
                break

    if sink_id:
        run_cmd(f"wpctl set-default {sink_id}", shell=True)
        print(f"   Set default audio sink to WirePlumber ID [{sink_id}].")

    # Play test announcement
    test_msg = "Hello! Your Bluetooth speaker is connected and ready for assistive vision."
    print(f'   Speaking: "{test_msg}"')
    if shutil.which("espeak-ng"):
        run_cmd(f'espeak-ng -s 145 "{test_msg}"', shell=True)
    elif shutil.which("espeak"):
        run_cmd(f'espeak -s 145 "{test_msg}"', shell=True)
    else:
        print("   (espeak not found; skipped speech playback)")

    print("\n" + "=" * 65)
    print("🎉 SUCCESS! Your speaker is paired and set as default audio.")
    print("=" * 65)


def main() -> int:
    print_banner()
    check_and_install_dependencies()
    fix_audio_stack()

    saved_mac, saved_name = get_saved_speaker()

    while True:
        options = []
        if saved_mac:
            options.append((saved_mac, f"{saved_name} [Last Connected]"))

        print("\nChoose an option:")
        if saved_mac:
            print(f"  [0] Quick Reconnect to: {saved_name} ({saved_mac})")
        print("  [1] Scan for Bluetooth speakers")
        print("  [q] Quit")

        choice = input("\nEnter choice: ").strip().lower()

        if choice == "q":
            return 0
        if choice == "0" and saved_mac:
            if pair_and_connect(saved_mac, saved_name or "Speaker"):
                set_default_sink_and_test()
                break
            continue
        if choice == "1":
            devices = scan_bluetooth_devices(duration=8)
            if not devices:
                print("⚠️ No Bluetooth devices found. Make sure the speaker is in pairing mode and not connected to your phone!")
                continue

            print("\nFound Devices:")
            for idx, (mac, name) in enumerate(devices, start=1):
                star = "⭐ " if name.replace("-", ":").upper() != mac else "   "
                print(f"  [{idx:2d}] {star}{name} ({mac})")

            sel = input("\nEnter device number to pair & connect (or 'r' to rescan): ").strip().lower()
            if sel == "r":
                continue
            try:
                sel_idx = int(sel) - 1
                if 0 <= sel_idx < len(devices):
                    target_mac, target_name = devices[sel_idx]
                    if pair_and_connect(target_mac, target_name):
                        set_default_sink_and_test()
                        break
                else:
                    print("Invalid selection number.")
            except ValueError:
                print("Invalid input.")
        else:
            print("Invalid choice.")

    # Offer to run assistive vision immediately
    print("\nWould you like to launch Assistive Vision now?")
    laptop_ip = input("Enter your Laptop's Wi-Fi IP address (or press Enter to skip): ").strip()
    if laptop_ip:
        cmd = [
            sys.executable,
            "-m",
            "assistive_vision",
            "--stream-url",
            f"http://{laptop_ip}:8765/video",
            "--model",
            "yolov8n.onnx",
            "--speak",
        ]
        print(f"\n🚀 Running: {' '.join(cmd)}\n")
        subprocess.run(cmd)

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\nExiting setup wizard.")
        sys.exit(0)
