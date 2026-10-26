# Assistive Vision Object Detection

An assistive computer vision system designed to announce detected objects and their spatial positions (left, center, right) through voice feedback for visually impaired users.

The system is built on a **modular, hardware-independent architecture**, allowing development, simulation, and real-world deployment across laptops and embedded systems (Raspberry Pi).

> 💡 **Looking for the easy, step-by-step setup guide?**  
> Check out the [**Plain-English Quickstart Guide (QUICKSTART.md)**](QUICKSTART.md) — it walks you through running the Laptop Camera + Raspberry Pi + Bluetooth Speaker in 3 foolproof steps.

---

## Architecture Overview

```text
┌───────────────────────┐          Wi-Fi / LAN           ┌────────────────────────────────┐
│     Laptop / Host     │ ─────────────────────────────> │       Raspberry Pi (Pi 4/5)    │
│  (tools/camera_server)│   MJPEG Stream (Port 8765)     │  OpenCV DNN (YOLOv8 ONNX)      │
└───────────────────────┘                                └───────────────┬────────────────┘
                                                                         │ Bluetooth (A2DP)
                                                                         ▼
                                                         ┌────────────────────────────────┐
                                                         │        Bluetooth Speaker       │
                                                         │       ("bottle, center, 0.94") │
                                                         └────────────────────────────────┘
```

The system uses standard Python `Protocol` interfaces:

- **`Camera`**: Captures frames from webcams, network streams, or mock generators.
- **`Detector`**: Runs inference. Supports OpenCV DNN (`yolov8n.onnx` without PyTorch/CUDA) or Ultralytics (`yolov8n.pt`).
- **`Speaker`**: Text-to-speech output via `pyttsx3` / `espeak-ng` or terminal stdout.
- **`VisionPipeline`**: Coordinates capture, detection, spatial position mapping, and rate-limited speech debouncing.

---

## Quick Start (Demo Mode)

Run the deterministic virtual simulation using only the standard Python library (no camera, GPU, or model required):

```bash
python -m assistive_vision --demo --scans 3
```

**Expected output:**

```text
Detected: bottle (center, 0.94)
Detected: chair (left, 0.88), table (center, 0.91)
Detected: cell phone (right, 0.86)
```

Run automated tests:

```bash
python -m unittest discover -s tests -v
```

---

## Target Setup: Laptop Camera + Raspberry Pi + Bluetooth Speaker

In this setup, your laptop acts purely as a wireless camera, while the Raspberry Pi runs the AI detection and speaks through a paired Bluetooth speaker.

### 1. On your Laptop (Camera Streamer)

1. Install OpenCV on your laptop:

   ```bash
   pip install opencv-python
   ```

2. Find your laptop's local IPv4 address:
   - **Windows:** Run `ipconfig` (look for `IPv4 Address` under your active Wi-Fi adapter, e.g., `172.17.4.137` or `192.168.1.50`).
   - **Linux / macOS:** Run `ip a` or `ifconfig`.

3. Start the lightweight camera streaming server:

   ```bash
   python tools/laptop_camera_server.py --camera 0 --port 8765
   ```

   *(If prompted by Windows Firewall, allow access on Private Networks).*

---

### 2. On your Raspberry Pi (Detection & Audio)

#### A. Install System Dependencies

Install OpenCV, NumPy, text-to-speech, and PipeWire Bluetooth audio plugins:

```bash
sudo apt update
sudo apt install -y python3-opencv python3-numpy espeak-ng python3-venv libspa-0.2-bluetooth pipewire-alsa
```

#### B. Set Up the Project & Virtual Environment

```bash
cd ~/assistive-vision
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
pip install -e ".[pi]"
```

Ensure `yolov8n.onnx` is placed in this directory.

---

### 3. Pair & Connect Your Bluetooth Speaker

1. Turn off Bluetooth on your phone and laptop temporarily so the speaker doesn't auto-connect to them.
2. Put your Bluetooth speaker into **pairing mode** (long-press the Bluetooth button until it chimes/flashes).
3. Open `bluetoothctl` on the Pi:

   ```bash
   bluetoothctl
   ```

