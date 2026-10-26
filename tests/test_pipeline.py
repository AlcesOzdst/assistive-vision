import unittest

from assistive_vision.adapters import DemoCamera, DemoDetector
from assistive_vision.models import Detection
from assistive_vision.pipeline import VisionPipeline


class RecordingSpeaker:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def speak(self, message: str) -> None:
        self.messages.append(message)


class Clock:
    def __init__(self) -> None:
        self.value = 0.0

    def __call__(self) -> float:
        return self.value


class EmptyCamera:
    def capture(self):
        return None

    def close(self) -> None:
        pass


class EmptyDetector:
    def detect(self, frame):
        return []


class PipelineTests(unittest.TestCase):
    def test_demo_pipeline_announces_every_scan_when_interval_is_zero(self) -> None:
        speaker = RecordingSpeaker()
        pipeline = VisionPipeline(
            DemoCamera(3), DemoDetector(), speaker, announcement_interval=0
        )

        self.assertEqual(pipeline.run(max_scans=3), 3)
        self.assertEqual(len(speaker.messages), 3)
        self.assertIn("bottle", speaker.messages[0])
        self.assertIn("chair", speaker.messages[1])

    def test_interval_suppresses_duplicate_announcements(self) -> None:
        speaker = RecordingSpeaker()
        clock = Clock()
        pipeline = VisionPipeline(
            DemoCamera(3), DemoDetector(), speaker, announcement_interval=5, clock=clock
        )

        pipeline.scan_once()
        clock.value = 1
        pipeline.scan_once()
        clock.value = 5
        pipeline.scan_once()

        self.assertEqual(len(speaker.messages), 2)

    def test_empty_camera_does_not_call_detector_and_closes(self) -> None:
        speaker = RecordingSpeaker()
        pipeline = VisionPipeline(EmptyCamera(), EmptyDetector(), speaker)

        self.assertEqual(pipeline.run(), 0)
        self.assertEqual(speaker.messages, [])

    def test_invalid_detection_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            Detection("", 0.5)
        with self.assertRaises(ValueError):
            Detection("person", 1.1)


if __name__ == "__main__":
    unittest.main()
