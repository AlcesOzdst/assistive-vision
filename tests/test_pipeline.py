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

    def test_natural_speech_formatting_no_decimals_or_parentheses(self) -> None:
        detections = [
            Detection("person", 0.84, "center"),
            Detection("cell phone", 0.91, "center"),
            Detection("chair", 0.88, "left"),
        ]
        text = VisionPipeline._format_announcement(detections)
        self.assertNotIn("0.84", text)
        self.assertNotIn("0.91", text)
        self.assertNotIn("(", text)
        self.assertNotIn(")", text)
        self.assertIn("In front: a person and a cell phone", text)
        self.assertIn("On your left: a chair", text)

    def test_unchanged_scene_suppressed_until_repeat_interval(self) -> None:
        speaker = RecordingSpeaker()
        clock = Clock()
        
        class StaticDetector:
            def detect(self, frame):
                return [Detection("cup", 0.9, "center")]

        pipeline = VisionPipeline(
            DemoCamera(5),
            StaticDetector(),
            speaker,
            announcement_interval=3.0,
            repeat_unchanged_interval=15.0,
            clock=clock,
        )

        pipeline.scan_once()  # t=0 -> announces
        self.assertEqual(len(speaker.messages), 1)

        clock.value = 4.0
        pipeline.scan_once()  # t=4 -> elapsed 4 >= 3, but unchanged, so suppressed!
        self.assertEqual(len(speaker.messages), 1)

        clock.value = 15.0
        pipeline.scan_once()  # t=15 -> repeat interval reached!
        self.assertEqual(len(speaker.messages), 2)


if __name__ == "__main__":
    unittest.main()
