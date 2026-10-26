#!/usr/bin/env python3
"""Wi-Fi Auto-Connect and Headless SSH Setup Tool for Raspberry Pi.

Configures the Raspberry Pi to automatically connect to a specified Wi-Fi
network (e.g. 'SMJV') on startup, with high autoconnect priority and mDNS
(avahi-daemon) enabled so you can SSH directly using:
    ssh pi@raspi.local

Usage:
    sudo python tools/setup_wifi.py --ssid "SMJV" --password "your_password"
    sudo python tools/setup_wifi.py   (interactive wizard)
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys


def run_cmd(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    """Execute a system command and return output."""
    return subprocess.run(cmd, check=check, text=True, capture_output=True)


def has_tool(name: str) -> bool:
    """Check if a command-line tool is available."""
    return shutil.which(name) is not None


def list_scanned_networks() -> list[str]:
    """Scan and list unique nearby Wi-Fi SSIDs using nmcli."""
    if not has_tool("nmcli"):
        return []
    try:
        res = run_cmd(["nmcli", "-t", "-f", "SSID", "dev", "wifi", "list"], check=False)
        lines = [line.strip() for line in res.stdout.splitlines() if line.strip() and line.strip() != "--"]
        # Maintain order and remove duplicates
        seen: set[str] = set()
        unique = []
        for s in lines:
            if s not in seen:
                seen.add(s)
                unique.append(s)
        return unique
    except Exception:
        return []


def configure_nmcli(ssid: str, password: str, priority: int = 100) -> bool:
    """Configure Wi-Fi connection using NetworkManager (nmcli)."""
    print(f"📡 Configuring NetworkManager for SSID: '{ssid}'...")

    # Check if connection already exists
    con_check = run_cmd(["nmcli", "-t", "-f", "NAME", "connection", "show"], check=False)
    existing_conns = [line.strip() for line in con_check.stdout.splitlines()]

    if ssid in existing_conns:
        print(f"   Found existing connection profile for '{ssid}'. Updating settings...")
        if password:
            run_cmd(["nmcli", "connection", "modify", ssid, "802-11-wireless-security.key-mgmt", "wpa-psk", "802-11-wireless-security.psk", password], check=False)
    else:
        print(f"   Adding new Wi-Fi profile for '{ssid}'...")
        if password:
            cmd = ["nmcli", "dev", "wifi", "connect", ssid, "password", password]
        else:
            cmd = ["nmcli", "dev", "wifi", "connect", ssid]
        
        connect_res = run_cmd(cmd, check=False)
        if connect_res.returncode != 0:
            print(f"⚠️  Live connection note: {connect_res.stderr.strip() or connect_res.stdout.strip()}")
            print("   Creating saved connection profile directly...")
            create_cmd = [
                "nmcli", "connection", "add",
                "type", "wifi",
                "con-name", ssid,
                "ifname", "wlan0",
                "ssid", ssid
            ]
            run_cmd(create_cmd, check=False)
            if password:
                run_cmd([
                    "nmcli", "connection", "modify", ssid,
                    "wifi-sec.key-mgmt", "wpa-psk",
                    "wifi-sec.psk", password
                ], check=False)

    # Set auto-connect and high priority
    print(f"   Setting autoconnect=yes with priority={priority}...")
    run_cmd(["nmcli", "connection", "modify", ssid, "connection.autoconnect", "yes"], check=False)
    run_cmd(["nmcli", "connection", "modify", ssid, "connection.autoconnect-priority", str(priority)], check=False)
    return True


def configure_wpa_supplicant(ssid: str, password: str, priority: int = 100) -> bool:
    """Fallback: configure Wi-Fi in /etc/wpa_supplicant/wpa_supplicant.conf."""
    conf_path = "/etc/wpa_supplicant/wpa_supplicant.conf"
    if not os.path.exists(conf_path):
        return False

    print(f"📡 Adding '{ssid}' to {conf_path}...")
    try:
        if password:
            psk_res = run_cmd(["wpa_passphrase", ssid, password], check=False)
            block = psk_res.stdout if psk_res.returncode == 0 else f"""network={{
    ssid="{ssid}"
    psk="{password}"
    priority={priority}
}}
"""
        else:
            block = f"""network={{
    ssid="{ssid}"
    key_mgmt=NONE
    priority={priority}
}}
"""
        with open(conf_path, "a", encoding="utf-8") as f:
            f.write("\n" + block + "\n")
        run_cmd(["wpa_cli", "-i", "wlan0", "reconfigure"], check=False)
        return True
    except Exception as e:
        print(f"⚠️  Could not update wpa_supplicant: {e}")
        return False


def enable_mdns() -> None:
    """Enable and start avahi-daemon so the Pi can be reached via hostname.local."""
    print("🌐 Ensuring mDNS (avahi-daemon) is enabled for zero-config SSH...")
    if has_tool("systemctl"):
        run_cmd(["systemctl", "enable", "--now", "avahi-daemon"], check=False)
    hostname_res = run_cmd(["hostname"], check=False)
    hostname = hostname_res.stdout.strip() or "raspberrypi"
    print(f"✅ mDNS active! You can SSH from your laptop using: ssh pi@{hostname}.local")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Configure Raspberry Pi to auto-connect to Wi-Fi (e.g. SMJV) on boot."
    )
    parser.add_argument("--ssid", default="", help="Wi-Fi SSID network name (e.g. SMJV)")
    parser.add_argument("--password", default="", help="Wi-Fi password (leave empty if open network)")
    parser.add_argument("--priority", type=int, default=100, help="Autoconnect priority (default: 100)")
    args = parser.parse_args()

    print("\n" + "=" * 65)
    print("  📶 RASPBERRY PI WI-FI AUTO-CONNECT & HEADLESS SSH SETUP")
    print("=" * 65 + "\n")

    if hasattr(os, "geteuid") and os.geteuid() != 0:
        print("⚠️  Warning: This script requires root permissions to modify network settings.")
        print("   Please run with: sudo python tools/setup_wifi.py\n")

    ssid = args.ssid.strip()
    if not ssid:
        print("Scanning for nearby Wi-Fi networks...")
        scanned = list_scanned_networks()
        if scanned:
            print("Found available networks:")
            for idx, net in enumerate(scanned[:10], start=1):
                marker = " (Target)" if "SMJV" in net.upper() else ""
                print(f"  [{idx}] {net}{marker}")
            print("  [0] Type custom SSID name\n")
            choice = input(f"Select network number or press Enter for 'SMJV': ").strip()
            if choice and choice.isdigit() and 1 <= int(choice) <= len(scanned):
                ssid = scanned[int(choice) - 1]
            elif choice == "0":
                ssid = input("Enter Wi-Fi SSID name: ").strip()
            else:
                ssid = "SMJV"
        else:
            entered = input("Enter Wi-Fi SSID [default: SMJV]: ").strip()
            ssid = entered or "SMJV"

    password = args.password
    if not password and "--password" not in sys.argv:
        entered_pw = input(f"Enter password for '{ssid}' (press Enter if open/no password): ").strip()
        password = entered_pw

    success = False
    if has_tool("nmcli"):
        success = configure_nmcli(ssid, password, priority=args.priority)
    elif os.path.exists("/etc/wpa_supplicant/wpa_supplicant.conf"):
        success = configure_wpa_supplicant(ssid, password, priority=args.priority)
    else:
        print("❌ Neither NetworkManager (nmcli) nor wpa_supplicant was detected.")
        return 1

    # Ensure avahi mDNS is active
    enable_mdns()

    print("\n" + "=" * 65)
    print(f"  🎉 AUTO-CONNECT CONFIGURED FOR '{ssid}'!")
    print("=" * 65)
    print("How this works on every boot:")
    print(f"1. When your Pi turns on, it will automatically connect to '{ssid}'.")
    print("2. You do NOT need any HDMI cables, keyboard, or bulky Ethernet switches.")
    print("3. From your laptop (connected to the same Wi-Fi), simply run:")
    print("      ssh pi@raspi.local")
    print("   (Or use the Pi's IP address assigned by the network).")
    print("=" * 65 + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
