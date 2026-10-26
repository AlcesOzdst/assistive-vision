#!/usr/bin/env python3
"""Autonomous & Interactive Assistive Vision Runner for Raspberry Pi.

Handles the proven Bluetooth audio endpoint handshake, pairs/connects the
speaker, sets up audio routing, and starts real-time object detection
either 100% autonomously or via an interactive menu.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "assistive_vision"
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULT_CONFIG = {
    "speaker_mac": "BA:A6:58:A5:50:39",
    "speaker_name": "ZEB-DELIGHT",
    "laptop_ip": "172.17.4.137",
    "interval": 6.0,
    "repeat_interval": 45.0,
    "confidence": 0.20,
}


def run_cmd(cmd: str | list[str], check: bool = False, shell: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, check=check, shell=shell, text=True, capture_output=True)


def load_config() -> dict:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, encoding="utf-8") as f:
                data = json.load(f)
                merged = dict(DEFAULT_CONFIG)
                merged.update(data)
                return merged
        except Exception:
            pass
    return dict(DEFAULT_CONFIG)


def save_config(cfg: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)


def restart_audio_handshake() -> None:
    """The proven audio endpoint registration handshake."""
    print("🔄 [Handshake] Reloading Bluetooth and PipeWire audio services...")
    user = os.environ.get("USER", "pi")
    run_cmd(f"sudo loginctl enable-linger {user}")
    run_cmd("sudo rfkill unblock all")
    
    # 1. Stop conflicting pulseaudio if running
    run_cmd("systemctl --user stop pulseaudio pulseaudio.socket 2>/dev/null")
    run_cmd("systemctl --user disable pulseaudio 2>/dev/null")
    
    # 2. Restart system Bluetooth daemon
    run_cmd("sudo systemctl restart bluetooth")
    time.sleep(1)
    
    # 3. Restart PipeWire user audio stack
    run_cmd("systemctl --user restart pipewire pipewire-pulse wireplumber 2>/dev/null")
    run_cmd("systemctl --user restart pulseaudio 2>/dev/null")
    
    # 4. Wait for endpoints (/sep1, /sep2) to register on D-Bus
    time.sleep(2.5)
    print("   ✅ Endpoints ready.")


def connect_speaker(mac: str, name: str = "Speaker", force_repair: bool = False) -> bool:
    """Connect to speaker using the proven remove -> pair -> handshake -> connect flow."""
    print(f"\n🔗 Connecting to {name} ({mac})...")

    if force_repair:
        print("   ⏳ Resetting device state...")
        run_cmd(f"bluetoothctl remove {mac}")
        time.sleep(1)
        print("   ⏳ Pairing...")
        run_cmd(f"bluetoothctl pair {mac}")
        time.sleep(1)
        print("   ⏳ Trusting...")
        run_cmd(f"bluetoothctl trust {mac}")
        time.sleep(0.5)

    # Check info
    info = run_cmd(f"bluetoothctl info {mac}").stdout
    if "Paired: yes" not in info:
        print("   ⏳ Device not paired. Pairing now...")
        run_cmd(f"bluetoothctl pair {mac}")
        time.sleep(1)
        run_cmd(f"bluetoothctl trust {mac}")
        time.sleep(0.5)

    # 1. Execute audio handshake
    restart_audio_handshake()

    # 2. Connect
    print(f"   ⏳ Establishing audio connection to {mac}...")
    c_res = run_cmd(f"bluetoothctl connect {mac}").stdout

    if "Connection successful" in c_res or "Connected: yes" in c_res:
        print(f"   🎉 SUCCESS: Connected to {name} ({mac})!")
        return True

    if "br-connection-profile-unavailable" in c_res or "Failed" in c_res:
        print("   ⚠️ Retrying connection with fresh audio handshake...")
        run_cmd(f"bluetoothctl trust {mac}")
        restart_audio_handshake()
        retry_res = run_cmd(f"bluetoothctl connect {mac}").stdout
        if "Connection successful" in retry_res or "Connected: yes" in retry_res:
            print(f"   🎉 SUCCESS: Connected to {name} on retry!")
            return True

    # If still failed, full remove and re-pair flow
    print("   ⏳ Applying full reset (remove -> scan -> pair -> handshake -> connect)...")
    run_cmd(f"bluetoothctl remove {mac}")
    time.sleep(1)
    run_cmd(f"bluetoothctl pair {mac}")
    time.sleep(1.5)
    run_cmd(f"bluetoothctl trust {mac}")
    restart_audio_handshake()
    final_res = run_cmd(f"bluetoothctl connect {mac}").stdout

    if "Connection successful" in final_res or "Connected: yes" in final_res:
        print(f"   🎉 SUCCESS: Re-paired and connected to {name}!")
        return True

    print(f"❌ Connection failed:\n{final_res.strip()}")
    print("👉 If it says 'status 0x04': Turn your speaker OFF and back ON into pairing mode.")
    return False


def test_speech(message: str = "Audio connected successfully!") -> None:
    print(f"\n🔊 Speaking test: \"{message}\"...")
    # Route to default sink via WirePlumber
    wp_out = run_cmd("wpctl status").stdout
    for line in wp_out.splitlines():
        if "bluez" in line.lower() or "delight" in line.lower() or "speaker" in line.lower():
            match = re.search(r"│\s*\*?\s*(\d+)\.", line)
            if match:
                run_cmd(f"wpctl set-default {match.group(1)}")
                break

    if shutil.which("espeak-ng"):
        run_cmd(f'espeak-ng -s 145 "{message}"')
    elif shutil.which("espeak"):
        run_cmd(f'espeak -s 145 "{message}"')


def scan_devices(duration: int = 8) -> list[tuple[str, str]]:
    print(f"\n📡 Scanning for Bluetooth devices ({duration} seconds)...")
    print("   👉 Make sure your speaker is in PAIRING MODE now!")
    try:
        proc = subprocess.Popen(
            ["bluetoothctl"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        proc.stdin.write("power on\nscan on\n")
        proc.stdin.flush()

        for remaining in range(duration, 0, -1):
            sys.stdout.write(f"\r   Scanning... {remaining}s ")
            sys.stdout.flush()
            time.sleep(1)
        sys.stdout.write("\r   Scan complete!                   \n")

        proc.stdin.write("devices\nexit\n")
        proc.stdin.flush()
        out, _ = proc.communicate(timeout=5)
    except Exception as exc:
        print(f"Error: {exc}")
        out = ""

    devices: dict[str, str] = {}
    mac_pattern = re.compile(r"Device\s+([0-9A-Fa-f:]{17})\s+(.+)")
    for line in out.splitlines():
        match = mac_pattern.search(line)
        if match:
            mac = match.group(1).upper()
            name = match.group(2).strip()
            if mac not in devices or not devices[mac].replace("-", ":").upper() == mac:
                devices[mac] = name

    sorted_devs = sorted(
        devices.items(),
        key=lambda item: (item[1].replace("-", ":").upper() == item[0], item[1].lower()),
    )
    return [(mac, name) for mac, name in sorted_devs]


def launch_assistive_vision(cfg: dict) -> None:
    laptop_ip = cfg.get("laptop_ip", "172.17.4.137")
    cmd = [
        sys.executable,
        "-m",
        "assistive_vision",
        "--stream-url",
        f"http://{laptop_ip}:8765/video",
        "--model",
        "yolov8n.onnx",
        "--speak",
        "--confidence",
        str(cfg.get("confidence", 0.20)),
        "--interval",
        str(cfg.get("interval", 6.0)),
        "--repeat-interval",
        str(cfg.get("repeat_interval", 45.0)),
    ]
    print("\n" + "=" * 65)
    print(f"🚀 LAUNCHING ASSISTIVE VISION (Laptop: {laptop_ip})")
    print(f"   Interval: {cfg.get('interval')}s | Repeat: {cfg.get('repeat_interval')}s | Conf: {cfg.get('confidence')}")
    print("=" * 65 + "\n")
    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print("\n\nAssistive Vision stopped.")


def run_autonomous(cfg: dict, force_repair: bool = False) -> None:
    print("=" * 65)
    print("      🤖 AUTONOMOUS ASSISTIVE VISION STARTUP")
    print("=" * 65)
    mac = cfg["speaker_mac"]
    name = cfg.get("speaker_name", "Speaker")

    if connect_speaker(mac, name, force_repair=force_repair):
        test_speech("Speaker connected. Starting assistive vision.")
        launch_assistive_vision(cfg)
    else:
        print("\n❌ Autonomous connection failed.")
        print("👉 Falling back to interactive menu...")
        run_interactive(cfg)


def run_interactive(cfg: dict) -> None:
    while True:
        print("\n" + "=" * 65)
        print("         👁️ ASSISTIVE VISION — CONTROL PANEL")
        print("=" * 65)
        print(f"  • Speaker:     {cfg.get('speaker_name')} ({cfg.get('speaker_mac')})")
        print(f"  • Laptop IP:   {cfg.get('laptop_ip')}")
        print(f"  • Detection:   Interval: {cfg.get('interval')}s | Repeat: {cfg.get('repeat_interval')}s | Conf: {cfg.get('confidence')}")
        print("=" * 65)
        print("  [1] 🚀 Auto-Connect & Start Assistive Vision (1-Click)")
        print("  [2] 📡 Scan & Pair New Bluetooth Speaker")
        print("  [3] 🔄 Full Reset & Reconnect Speaker (Fix profile errors)")
        print("  [4] ⚙️ Change Laptop IP or Detection Interval")
        print("  [5] 🔊 Test Speaker Speech Output")
        print("  [6] 📶 Configure Wi-Fi Auto-Connect (e.g. SMJV)")
        print("  [q] Quit")

        choice = input("\nEnter choice [1-6, q]: ").strip().lower()

        if choice == "q":
            print("Exiting.")
            break
        elif choice == "1":
            if connect_speaker(cfg["speaker_mac"], cfg["speaker_name"]):
                test_speech("Speaker connected.")
                launch_assistive_vision(cfg)
        elif choice == "2":
            devs = scan_devices(duration=8)
            if not devs:
                print("⚠️ No devices found. Check pairing mode!")
                continue
            print("\nFound Devices:")
            for i, (m, n) in enumerate(devs, start=1):
                star = "⭐ " if n.replace("-", ":").upper() != m else "   "
                print(f"  [{i:2d}] {star}{n} ({m})")
            sel = input("\nEnter device number to connect (or 'r' to return): ").strip().lower()
            if sel != "r":
                try:
                    idx = int(sel) - 1
                    if 0 <= idx < len(devs):
                        cfg["speaker_mac"], cfg["speaker_name"] = devs[idx]
                        save_config(cfg)
                        if connect_speaker(cfg["speaker_mac"], cfg["speaker_name"], force_repair=True):
                            test_speech("Speaker connected.")
                            launch_assistive_vision(cfg)
                except ValueError:
                    print("Invalid selection.")
        elif choice == "3":
            if connect_speaker(cfg["speaker_mac"], cfg["speaker_name"], force_repair=True):
                test_speech("Audio re-connected successfully.")
        elif choice == "4":
            new_ip = input(f"Enter Laptop IP [{cfg['laptop_ip']}]: ").strip()
            if new_ip:
                cfg["laptop_ip"] = new_ip
            new_int = input(f"Enter announcement interval in seconds [{cfg['interval']}]: ").strip()
            if new_int:
                try:
                    cfg["interval"] = float(new_int)
                except ValueError:
                    pass
            new_conf = input(f"Enter confidence threshold (0.10 to 0.50) [{cfg['confidence']}]: ").strip()
            if new_conf:
                try:
                    cfg["confidence"] = float(new_conf)
                except ValueError:
                    pass
            save_config(cfg)
            print("✅ Settings saved!")
        elif choice == "5":
            test_speech("Test audio: one two three, assistive vision is ready.")
        elif choice == "6":
            script_path = Path(__file__).parent / "setup_wifi.py"
            subprocess.run([sys.executable, str(script_path)])
        else:
            print("Invalid option.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Autonomous & Interactive Assistive Vision Pi Runner")
    parser.add_argument("--auto", "-a", action="store_true", help="run 100% autonomously without interactive prompts")
    parser.add_argument("--repair", action="store_true", help="force clean re-pair before connecting")
    parser.add_argument("--mac", help="override speaker MAC address")
    parser.add_argument("--laptop-ip", help="override laptop IP address")
    parser.add_argument("--interval", type=float, help="announcement interval in seconds")
    parser.add_argument("--confidence", type=float, help="detection confidence threshold")
    args = parser.parse_args()

    cfg = load_config()
    if args.mac:
        cfg["speaker_mac"] = args.mac
    if args.laptop_ip:
        cfg["laptop_ip"] = args.laptop_ip
    if args.interval:
        cfg["interval"] = args.interval
    if args.confidence:
        cfg["confidence"] = args.confidence
    save_config(cfg)

    if args.auto:
        run_autonomous(cfg, force_repair=args.repair)
    else:
        run_interactive(cfg)

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\nExiting.")
        sys.exit(0)
