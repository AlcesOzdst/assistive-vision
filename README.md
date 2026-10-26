# Assistive Vision Object Detection

An assistive computer vision system designed to announce detected objects and their spatial positions (left, ahead, right) in natural human speech for visually impaired users.

The system is built on a **modular, hardware-independent architecture**, allowing development, simulation, and real-world deployment across laptops and embedded systems (Raspberry Pi).

---

## 🧠 System Architecture & Workflow

```text
┌───────────────────────────────┐           Wi-Fi / LAN           ┌────────────────────────────────┐
│      Any Laptop / Host        │ ──────────────────────────────> │      Raspberry Pi (Pi 4/5)     │
│   (Windows, macOS, or Linux)  │     MJPEG Stream (Port 8765)    │    OpenCV DNN (YOLOv8 ONNX)    │
│  tools/laptop_camera_server.py│                                 │   Natural Speech Announcement  │
└───────────────────────────────┘                                 └───────────────┬────────────────┘
                                                                                  │ Bluetooth (A2DP)
                                                                                  ▼
                                                                  ┌────────────────────────────────┐
                                                                  │       Bluetooth Speaker        │
                                                                  │ "In front: a bottle and a cup."│
                                                                  └────────────────────────────────┘
```

- **Laptop:** Serves purely as a wireless camera. It captures your webcam frames and streams them over your local Wi-Fi network using a zero-dependency HTTP server. No AI models or audio run on your laptop.
- **Raspberry Pi:** The brain of the system. It connects to the laptop's video stream over Wi-Fi, performs real-time YOLOv8 object detection via OpenCV DNN (native C++, no PyTorch/CUDA needed), and generates natural speech.
- **Bluetooth Speaker:** Paired to the Raspberry Pi to deliver natural audio feedback (*"In front: a person and a cell phone."*).

---

## 🚀 Complete Step-by-Step Guide (Start to End)

Follow these steps to get the entire system running with **any laptop** and a **Raspberry Pi**.

---

### Step 1: Laptop Setup (Any Laptop: Windows, macOS, or Linux)

#### 1.1 Clone the repository on your laptop

Open a terminal (PowerShell on Windows, Terminal on Mac/Linux) and run:

```bash
git clone https://github.com/AlcesOzdst/assistive-vision.git
cd assistive-vision
```

#### 1.2 Install OpenCV on your laptop

```bash
pip install opencv-python
```

#### 1.3 Find your Laptop's Wi-Fi IP address

Your laptop and Raspberry Pi must be connected to the **same Wi-Fi network**.

- **Windows:** Run `ipconfig` in PowerShell. Look under `Wireless LAN adapter WiFi` for `IPv4 Address` (e.g. `172.17.4.137` or `192.168.1.50`). *(Ignore virtual adapters like WSL or VMware).*
- **macOS:** Open Terminal and run:

  ```bash
  ipconfig getifaddr en0
  ```

  *(or `en1` depending on Wi-Fi interface).*
- **Linux:** Open Terminal and run:

  ```bash
  hostname -I | awk '{print $1}'
  ```

*Make note of this IP address (e.g., `172.17.4.137`).*

#### 1.4 Start the camera stream on your laptop

```bash
python tools/laptop_camera_server.py --camera 0 --port 8765
```

- If Windows Defender Firewall or macOS prompts for network permissions, allow access on **Private Networks**.
- You will see: `Camera stream ready at http://<LAPTOP_IP>:8765/video`.
- **Leave this terminal open.**

---

### Step 2: Raspberry Pi Setup

SSH into your Raspberry Pi or open a terminal on the Pi desktop.

#### 2.1 Get the project on your Pi

```bash
git clone https://github.com/AlcesOzdst/assistive-vision.git ~/assistive-vision
cd ~/assistive-vision
```

*(If already cloned, simply run `git pull origin main`).*

#### 2.2 Install system packages & virtual environment

```bash
sudo apt update
sudo apt install -y python3-opencv python3-numpy espeak-ng python3-venv libspa-0.2-bluetooth pipewire-alsa

python3 -m venv --system-site-packages .venv
source .venv/bin/activate
pip install -e ".[pi]"
```

Make sure the pre-converted `yolov8n.onnx` model file is present in `~/assistive-vision` (included in the repo).

---

### Step 3: Connect Bluetooth Speaker (Simplified Interactive Wizard)

Bluetooth pairing on Linux can be tricky due to audio drivers, sleep timeouts, and PipeWire profile registration.

We built an **automated interactive setup wizard** that handles everything for you.

#### 3.1 Put your speaker in pairing mode

1. Turn off Bluetooth on your phone and laptop so they don't hijack your speaker.
2. Turn on your Bluetooth speaker and hold its Bluetooth/Pairing button until its light flashes rapidly or it chimes.

#### 3.2 Run the interactive wizard on the Pi

```bash
cd ~/assistive-vision
source .venv/bin/activate
python tools/connect_speaker.py
```

*(Or run `./scripts/connect_speaker.sh`).*

#### What the wizard does automatically

