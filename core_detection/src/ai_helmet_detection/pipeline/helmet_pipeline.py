from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator, Optional, Union

import cv2
import numpy as np
import torch
from ultralytics import YOLO

from ai_helmet_detection.alert_validation import OfficialAlert, TrackViolationValidator, ViolationValidator
from ai_helmet_detection.preprocessing import FramePreprocessor, PreProcessor, PreprocessingResult
from ai_helmet_detection.rule_engine import (
    Detection,
    HelmetViolation,
    PersonValidationResult,
    TrackedPerson,
    evaluate_tracked_person_violations,
)
from ai_helmet_detection.rule_engine.helmet_violation import validate_helmet_violations_from_results
from ai_helmet_detection.tracking import TrackingFrame, YoloWorkerTracker


FrameSource = Union[str, int, Path]


@dataclass(frozen=True)
class PipelineFrame:
    frame_index: int
    event_time: datetime
    source_time_seconds: float
    accepted: bool
    display_frame: np.ndarray
    preprocessing_metrics: dict[str, float]
    tracking_frame: Optional[TrackingFrame]
    violations: list[HelmetViolation]
    official_alerts: list[OfficialAlert]
    drop_reason: Optional[str]


@dataclass(frozen=True)
class EngineFrameResult:
    preprocessing: PreprocessingResult
    helmet_detections: list[Detection]
    tracked_persons: list[TrackedPerson]
    validation_results: list[PersonValidationResult]


