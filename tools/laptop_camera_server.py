"""Stream the laptop camera to the Raspberry Pi over a local network.

Run this on the laptop. The Raspberry Pi reads the /video endpoint with OpenCV.
This intentionally has no external web-framework dependency.
"""

from __future__ import annotations

import argparse
import threading
from http import server
from typing import Any


class CameraState:
    def __init__(self, capture: Any, cv2: Any) -> None:
        self.capture = capture
        self.cv2 = cv2
        self.lock = threading.Lock()

    def jpeg(self) -> bytes | None:
        with self.lock:
            ok, frame = self.capture.read()
            if not ok:
                return None
            ok, encoded = self.cv2.imencode(".jpg", frame, [self.cv2.IMWRITE_JPEG_QUALITY, 80])
            return encoded.tobytes() if ok else None


def play_laptop_speech(message: str) -> None:
    """Announce text on the laptop using pyttsx3 or Windows SAPI."""
    try:
        import pyttsx3
        engine = pyttsx3.init()
        engine.setProperty("rate", 145)
        engine.say(message)
        engine.runAndWait()
        return
    except Exception:
        pass
    try:
        import win32com.client
        sp = win32com.client.Dispatch("SAPI.SpVoice")
        sp.Speak(message)
        return
    except Exception:
        pass
    print(f"🔊 [Announcement]: {message}")


def make_handler(state: CameraState):
    class StreamHandler(server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path != "/video":
                self.send_error(404, "Use /video")
                return
            self.send_response(200)
            self.send_header("Cache-Control", "no-cache, private")
            self.send_header("Pragma", "no-cache")
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
            self.end_headers()
            try:
                while True:
                    image = state.jpeg()
                    if image is None:
                        break
                    self.wfile.write(
                        b"--frame\r\n"
                        b"Content-Type: image/jpeg\r\n"
                        + f"Content-Length: {len(image)}\r\n\r\n".encode("ascii")
                        + image
                        + b"\r\n"
                    )
            except (BrokenPipeError, ConnectionResetError):
                pass

        def do_POST(self) -> None:
            if self.path == "/speak":
                length = int(self.headers.get("Content-Length", 0))
                raw_body = self.rfile.read(length).decode("utf-8")
                try:
                    import json
                    text = json.loads(raw_body).get("message", "")
                except Exception:
                    text = raw_body
                if text:
                    print(f"🔊 Laptop Announcing: \"{text}\"")
                    threading.Thread(target=play_laptop_speech, args=(text,), daemon=True).start()
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"OK")
                return
            self.send_error(404, "Unknown endpoint")

        def log_message(self, format: str, *args: object) -> None:
            return

    return StreamHandler


def main() -> int:
    parser = argparse.ArgumentParser(description="Stream the laptop camera over HTTP")
    parser.add_argument("--camera", type=int, default=0, help="local camera index")
    parser.add_argument("--host", default="0.0.0.0", help="listen address")
    parser.add_argument("--port", type=int, default=8765, help="listen port")
    args = parser.parse_args()

    try:
        import cv2
    except ImportError as exc:
        raise SystemExit("Install OpenCV first: python -m pip install opencv-python") from exc

    capture = cv2.VideoCapture(args.camera)
    if not capture.isOpened():
        raise SystemExit(f"Unable to open laptop camera index {args.camera}")
    state = CameraState(capture, cv2)
    address = (args.host, args.port)
    print(f"Camera stream ready at http://<LAPTOP_IP>:{args.port}/video")
    try:
        with server.ThreadingHTTPServer(address, make_handler(state)) as httpd:
            httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping camera stream")
    finally:
        capture.release()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
