from collections.abc import Iterable
from typing import Any

from .models import Detection, Frame


class DemoCamera:
    """Deterministic camera substitute for development and automated tests."""

    def __init__(self, frames: int = 3) -> None:
        if frames < 0:
            raise ValueError("frames must not be negative")
        self._frames = iter(Frame(payload=f"virtual-frame-{i + 1}", sequence=i + 1) for i in range(frames))

    def capture(self) -> Frame | None:
        return next(self._frames, None)

    def close(self) -> None:
        pass


class DemoDetector:
    """Deterministic detector that represents typical objects from the report."""

    _scenes = (
        (Detection("bottle", 0.94, "center"),),
        (Detection("chair", 0.88, "left"), Detection("table", 0.91, "center")),
        (Detection("cell phone", 0.86, "right"),),
    )

    def detect(self, frame: Frame) -> Iterable[Detection]:
        return self._scenes[(frame.sequence - 1) % len(self._scenes)]


class ConsoleSpeaker:
    def speak(self, message: str) -> None:
        print(message)


class Pyttsx3Speaker:
    """Optional local text-to-speech adapter for a laptop or Raspberry Pi."""

    def __init__(self) -> None:
        try:
            import pyttsx3
        except ImportError as exc:
            raise RuntimeError("speech output requires pyttsx3") from exc
        self._engine = pyttsx3.init()

    def speak(self, message: str) -> None:
        self._engine.say(message)
        self._engine.runAndWait()


class OpenCVCamera:
    """OpenCV camera adapter for a local device or a network video stream."""

    def __init__(
        self,
        source: int | str = 0,
        *,
        width: int | None = None,
        height: int | None = None,
    ) -> None:
        try:
            import cv2
        except ImportError as exc:
            raise RuntimeError("camera mode requires opencv-python") from exc
        self._capture = cv2.VideoCapture(source)
        if not self._capture.isOpened():
            self._capture.release()
            raise RuntimeError(f"unable to open camera source {source!r}")
        if width is not None:
            self._capture.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        if height is not None:
            self._capture.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

    def capture(self) -> Frame | None:
        ok, image = self._capture.read()
        if not ok:
            return None
        return Frame(payload=image, sequence=0)

    def close(self) -> None:
        self._capture.release()


class UltralyticsDetector:
    """Optional YOLO adapter for a local Ultralytics model."""

    def __init__(self, model_path: str) -> None:
        try:
            from ultralytics import YOLO
        except ImportError as exc:
            raise RuntimeError("YOLO mode requires the optional camera dependencies") from exc
        self._model = YOLO(model_path)

    def detect(self, frame: Frame) -> Iterable[Detection]:
        results = self._model(frame.payload, verbose=False)
        detections: list[Detection] = []
        for result in results:
            names: dict[int, str] = result.names
            boxes = result.boxes
            for box in boxes:
                confidence = float(box.conf[0])
                class_id = int(box.cls[0])
                x1, _, x2, _ = (float(value) for value in box.xyxy[0])
                frame_width = float(frame.payload.shape[1])
                center = (x1 + x2) / 2
                position = "left" if center < frame_width / 3 else "right" if center > frame_width * 2 / 3 else "center"
                detections.append(Detection(names[class_id], confidence, position))
        return detections


class OpenCVYoloDetector:
    """Run a YOLOv8 ONNX model through OpenCV DNN without PyTorch or CUDA."""

    _labels = (
        "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train",
        "truck", "boat", "traffic light", "fire hydrant", "stop sign",
        "parking meter", "bench", "bird", "cat", "dog", "horse", "sheep",
        "cow", "elephant", "bear", "zebra", "giraffe", "backpack", "umbrella",
        "handbag", "tie", "suitcase", "frisbee", "skis", "snowboard",
        "sports ball", "kite", "baseball bat", "baseball glove", "skateboard",
        "surfboard", "tennis racket", "bottle", "wine glass", "cup", "fork",
        "knife", "spoon", "bowl", "banana", "apple", "sandwich", "orange",
        "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "chair",
        "couch", "potted plant", "bed", "dining table", "toilet", "tv",
        "laptop", "mouse", "remote", "keyboard", "cell phone", "microwave",
        "oven", "toaster", "sink", "refrigerator", "book", "clock", "vase",
        "scissors", "teddy bear", "hair drier", "toothbrush",
    )

    def __init__(
        self,
        model_path: str,
        *,
        confidence_threshold: float = 0.35,
        nms_threshold: float = 0.45,
        input_size: int = 640,
    ) -> None:
        try:
            import cv2
            import numpy as np
        except ImportError as exc:
            raise RuntimeError("ONNX mode requires python3-opencv and python3-numpy") from exc
        self._cv2 = cv2
        self._np = np
        self._net = cv2.dnn.readNetFromONNX(model_path)
        self._confidence_threshold = confidence_threshold
        self._nms_threshold = nms_threshold
        self._input_size = input_size

    def detect(self, frame: Frame) -> Iterable[Detection]:
        image = frame.payload
        height, width = image.shape[:2]
        blob = self._cv2.dnn.blobFromImage(
            image, 1 / 255.0, (self._input_size, self._input_size),
            swapRB=True, crop=False,
        )
        self._net.setInput(blob)
        output = self._net.forward()
        predictions = output[0] if output.ndim == 3 else output
        if predictions.shape[0] < predictions.shape[1]:
            predictions = predictions.T

        boxes: list[list[int]] = []
        scores: list[float] = []
        class_ids: list[int] = []
        x_scale, y_scale = width / self._input_size, height / self._input_size
        for row in predictions:
            class_scores = row[4:]
            class_id = int(self._np.argmax(class_scores))
            confidence = float(class_scores[class_id])
            if confidence < self._confidence_threshold:
                continue
            center_x, center_y, box_width, box_height = row[:4]
            left = int((center_x - box_width / 2) * x_scale)
            top = int((center_y - box_height / 2) * y_scale)
            boxes.append([left, top, int(box_width * x_scale), int(box_height * y_scale)])
            scores.append(confidence)
            class_ids.append(class_id)

        kept = self._cv2.dnn.NMSBoxes(
            boxes, scores, self._confidence_threshold, self._nms_threshold
        )
        detections = []
        for index in kept:
            index = int(index)
            left, _, box_width, _ = boxes[index]
            center = left + box_width / 2
            position = "left" if center < width / 3 else "right" if center > width * 2 / 3 else "center"
            label = self._labels[class_ids[index]] if class_ids[index] < len(self._labels) else f"class {class_ids[index]}"
            detections.append(Detection(label, scores[index], position))
        return detections
