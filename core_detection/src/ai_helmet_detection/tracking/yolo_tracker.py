from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional, Union
from urllib.parse import urlparse

import cv2
import numpy as np
from ultralytics import YOLO
from ultralytics.engine.results import Results


SUPPORTED_CLASS_NAMES = ("helmet", "other hat", "no helmet")

# Per-class confidence thresholds.
# Using a lower threshold for "helmet" avoids missing white / light-coloured
# helmets whose predictions tend to score below a generic 0.25 cutoff.
# A stricter threshold for "no helmet" suppresses ambiguous predictions that
# would otherwise trigger false violations.
PER_CLASS_THRESHOLDS: dict[str, float] = {
    "helmet":    0.30,   # permissive — catches white / light helmets
    "other hat": 0.45,   # standard
    "no helmet": 0.60,   # strict — suppresses false no-helmet violations
}

FrameSource = Union[str, int, Path]


def filter_detections_by_class_threshold(
    detections: list,
    per_class_thresholds: Optional[dict[str, float]] = None,
    default_threshold: float = 0.25,
) -> list:
    """Return only detections whose confidence meets their per-class threshold.

    Detections below the class-specific threshold are discarded so that
    ambiguous predictions do not propagate into the violation logic.

    Parameters
    ----------
    detections:
        List of Detection-like objects with ``.class_name`` and ``.confidence``.
    per_class_thresholds:
        Mapping of class name → minimum confidence.  Falls back to
        ``PER_CLASS_THRESHOLDS`` when *None*.
    default_threshold:
        Fallback for classes not listed in *per_class_thresholds*.
    """
    thresholds = per_class_thresholds if per_class_thresholds is not None else PER_CLASS_THRESHOLDS
    return [
        d for d in detections
        if d.confidence >= thresholds.get(d.class_name, default_threshold)
    ]


@dataclass(frozen=True)
class TrackingFrame:
    frame_index: int
    annotated_frame: np.ndarray
    results: Results


class YoloWorkerTracker:
    def __init__(
        self,
        model_path: str = "yolov8n.pt",
        tracker_config: str = "botsort.yaml",
        confidence_threshold: float = 0.25,
        iou_threshold: float = 0.45,
        supported_class_names: tuple[str, ...] = SUPPORTED_CLASS_NAMES,
    ) -> None:
        self.model = YOLO(model_path)
        self.tracker_config = tracker_config
        self.confidence_threshold = confidence_threshold
        self.iou_threshold = iou_threshold
        self.supported_class_names = supported_class_names
        self.class_ids = self._resolve_class_ids()

    def track_source(
        self,
        source: FrameSource,
        max_frames: int = 0,
    ) -> Iterator[TrackingFrame]:
        capture = cv2.VideoCapture(self._normalize_source(source))
        if not capture.isOpened():
            raise ValueError(f"Unable to open source: {source}")

        frame_index = 0
        try:
            while True:
                has_frame, frame = capture.read()
                if not has_frame:
                    break

                frame_index += 1
                yield self.track_frame(frame, frame_index)

                if max_frames and frame_index >= max_frames:
                    break
        finally:
            capture.release()

    def track_frame(
        self,
        frame: np.ndarray,
        frame_index: int,
    ) -> TrackingFrame:
        results = self.model.track(
            source=frame,
            tracker=self.tracker_config,
            persist=True,
            conf=self.confidence_threshold,
            iou=self.iou_threshold,
            classes=self.class_ids,
            verbose=False,
        )
        result = results[0]
        return TrackingFrame(
            frame_index=frame_index,
            annotated_frame=result.plot(),
            results=result,
        )

    def _resolve_class_ids(self) -> list[int]:
        model_names = self.model.names
        normalized_names = {
            str(class_id): class_name.lower()
            for class_id, class_name in model_names.items()
        }
        class_ids = [
            int(class_id)
            for class_id, class_name in normalized_names.items()
            if class_name in self.supported_class_names
        ]

        missing_classes = [
            class_name
            for class_name in self.supported_class_names
            if class_name not in normalized_names.values()
        ]
        if missing_classes:
            raise ValueError(
                "Model does not contain required classes: "
                f"{', '.join(missing_classes)}. "
                "Use custom YOLOv8 Nano weights trained with helmet, other_hat, and no_helmet."
            )

        return class_ids

    @staticmethod
    def _normalize_source(source: FrameSource) -> Union[str, int]:
        if isinstance(source, Path):
            return str(source)

        if isinstance(source, str) and source.isdigit():
            return int(source)

        return source

    @staticmethod
    def is_stream_source(source: str) -> bool:
        parsed_source = urlparse(source)
        return parsed_source.scheme.lower() in {
            "http",
            "https",
            "rtmp",
            "rtsp",
            "rtp",
            "tcp",
            "udp",
        }
