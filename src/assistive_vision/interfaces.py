from collections.abc import Iterable
from typing import Protocol

from .models import Detection, Frame


class Camera(Protocol):
    def capture(self) -> Frame | None:
        """Return the next frame, or None when the source is exhausted."""

    def close(self) -> None:
        """Release the source."""


class Detector(Protocol):
    def detect(self, frame: Frame) -> Iterable[Detection]:
        """Return detections for a frame."""


class Speaker(Protocol):
    def speak(self, message: str) -> None:
        """Deliver an announcement."""
