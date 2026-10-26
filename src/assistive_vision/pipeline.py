from collections.abc import Iterable
from time import monotonic
from typing import Callable

from .interfaces import Camera, Detector, Speaker
from .models import Detection


class VisionPipeline:
    """Coordinates capture, detection, and throttled audio announcements."""

    def __init__(
        self,
        camera: Camera,
        detector: Detector,
        speaker: Speaker,
        *,
        announcement_interval: float = 5.0,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        if announcement_interval < 0:
            raise ValueError("announcement_interval must not be negative")
        self.camera = camera
        self.detector = detector
        self.speaker = speaker
        self.announcement_interval = announcement_interval
        self._clock = clock
        self._last_announcement: float | None = None

    def scan_once(self) -> list[Detection]:
        frame = self.camera.capture()
        if frame is None:
            return []
        detections = list(self.detector.detect(frame))
        now = self._clock()
        if detections and (
            self._last_announcement is None
            or now - self._last_announcement >= self.announcement_interval
        ):
            self.speaker.speak(self._format_announcement(detections))
            self._last_announcement = now
        return detections

    def run(self, *, max_scans: int | None = None) -> int:
        """Run until the camera ends or max_scans is reached; return scan count."""
        if max_scans is not None and max_scans < 0:
            raise ValueError("max_scans must not be negative")
        scans = 0
        try:
            while max_scans is None or scans < max_scans:
                frame = self.camera.capture()
                if frame is None:
                    break
                detections = list(self.detector.detect(frame))
                now = self._clock()
                if detections and (
                    self._last_announcement is None
                    or now - self._last_announcement >= self.announcement_interval
                ):
                    self.speaker.speak(self._format_announcement(detections))
                    self._last_announcement = now
                scans += 1
        finally:
            self.camera.close()
        return scans

    @staticmethod
    def _format_announcement(detections: Iterable[Detection]) -> str:
        descriptions = [
            f"{item.label} ({item.position}, {item.confidence:.2f})"
            for item in detections
        ]
        return "Detected: " + ", ".join(descriptions)