class WorkerSafetyPipeline:
    def __init__(
        self,
        tracker: YoloWorkerTracker,
        preprocessor: Optional[PreProcessor] = None,
        validator: Optional[ViolationValidator] = None,
    ) -> None:
        self.tracker = tracker
        self.preprocessor = preprocessor or PreProcessor()
        self.validator = validator or ViolationValidator()

    def run(
        self,
        source: FrameSource,
        max_frames: int = 0,
    ) -> Iterator[PipelineFrame]:
        normalized_source = self._normalize_source(source)

        #connect with video stream (take FPS and sourcr time)
        capture = cv2.VideoCapture(normalized_source)
        
        # Optimize OpenCV Buffer: Drop stale frames to fix accumulated camera lag
        capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        if not capture.isOpened():
            raise ValueError(f"Unable to open source: {source}")

        previous_frame: Optional[np.ndarray] = None
        frame_index = 0
        source_start_time = datetime.now(timezone.utc)
        source_fps = capture.get(cv2.CAP_PROP_FPS)
        
        last_tracking_frame = None
        last_violations = []
        last_official_alerts = []
        dropped_count = 0
        MAX_GRACE_PERIOD = 5
        try:
            # each cycle -> get 1 frame
            while True:
                has_frame, frame = capture.read()
                if not has_frame:
                    break
                    
                # Optimize: Resize frame from phone to prevent SSIM limit + CPU bottleneck
                frame = cv2.resize(frame, (640, 480))

                frame_index += 1
                source_time_seconds = self._resolve_source_time_seconds(capture, frame_index, source_fps)
                event_time = source_start_time + timedelta(seconds=source_time_seconds)
                
                # althogirm: CLAUHE + Laplacian variance + compare structure of SSIM with previos_frame
                accepted, processed_frame, preprocessing_metrics = self.preprocessor.process_frame(
                    frame,
                    previous_frame,
                ) # -> return boolean (frame is accepted or not)
                previous_frame = frame

                # if frame is accepted -> run object detection
                if accepted:
                    dropped_count = 0
                    # tracking frame - YOLOv8 -> return coordinates bounding box and provide trackId
                    tracking_frame = self.tracker.track_frame(processed_frame, frame_index)
                    # validate helmet violations - rule engine
                    violations = validate_helmet_violations_from_results(tracking_frame.results)
                    # update validator -> alert?
                    official_alerts = self.validator.update(
                        frame_index=frame_index,
                        frame=processed_frame,
                        violations=violations,
                        event_time=event_time,
                        source_time_seconds=source_time_seconds,
                    )
                    
                    last_tracking_frame = tracking_frame
                    last_violations = violations
                    last_official_alerts = official_alerts
                    
                    # annotate frame
                    #openCV draw the border and display label for ACCEPTED? NOT_ACCEPTED
                    annotated_frame = self._annotate_frame(
                        tracking_frame.annotated_frame,
                        accepted=True,
                        preprocessing_metrics=preprocessing_metrics,
                        violations=violations,
                        official_alerts=official_alerts,
                        drop_reason=None,
                    )
                    # return object
                    yield PipelineFrame(
                        frame_index=frame_index,
                        event_time=event_time,
                        source_time_seconds=source_time_seconds,
                        accepted=True,
                        display_frame=annotated_frame,
                        preprocessing_metrics=preprocessing_metrics,
                        tracking_frame=tracking_frame,
                        violations=violations,
                        official_alerts=official_alerts,
                        drop_reason=None,
                    )
                else:
                    dropped_count += 1
                    drop_reason = self._resolve_drop_reason(preprocessing_metrics)
                    
                    if dropped_count <= MAX_GRACE_PERIOD and last_tracking_frame is not None:
                        # Edge Case fix: Grace period active
                        active_violations = last_violations
                        active_alerts = last_official_alerts
                        active_tracking = last_tracking_frame
                    else:
                        active_violations = []
                        active_alerts = []
                        active_tracking = None
                        
                    dropped_frame = self._annotate_frame(
                        frame.copy(),
                        accepted=False,
                        preprocessing_metrics=preprocessing_metrics,
                        violations=active_violations,
                        official_alerts=active_alerts,
                        drop_reason=drop_reason,
                    )
                    yield PipelineFrame(
                        frame_index=frame_index,
                        event_time=event_time,
                        source_time_seconds=source_time_seconds,
                        accepted=False,
                        display_frame=dropped_frame,
                        preprocessing_metrics=preprocessing_metrics,
                        tracking_frame=active_tracking,
                        violations=active_violations,
                        official_alerts=active_alerts,
                        drop_reason=drop_reason,
                    )

                if max_frames and frame_index >= max_frames:
                    break
        finally:
            capture.release()

    def _annotate_frame(
        self,
        frame: np.ndarray,
        accepted: bool,
        preprocessing_metrics: dict[str, float],
        violations: list[HelmetViolation],
        official_alerts: list[OfficialAlert],
        drop_reason: Optional[str],
    ) -> np.ndarray:
        status_text = "ACCEPTED" if accepted else f"DROPPED: {drop_reason}"
        status_color = (60, 180, 75) if accepted else (0, 0, 255)
        cv2.putText(frame, status_text, (16, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, status_color, 2)
        cv2.putText(
            frame,
            f"SSIM: {preprocessing_metrics['ssim']:.4f}",
            (16, 60),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 255, 255),
            2,
        )
        cv2.putText(
            frame,
            f"Laplacian Var: {preprocessing_metrics['laplacian_variance']:.2f}",
            (16, 88),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 255, 255),
            2,
        )
        for violation in violations:
            if not getattr(violation, "violation", False):
                continue

            x1, y1, x2, y2 = (int(value) for value in violation.subject_box)
            hx1, hy1, hx2, hy2 = (int(value) for value in violation.head_roi)
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
            cv2.rectangle(frame, (hx1, hy1), (hx2, hy2), (0, 165, 255), 2)
            label = (
                f"Violation {violation.predicted_class} ID="
                f"{violation.track_id if violation.track_id is not None else 'NA'}"
            )
            cv2.putText(frame, label, (x1, max(y1 - 8, 20)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

        for alert in official_alerts:
            x1, y1, x2, _ = (int(value) for value in alert.subject_box)
            label = f"ALERT ID={alert.track_id} ratio={alert.violation_ratio:.2f} t={alert.source_time_seconds:.2f}s"
            cv2.putText(frame, label, (x1, y1 + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        return frame

    def _resolve_drop_reason(self, preprocessing_metrics: dict[str, float]) -> str:
        if preprocessing_metrics["ssim"] < self.preprocessor.ssim_threshold:
            return "low_ssim"
        return "blur"

    @staticmethod
    def _normalize_source(source: FrameSource) -> Union[str, int]:
        if isinstance(source, Path):
            return str(source)
        if isinstance(source, str) and source.isdigit():
            return int(source)
        return source

    @staticmethod
    def _resolve_source_time_seconds(capture: cv2.VideoCapture, frame_index: int, source_fps: float) -> float:
        position_msec = capture.get(cv2.CAP_PROP_POS_MSEC)
        if position_msec > 0:
            return position_msec / 1000.0

        if source_fps and source_fps > 0:
            return max(frame_index - 1, 0) / source_fps

        return float(max(frame_index - 1, 0))


class HelmetSystem:
    def __init__(
        self,
        helmet_model_path: str | Path,
        person_model_path: str | Path,
        inference_image_size: int = 640,
        helmet_confidence_threshold: float = 0.12,
        person_confidence_threshold: float = 0.25,
        person_iou_threshold: float = 0.45,
        blur_threshold: float = 60.0,
        head_roi_ratio: float = 0.35,
        validation_window_size: int = 30,
        validation_required_hits: int = 24,
        device: str = "cpu",
        temporal_validator: Optional[TrackViolationValidator] = None,
        single_model_inference: Optional[bool] = None,
        tracker_config: str = "botsort.yaml",
        min_head_iou: float = 0.1,
    ) -> None:
        self.inference_image_size = inference_image_size
        self.helmet_confidence_threshold = helmet_confidence_threshold
        self.person_confidence_threshold = person_confidence_threshold
        self.person_iou_threshold = person_iou_threshold
        self.head_roi_ratio = head_roi_ratio
        self.min_head_iou = min_head_iou
        self.device = device
        self.tracker_config = tracker_config
        self.preprocessor = FramePreprocessor(blur_threshold=blur_threshold)
        self.temporal_validator = temporal_validator or TrackViolationValidator(
            window_size=validation_window_size,
            required_hits=validation_required_hits,
        )
        self.helmet_model = YOLO(str(helmet_model_path))
        helmet_model_path = Path(helmet_model_path)
        person_model_path = Path(person_model_path)
        if single_model_inference is None:
            self.single_model_inference = helmet_model_path == person_model_path
        else:
            self.single_model_inference = single_model_inference

        self.person_model = self.helmet_model if self.single_model_inference else YOLO(str(person_model_path))

        if self.device.lower() == "cpu":
            torch.backends.mkldnn.enabled = False

    def process_frame(self, frame: Any) -> EngineFrameResult:
        preprocessing = self.preprocessor.process_frame(frame)
        if not preprocessing.inference_allowed:
            return EngineFrameResult(
                preprocessing=preprocessing,
                helmet_detections=[],
                tracked_persons=[],
                validation_results=[],
            )

        if self.single_model_inference:
            helmet_detections, tracked_persons = self._run_joint_detection_and_tracking(preprocessing.processed_frame)
        else:
            helmet_detections = self._run_helmet_detection(preprocessing.processed_frame)
            tracked_persons = self._run_person_tracking(preprocessing.processed_frame)

        # Multi-object flow: evaluate every tracked person independently with their own head ROI.
        # Pass the raw frame so analyse_head_roi_gloss can crop each head ROI and check
        # specular highlights when YOLOv8 confidence is low (gloss-based SAFE override).
        base_results = evaluate_tracked_person_violations(
            tracked_persons,
            helmet_detections,
            confirmed_ratios={},
            head_roi_ratio=self.head_roi_ratio,
            min_head_iou=self.min_head_iou,
            frame=preprocessing.processed_frame,
        )
        confirmed_ratios = self.temporal_validator.update_results(base_results)
        validation_results = evaluate_tracked_person_violations(
            tracked_persons,
            helmet_detections,
            confirmed_ratios=confirmed_ratios,
            head_roi_ratio=self.head_roi_ratio,
            min_head_iou=self.min_head_iou,
            frame=preprocessing.processed_frame,
        )
        return EngineFrameResult(
            preprocessing=preprocessing,
            helmet_detections=helmet_detections,
            tracked_persons=tracked_persons,
            validation_results=validation_results,
        )

    def _run_joint_detection_and_tracking(self, frame: np.ndarray) -> tuple[list[Detection], list[TrackedPerson]]:
        # In single-model mode, YOLOv8 uses one backbone (CSPDarknet) to build shared feature maps,
        # then predicts person and helmet classes in one detection head pass, reducing duplicate compute.
        results = self.helmet_model.track(
            source=frame,
            tracker=self.tracker_config,
            persist=True,
            imgsz=self.inference_image_size,
            conf=min(self.person_confidence_threshold, self.helmet_confidence_threshold),
            iou=self.person_iou_threshold,
            device=self.device,
            verbose=False,
        )
        result = results[0]
        boxes = result.boxes
        if boxes is None or boxes.xyxy is None or boxes.conf is None or boxes.cls is None:
            return [], []

        names = self.helmet_model.names
        track_ids = boxes.id.tolist() if boxes.id is not None else []
        has_track_ids = len(track_ids) == len(boxes)
        helmet_detections: list[Detection] = []
        tracked_persons: list[TrackedPerson] = []

        for index, detected_box in enumerate(boxes):
            class_id = int(detected_box.cls.item())
            label = str(names[class_id]).lower()
            confidence = float(detected_box.conf.item())
            x1, y1, x2, y2 = (float(value) for value in detected_box.xyxy[0].tolist())

            if label == "person":
                if confidence < self.person_confidence_threshold:
                    continue

                track_id = int(track_ids[index]) if has_track_ids else index
                tracked_persons.append(
                    TrackedPerson(
                        track_id=track_id,
                        confidence=confidence,
                        bounding_box=(int(x1), int(y1), int(x2), int(y2)),
                    )
                )
                continue

            if confidence < self.helmet_confidence_threshold:
                continue

            helmet_detections.append(
                Detection(
                    class_name=label,
                    bounding_box=(x1, y1, x2, y2),
                    confidence=confidence,
                )
            )

        return helmet_detections, tracked_persons

    def _run_helmet_detection(self, frame: np.ndarray) -> list[Detection]:
        results = self.helmet_model.predict(
            frame,
            imgsz=self.inference_image_size,
            conf=self.helmet_confidence_threshold,
            device=self.device,
            verbose=False,
        )
        result = results[0]
        boxes = result.boxes
        detections: list[Detection] = []
        if boxes is None:
            return detections

        for detected_box in boxes:
            class_id = int(detected_box.cls.item())
            label = str(self.helmet_model.names[class_id]).lower()
            confidence = float(detected_box.conf.item())
            x1, y1, x2, y2 = (float(value) for value in detected_box.xyxy[0].tolist())
            detections.append(
                Detection(
                    class_name=label,
                    bounding_box=(x1, y1, x2, y2),
                    confidence=confidence,
                )
            )
        return detections

    def _run_person_tracking(self, frame: np.ndarray) -> list[TrackedPerson]:
        results = self.person_model.track(
            source=frame,
            tracker=self.tracker_config,
            persist=True,
            classes=[0],
            imgsz=self.inference_image_size,
            conf=self.person_confidence_threshold,
            iou=self.person_iou_threshold,
            device=self.device,
            verbose=False,
        )
        return self._extract_person_tracks(results)

    @staticmethod
    def _extract_person_tracks(results: list[Any]) -> list[TrackedPerson]:
        result = results[0]
        boxes = result.boxes
        if boxes is None or boxes.id is None or boxes.xyxy is None or boxes.conf is None:
            return []

        tracked_persons: list[TrackedPerson] = []
        for track_id, confidence, box in zip(boxes.id.tolist(), boxes.conf.tolist(), boxes.xyxy.tolist()):
            x1, y1, x2, y2 = (int(value) for value in box)
            tracked_persons.append(
                TrackedPerson(
                    track_id=int(track_id),
                    confidence=float(confidence),
                    bounding_box=(x1, y1, x2, y2),
                )
            )
        return tracked_persons