4. In the `[bluetooth]#` prompt:

   ```text
   scan on
   ```

   Wait for your speaker to appear with its MAC address (e.g., `BA:A6:58:A5:50:39 ZEB-DELIGHT`):

   ```text
   pair BA:A6:58:A5:50:39
   trust BA:A6:58:A5:50:39
   connect BA:A6:58:A5:50:39
   exit
   ```

5. Test sound output:

   ```bash
   espeak-ng "audio connected"
   ```

---

### 4. Run the Live Pipeline

Run the detector on the Raspberry Pi (replace `LAPTOP_IP` with your laptop's IP address):

```bash
python -m assistive_vision \
  --stream-url http://<LAPTOP_IP>:8765/video \
  --model yolov8n.onnx \
  --speak \
  --interval 4
```

- `--stream-url`: Connects to your laptop camera stream.
- `--model`: Loads the optimized ONNX model into OpenCV DNN (C++ execution).
- `--speak`: Enables voice output via the Bluetooth speaker.
- `--interval 4`: Enforces a 4-second minimum interval between announcements to prevent audio spam.

Press `Ctrl+C` to stop.

---

## Alternative: Full Local Run on Laptop

If you want to run everything (camera, YOLO, and audio) locally on your laptop:

```bash
pip install -e ".[camera]"
python -m assistive_vision --laptop-camera --model yolov8n.pt --speak --interval 3
```

---

## Exporting YOLOv8 Models for Raspberry Pi

To generate `yolov8n.onnx` from a PyTorch `.pt` file:

```bash
python -c "from ultralytics import YOLO; YOLO('yolov8n.pt').export(format='onnx', imgsz=640, simplify=False)"
```

---

## Troubleshooting Guide

| Issue | Cause | Solution |
| :--- | :--- | :--- |
| `aplay: audio open error 524` | PipeWire/ALSA missing Bluetooth audio bridge. | Run `sudo apt install -y libspa-0.2-bluetooth pipewire-alsa` and `systemctl --user restart pipewire wireplumber`. |
| `Failed to connect: br-connection-profile-unavailable` | Audio server has not registered the A2DP profile with BlueZ. | Install `libspa-0.2-bluetooth`, run `sudo systemctl restart bluetooth`, and reconnect in `bluetoothctl`. |
| `connect failed (status 0x04)` | Bluetooth Page Timeout. The speaker auto-connected to your phone/laptop. | Turn off Bluetooth on your phone/laptop, power-cycle the speaker into pairing mode, and run `bluetoothctl connect <MAC>`. |
| `Could not get lock /var/lib/dpkg/lock-frontend` | Background updates or another `apt` process is running. | Run `sudo kill -9 <PID>` followed by `sudo dpkg --configure -a`. |
| Pi cannot reach `http://<LAPTOP_IP>:8765/video` | Windows Firewall blocking port 8765, or devices on different Wi-Fi subnets. | Allow Python through Windows Defender Firewall on Private Networks and confirm both devices are on the same Wi-Fi. |

---

## Repository Structure

```text
├── src/assistive_vision/
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli.py            # Command-line interface parser
│   ├── interfaces.py     # Camera, Detector, and Speaker Protocols
│   ├── models.py         # Frame and Detection dataclasses
│   ├── pipeline.py       # Detection and speech coordination pipeline
│   └── adapters.py       # OpenCV, ONNX DNN, Ultralytics, and pyttsx3 adapters
├── tools/
│   └── laptop_camera_server.py  # Zero-dependency MJPEG camera HTTP streamer
├── scripts/
│   └── deploy_to_pi.sh   # Automated SSH/SCP deployment script
├── tests/
│   └── test_pipeline.py  # Unit tests
├── pyproject.toml        # Package dependencies and CLI entry point
├── yolov8n.onnx          # Pre-converted YOLOv8 nano ONNX model for Raspberry Pi
├── yolov8n.pt            # YOLOv8 nano PyTorch model
├── QUICKSTART.md         # Plain-English step-by-step guide
└── README.md
```

## License

MIT License.
