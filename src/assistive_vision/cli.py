import argparse

from .adapters import (
    ConsoleSpeaker,
    DemoCamera,
    DemoDetector,
    OpenCVCamera,
    OpenCVYoloDetector,
    Pyttsx3Speaker,
    UltralyticsDetector,
)
from .pipeline import VisionPipeline


def main() -> int:
    parser = argparse.ArgumentParser(description="Assistive real-time object detection")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--demo", action="store_true", help="run the deterministic virtual camera")
    source.add_argument("--camera", type=int, help="open a local/USB camera by index")
    source.add_argument(
        "--laptop-camera",
        action="store_true",
        help="use a local camera (same as --camera 0)",
    )
    source.add_argument(
        "--stream-url",
        help="read an MJPEG camera stream, for example http://LAPTOP_IP:8765/video",
    )
    parser.add_argument("--scans", type=int, default=3, help="number of scans in demo mode")
    parser.add_argument("--model", help="local YOLO model path for camera mode")
    parser.add_argument("--interval", type=float, default=0.0, help="minimum seconds between announcements")
    parser.add_argument(
        "--speak",
        action="store_true",
        help="use local text-to-speech instead of printing announcements",
    )
    args = parser.parse_args()

    if args.demo:
        camera, detector = DemoCamera(args.scans), DemoDetector()
    else:
        camera_source = (
            args.stream_url
            if args.stream_url
            else 0 if args.laptop_camera else args.camera
        )
        if camera_source is None:
            parser.error("choose --laptop-camera, --camera INDEX, or --stream-url URL")
        if not args.model:
            parser.error("--model is required for camera mode")
        camera = OpenCVCamera(camera_source)
        if args.model.lower().endswith(".onnx"):
            detector = OpenCVYoloDetector(args.model)
        else:
            detector = UltralyticsDetector(args.model)

    VisionPipeline(
        camera,
        detector,
        Pyttsx3Speaker() if args.speak else ConsoleSpeaker(),
        announcement_interval=args.interval,
    ).run(max_scans=args.scans if args.demo else None)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
