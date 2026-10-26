from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Frame:
    """A captured frame and its source metadata."""

    payload: Any
    sequence: int


@dataclass(frozen=True)
class Detection:
    """One model prediction expressed in user-facing terms."""

    label: str
    confidence: float
    position: str = "center"

    def __post_init__(self) -> None:
        if not self.label.strip():
            raise ValueError("detection label must not be empty")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("detection confidence must be between 0 and 1")
        if not self.position.strip():
            raise ValueError("detection position must not be empty")

