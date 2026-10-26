"""Assistive vision object detection prototype."""

from .models import Detection, Frame
from .pipeline import VisionPipeline

__all__ = ["Detection", "Frame", "VisionPipeline"]
