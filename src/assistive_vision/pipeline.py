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
        announcement_interval: float = 6.0,
        repeat_unchanged_interval: float = 45.0,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        if announcement_interval < 0:
            raise ValueError("announcement_interval must not be negative")
        if repeat_unchanged_interval < 0:
            raise ValueError("repeat_unchanged_interval must not be negative")
        self.camera = camera
        self.detector = detector
        self.speaker = speaker
        self.announcement_interval = announcement_interval
        self.repeat_unchanged_interval = repeat_unchanged_interval
        self._clock = clock
        self._last_announcement: float | None = None
        self._last_summary: tuple[tuple[str, str], ...] | None = None

    def scan_once(self) -> list[Detection]:
        frame = self.camera.capture()
        if frame is None:
            return []
        detections = list(self.detector.detect(frame))
        now = self._clock()
        if detections and self._should_announce(detections, now):
            self.speaker.speak(self._format_announcement(detections))
            self._last_announcement = now
            self._last_summary = tuple(sorted((d.label, d.position) for d in detections))
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
                if detections and self._should_announce(detections, now):
                    self.speaker.speak(self._format_announcement(detections))
                    self._last_announcement = now
                    self._last_summary = tuple(sorted((d.label, d.position) for d in detections))
                scans += 1
        finally:
            self.camera.close()
        return scans

    def _should_announce(self, detections: list[Detection], now: float) -> bool:
        if self._last_announcement is None:
            return True
        current_summary = tuple(sorted((d.label, d.position) for d in detections))
        changed = current_summary != self._last_summary
        elapsed = now - self._last_announcement
        if changed and elapsed >= self.announcement_interval:
            return True
        if not changed and elapsed >= self.repeat_unchanged_interval:
            return True
        return False

    @staticmethod
    def _format_announcement(detections: Iterable[Detection]) -> str:
        from collections import Counter

        by_position: dict[str, list[str]] = {}
        for item in detections:
            pos = item.position.strip().lower()
            by_position.setdefault(pos, []).append(item.label.strip())

        position_names = {
            "center": "In front",
            "left": "On your left",
            "right": "On your right",
        }

        parts: list[str] = []
        ordered_positions = ["center", "left", "right"] + [
            p for p in by_position if p not in ("center", "left", "right")
        ]

        for pos in ordered_positions:
            labels = by_position.get(pos, [])
            if not labels:
                continue
            counts = Counter(labels)
            items_phrased: list[str] = []
            for label, count in counts.items():
                if count == 1:
                    article = "an" if label[0].lower() in "aeiou" else "a"
                    items_phrased.append(f"{article} {label}")
                else:
                    items_phrased.append(f"{count} {label}s")

            if len(items_phrased) == 1:
                joined_items = items_phrased[0]
            elif len(items_phrased) == 2:
                joined_items = f"{items_phrased[0]} and {items_phrased[1]}"
            else:
                joined_items = ", ".join(items_phrased[:-1]) + f", and {items_phrased[-1]}"

            pos_label = position_names.get(pos, f"At {pos}")
            parts.append(f"{pos_label}: {joined_items}")

        if not parts:
            return "Nothing detected"
        return ". ".join(parts) + "."

