# Plain-English Quickstart Guide

> **Goal:** Use your **laptop's webcam** as a wireless camera, process everything with **YOLOv8 on your Raspberry Pi**, and hear the detected objects spoken aloud through your **Bluetooth speaker**.

---

## The 10-Second Mental Model

Before running any commands, here is how the 3 devices talk to each other:

1. **Laptop:** Acts purely as a wireless webcam. It captures video and broadcasts it on your local Wi-Fi. (No AI or voice runs on your laptop).
2. **Raspberry Pi:** Does all the heavy computing. It pulls the video over Wi-Fi, detects objects with YOLO, and sends voice commands to the speaker.
3. **Bluetooth Speaker:** Connected to the Pi to speak out announcements (e.g., *"Detected: bottle (center, 0.94)"*).

```text
[Laptop Webcam]  --(Wi-Fi Stream)-->  [Raspberry Pi (AI)]  --(Bluetooth)-->  [Speaker]
```

---

## Pre-Flight Checklist

Make sure:

- [ ] Your laptop and Raspberry Pi are connected to the **exact same Wi-Fi network**.
- [ ] Bluetooth on your **phone** and **laptop** is turned **OFF** (this prevents your speaker from secretly auto-connecting to them).

---

## Step 1: On Your Laptop (Start Camera Stream)

### 1.1 Find your Laptop's Wi-Fi IP address

Open **PowerShell** or **Command Prompt** on your laptop and type:

```powershell
ipconfig
```

Scroll through the output and look **specifically** for:

```text
Wireless LAN adapter WiFi:
   IPv4 Address. . . . . . . . . . . : 172.17.4.137  <-- COPY THIS IP!
```

*(⚠️ **Warning:** Ignore adapters called `WSL`, `VMware`, or `vEthernet`. Only use the one under `Wireless LAN adapter WiFi` or your active Wi-Fi adapter).*

### 1.2 Start the camera server

In the project folder on your laptop, run:

```powershell
python tools/laptop_camera_server.py --camera 0 --port 8765
```

You should see:

```text
Camera stream ready at http://<LAPTOP_IP>:8765/video
```

> **Keep this terminal window open!** If Windows Defender Firewall pops up, check the box for **Private Networks** and click **Allow**.

---

## Step 2: On Your Raspberry Pi (Connect Bluetooth Speaker)

### 2.1 Put your speaker in pairing mode

1. Turn on your Bluetooth speaker (e.g. Zebronics, JBL, Boat).
2. Make sure it says *"Bluetooth Mode"*.
3. Press and hold the **Bluetooth / Pairing button** for 3 seconds until the LED starts blinking rapidly or it chimes.

### 2.2 Pair and connect on the Pi

Open a terminal on your Raspberry Pi and run:

```bash
bluetoothctl
```

You are now in the Bluetooth shell (`[bluetooth]#`). Run:

```text
scan on
```

Wait a few seconds until your speaker appears with its MAC address:

```text
[NEW] Device BA:A6:58:A5:50:39 ZEB-DELIGHT
```

Copy that MAC address and run:

```text
pair BA:A6:58:A5:50:39
trust BA:A6:58:A5:50:39
connect BA:A6:58:A5:50:39
exit
```

Your speaker should chime and announce *"Connected"*.

### 2.3 Test the audio

Back in your normal Pi terminal prompt, test speech output:

```bash
espeak-ng "audio connected"
```

If you hear that through your Bluetooth speaker, your audio is ready!

---

## Step 3: Start the Object Detection

On your Raspberry Pi, inside your project folder:

```bash
cd ~/assistive-vision
source .venv/bin/activate
```

Run this command (replace `172.17.4.137` with **your laptop's IP** from Step 1):

```bash
python -m assistive_vision --stream-url http://172.17.4.137:8765/video --model yolov8n.onnx --speak --interval 4
```

### What happens now

- Point your laptop's camera at everyday objects (chairs, cups, phones, people, bottles).
- The Pi analyzes the video feed in real-time.
- Every 4 seconds, your Bluetooth speaker will announce what it sees:
  > *"Detected: bottle (center, 0.94)"*  
  > *"Detected: person (left, 0.88), laptop (center, 0.92)"*

Press `Ctrl+C` whenever you want to stop.

---

## Common Pitfalls and Easy Fixes

### 1. Bluetooth says `br-connection-profile-unavailable`

- **What it means:** The Pi is missing the Bluetooth audio driver for PipeWire.
- **The Fix:** Run this on the Pi:

  ```bash
  sudo apt install -y libspa-0.2-bluetooth pipewire-alsa
  sudo systemctl restart bluetooth
  systemctl --user restart pipewire wireplumber
  ```

  Then re-run `bluetoothctl connect YOUR_SPEAKER_MAC`.

### 2. Bluetooth says `connect failed (status 0x04)`

- **What it means:** Page Timeout — your speaker didn't respond to the Pi.
- **The Fix:** Your speaker almost certainly auto-connected to your phone or laptop. Turn Bluetooth OFF on your phone and laptop, power-cycle the speaker into pairing mode, and try again.

### 3. The Pi cannot open the stream URL or hangs

- **The Fix:**
  1. Make sure `laptop_camera_server.py` is still running in the laptop terminal.
  2. Verify you used the correct IP under `Wireless LAN adapter WiFi` and not a virtual adapter like WSL or VMware.
  3. Ensure both laptop and Pi are on the same Wi-Fi router.

### 4. How to run detection without audio

- **The Fix:** Omit the `--speak` flag:

  ```bash
  python -m assistive_vision --stream-url http://YOUR_LAPTOP_IP:8765/video --model yolov8n.onnx --interval 4
  ```

  The detections will print directly in your terminal text.