1. **Checks & verifies audio drivers**: Ensures `libspa-0.2-bluetooth` and PipeWire are installed and active.
2. **Registers audio endpoints**: Restarts Bluetooth and user audio daemons to prevent `br-connection-profile-unavailable`.
3. **Scans & displays devices**: Shows a clean numbered list of detected speakers by name (e.g., `[1] ZEB-DELIGHT`).
4. **Pairs, trusts, and connects**: Type the number of your speaker and hit Enter.
5. **Sets default audio output**: Configures PipeWire/WirePlumber to route system speech to the speaker.
6. **Tests audio output**: Speaks a test announcement through your speaker to confirm sound is working.
7. **Saves for 1-click reconnect**: Next time, simply press `[0]` to reconnect instantly!

---

### Step 4: Run Real-Time Assistive Vision

Once your speaker announces that it is connected, start detection:

```bash
python -m assistive_vision \
  --stream-url http://<YOUR_LAPTOP_IP>:8765/video \
  --model yolov8n.onnx \
  --speak
```

*(Replace `<YOUR_LAPTOP_IP>` with your laptop's Wi-Fi IP from Step 1.3, e.g. `172.17.4.137`).*

#### What you will experience

- Point your laptop's camera around the room (at people, chairs, bottles, cups, cell phones, laptops, books).
- The Pi analyzes the video feed in real-time.
- The Bluetooth speaker announces objects in **natural English sentences**:
  > *"In front: a person and a cell phone."*  
  > *"On your left: a chair. In front: a bottle."*  
  > *"In front: 2 cups."*
- **Smart Change Detection:** If you don't move, it won't spam you with repeated announcements. It speaks immediately when a new object appears or when the scene changes!

Press `Ctrl+C` in the Pi terminal to stop.

---

## ⚙️ Advanced CLI Options

You can customize detection sensitivity and speech behavior with optional flags:

```bash
python -m assistive_vision --stream-url http://<LAPTOP_IP>:8765/video --model yolov8n.onnx --speak [OPTIONS]
```

| Flag | Default | Description |
| :--- | :--- | :--- |
| `--confidence` | `0.25` | Detection threshold (0.0 to 1.0). Lower values (e.g. `0.20`) detect smaller objects easier; higher values (e.g. `0.40`) reduce false positives. |
| `--interval` | `3.0` | Minimum seconds between announcements when the scene changes. |
| `--repeat-interval` | `15.0` | Seconds before re-announcing if the scene stays completely unchanged. |
| `--speech-rate` | `145` | Words per minute for speech output. Lower values sound clearer and calmer; higher values speak faster. |
| *(omit `--speak`)* | — | Runs detection and prints results in the terminal without voice output. |

---

## 💻 Alternative: Running Everything on Laptop Alone

If you do not have a Raspberry Pi and want to test everything on your laptop locally:

```bash
pip install -e ".[camera]"
python -m assistive_vision --laptop-camera --model yolov8n.pt --speak
```

---

## 🛠️ Troubleshooting & FAQ

| Problem | Root Cause | Solution |
| :--- | :--- | :--- |
| `br-connection-profile-unavailable` | PipeWire Bluetooth audio bridge was not initialized. | Run `python tools/connect_speaker.py` — it automatically resets and registers the PipeWire endpoints for you. |
| `connect failed (status 0x04)` | Bluetooth Page Timeout. The speaker auto-connected to your phone or laptop. | Turn off Bluetooth on your phone and laptop, power-cycle the speaker into pairing mode, and run `python tools/connect_speaker.py`. |
| Pi cannot reach `http://<LAPTOP_IP>:8765/video` | Windows Firewall or wrong IP chosen in `ipconfig`. | Allow Python through Windows Firewall on Private Networks, and ensure you copied the IP under `Wireless LAN adapter WiFi`, not WSL or VMware. |
| Audio dies after closing SSH | User systemd services suspended on SSH exit. | Run `sudo loginctl enable-linger pi` on the Pi so audio services run continuously in the background. |
| It only announces "person" and "cell phone" | Camera is pointing directly at you holding your phone. | Point the webcam around the room at different objects (chair, bottle, cup, backpack, book, laptop). |

---

## 📁 Repository Structure

```text
├── src/assistive_vision/
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli.py                   # Command-line interface with custom flags
│   ├── interfaces.py            # Camera, Detector, and Speaker Protocols
│   ├── models.py                # Frame and Detection validated dataclasses
│   ├── pipeline.py              # Throttled detection & natural speech coordinator
│   └── adapters.py              # OpenCV, ONNX DNN, Ultralytics, and pyttsx3 adapters
├── tools/
│   ├── connect_speaker.py       # Interactive Bluetooth pairing & audio wizard
│   └── laptop_camera_server.py  # Lightweight MJPEG camera streamer for any laptop
├── scripts/
│   ├── connect_speaker.sh       # Shell shortcut for connect_speaker.py
│   └── deploy_to_pi.sh          # Automated SSH/SCP deployment script
├── tests/
│   └── test_pipeline.py         # Unit tests
├── pyproject.toml               # Package configuration
├── yolov8n.onnx                 # Pre-converted YOLOv8 nano ONNX model for Pi
├── yolov8n.pt                   # YOLOv8 nano PyTorch model
├── QUICKSTART.md                # Fast 3-step cheat sheet
└── README.md
```

## 📜 License

MIT License.
