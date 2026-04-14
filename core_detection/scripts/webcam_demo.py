from __future__ import annotations

import csv
from datetime import datetime
import os
from pathlib import Path
import sys
import threading
import time

import cv2
import numpy as np

try:
    import pyttsx3
except ImportError:
    pyttsx3 = None

try:
    import winsound
except ImportError:
    winsound = None


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.ai_helmet_detection.alert_validation import TrackViolationValidator
from src.ai_helmet_detection.core_detection.preprocessor import Preprocessor
from src.ai_helmet_detection.pipeline import HelmetSystem
from src.ai_helmet_detection.rule_engine import Detection, PersonValidationResult, TrackedPerson
from src.ai_helmet_detection.tracking.yolo_tracker import (
    filter_detections_by_class_threshold,
)


MODEL_PATH = PROJECT_ROOT / "helmet_v2_final.pt"
EXPECTED_MODEL_BYTES = 6_262_257
PERSON_MODEL_PATH = PROJECT_ROOT / "yolov8n.pt"
WINDOW_NAME = "Helmet Detection Webcam Demo"
ENHANCED_WINDOW_NAME = "Enhanced Frame (CLAHE + Unsharp)"
VIOLATIONS_DIR = PROJECT_ROOT / "violations"
VIOLATION_LOG_PATH = PROJECT_ROOT / "violation_log.csv"
VIOLATION_MESSAGE = "VIOLATION DETECTED: NO SAFETY HELMET"
SAVED_VIOLATION_LABEL = "VIOLATION: NO SAFETY HELMET"
EVIDENCE_SCALE_FACTOR = 2.5
INFERENCE_IMAGE_SIZE = 640
# Per-class confidence thresholds — used to disambiguate between similar
# visual categories (e.g. white helmet vs. bare head).
THRESHOLD_HELMET    = 0.30   # permissive: catches white / light-coloured helmets
THRESHOLD_OTHER_HAT = 0.45   # standard
THRESHOLD_NO_HELMET = 0.60   # strict: suppresses false no-helmet violations
# The base threshold sent to YOLO is the minimum per-class value so that all
# potentially valid detections reach the per-class filter below.
HELMET_CONFIDENCE_THRESHOLD = THRESHOLD_HELMET
PERSON_TRACK_CONFIDENCE = 0.25
PERSON_TRACK_IOU = 0.45
BLUR_THRESHOLD = 0.0
PREPROCESSOR_BLUR_THRESHOLD = 30.0
PREPROCESSOR_SSIM_THRESHOLD = 0.3
PREPROCESSOR_SSIM_INTERVAL = 3
HEAD_ROI_RATIO = 0.35
VALIDATION_WINDOW_SIZE = 30
VALIDATION_REQUIRED_HITS = 24
INSPECTOR_WINDOW_NAME = "Head ROI Inspector"
INSPECTOR_THUMB_W = 128  # width of each thumbnail inside the inspector panel
INSPECTOR_THUMB_H = 96   # height of each thumbnail inside the inspector panel
HEAD_SPATIAL_TOP_RATIO = 0.35

# Lightweight enhancement settings tuned to improve white-helmet edge contrast
# in bright scenes while avoiding a large FPS penalty on CPU.
CLAHE_CLIP_LIMIT = 2.0
CLAHE_TILE_GRID = (8, 8)
UNSHARP_GAUSSIAN_KSIZE = (5, 5)
UNSHARP_SIGMA = 1.0
UNSHARP_ALPHA = 1.5
UNSHARP_BETA = -0.5
CLASS_COLORS: dict[str, tuple[int, int, int]] = {
    "helmet": (0, 255, 0),
    "other hat": (0, 255, 255),
    "no helmet": (0, 0, 255),
}

CLASS_THRESHOLDS = {
    "helmet": THRESHOLD_HELMET,
    "other_hat": THRESHOLD_OTHER_HAT,
    "no_helmet": THRESHOLD_NO_HELMET,
}

_FRAME_CLAHE = cv2.createCLAHE(clipLimit=CLAHE_CLIP_LIMIT, tileGridSize=CLAHE_TILE_GRID)


def _normalize_class_name(class_name: str) -> str:
    return class_name.lower().replace(" ", "_")


def enhance_frame(frame_bgr: cv2.typing.MatLike) -> cv2.typing.MatLike:
    """Enhance frame with LAB-CLAHE and unsharp masking before inference."""
    lab = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2LAB)
    l_channel, a_channel, b_channel = cv2.split(lab)
    l_enhanced = _FRAME_CLAHE.apply(l_channel)
    lab_enhanced = cv2.merge((l_enhanced, a_channel, b_channel))
    clahe_bgr = cv2.cvtColor(lab_enhanced, cv2.COLOR_LAB2BGR)

    denoised = cv2.GaussianBlur(clahe_bgr, UNSHARP_GAUSSIAN_KSIZE, UNSHARP_SIGMA)
    sharpened = cv2.addWeighted(clahe_bgr, UNSHARP_ALPHA, denoised, UNSHARP_BETA, 0)
    return np.clip(sharpened, 0, 255).astype(np.uint8)


def _in_person_head_top_zone(
    detection: Detection,
    person_box: tuple[int, int, int, int],
    head_top_ratio: float = HEAD_SPATIAL_TOP_RATIO,
) -> bool:
    dx1, dy1, dx2, dy2 = detection.bounding_box
    center_x = 0.5 * (dx1 + dx2)
    center_y = 0.5 * (dy1 + dy2)
    px1, py1, px2, py2 = person_box
    person_h = max(py2 - py1, 1)
    head_bottom = py1 + int(person_h * head_top_ratio)
    return px1 <= center_x <= px2 and py1 <= center_y <= head_bottom


def filter_detections_by_spatial_constraint(
    detections: list[Detection],
    tracked_persons: list[TrackedPerson],
    head_top_ratio: float = HEAD_SPATIAL_TOP_RATIO,
) -> list[Detection]:
    """Apply top-head spatial validation to reduce background detections."""
    person_boxes = [person.bounding_box for person in tracked_persons]
    if not person_boxes:
        return []

    filtered: list[Detection] = []
    for detection in detections:
        normalized = _normalize_class_name(detection.class_name)
        if normalized in {"helmet", "other_hat", "no_helmet"}:
            if any(_in_person_head_top_zone(detection, box, head_top_ratio) for box in person_boxes):
                filtered.append(detection)
        else:
            filtered.append(detection)
    return filtered


def build_person_validation_results(
    tracked_persons: list[TrackedPerson],
    filtered_detections: list[Detection],
    head_top_ratio: float = HEAD_SPATIAL_TOP_RATIO,
) -> tuple[list[PersonValidationResult], dict[int, str]]:
    """Build explicit-label per-person safety state from head-zone detections."""
    results: list[PersonValidationResult] = []
    status_labels: dict[int, str] = {}
    for person in tracked_persons:
        px1, py1, px2, py2 = person.bounding_box
        person_h = max(py2 - py1, 1)
        head_bottom = py1 + int(person_h * head_top_ratio)
        head_roi = (px1, py1, px2, head_bottom)

        has_helmet = False
        has_other_hat = False
        has_no_helmet = False
        for detection in filtered_detections:
            if not _in_person_head_top_zone(detection, person.bounding_box, head_top_ratio):
                continue
            normalized = _normalize_class_name(detection.class_name)
            if normalized == "helmet":
                has_helmet = True
            elif normalized == "other_hat":
                has_other_hat = True
            elif normalized == "no_helmet":
                has_no_helmet = True

        if has_no_helmet:
            status_label = "No Helmet"
            is_violation = True
        elif has_other_hat:
            status_label = "Other Hat"
            is_violation = True
        elif has_helmet:
            status_label = "Helmet"
            is_violation = False
        else:
            status_label = "Safe"
            is_violation = False

        status_labels[person.track_id] = status_label
        results.append(
            PersonValidationResult(
                track_id=person.track_id,
                confidence=person.confidence,
                person_box=person.bounding_box,
                head_roi=head_roi,
                best_helmet_overlap=1.0 if has_helmet else 0.0,
                potential_violation=is_violation,
                confirmed_violation=is_violation,
                violation_ratio=1.0 if is_violation else 0.0,
                material_score=0.0,
                material_override=False,
            )
        )
    return results, status_labels


def _draw_scale(frame: cv2.typing.MatLike) -> tuple[float, int, int]:
    frame_height, frame_width = frame.shape[:2]
    resolution_scale = min(frame_width / 1280.0, frame_height / 720.0)
    text_scale = max(0.55, min(1.2, 0.6 * resolution_scale + 0.25))
    thickness = max(1, int(round(2 * resolution_scale)))
    thin_thickness = max(1, int(round(1 * resolution_scale)))
    return text_scale, thickness, thin_thickness


def draw_detection(frame: cv2.typing.MatLike, detection: Detection) -> None:
    text_scale, thickness, _ = _draw_scale(frame)
    x1, y1, x2, y2 = (int(value) for value in detection.bounding_box)
    color = CLASS_COLORS.get(detection.class_name, (255, 255, 255))
    cv2.rectangle(frame, (x1, y1), (x2, y2), color, thickness)

    text = f"{detection.class_name} {detection.confidence:.2f}"
    (text_width, text_height), baseline = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, text_scale, thickness)
    label_top = max(y1 - text_height - baseline - 6, 0)
    label_bottom = label_top + text_height + baseline + 6
    cv2.rectangle(frame, (x1, label_top), (x1 + text_width + 10, label_bottom), color, -1)
    cv2.putText(
        frame,
        text,
        (x1 + 5, label_bottom - baseline - 3),
        cv2.FONT_HERSHEY_SIMPLEX,
        text_scale,
        (0, 0, 0),
        thickness,
        cv2.LINE_AA,
    )


def draw_person_result(
    frame: cv2.typing.MatLike,
    result: PersonValidationResult,
    status_label: str,
) -> None:
    text_scale, thickness, thin_thickness = _draw_scale(frame)
    if status_label in {"Helmet", "Safe"}:
        box_color = (0, 255, 0)
    elif status_label == "Other Hat":
        box_color = (0, 215, 255)
    else:
        box_color = (0, 0, 255)

    x1, y1, x2, y2 = result.person_box
    rx1, ry1, rx2, ry2 = result.head_roi
    # Draw full body box as a thin outline and head ROI as a distinct highlight.
    cv2.rectangle(frame, (x1, y1), (x2, y2), box_color, thin_thickness)
    head_roi_color = (255, 255, 0)
    cv2.rectangle(frame, (rx1, ry1), (rx2, ry2), head_roi_color, max(thickness + 1, 2))

    state = "VIOLATION" if result.confirmed_violation else "SAFE"
    label = f"ID {result.track_id} {status_label} {state}"
    # Highlight the head ROI box in cyan when a material-score override is active.
    if result.material_override:
        cv2.rectangle(frame, (rx1, ry1), (rx2, ry2), (255, 255, 0), max(thickness + 1, 2))
        cv2.rectangle(frame, (rx1, ry1), (rx2, ry2), (0, 255, 255), max(thickness, 1))
    cv2.putText(
        frame,
        label,
        (rx1, max(ry1 - 10, 20)),
        cv2.FONT_HERSHEY_SIMPLEX,
        text_scale,
        box_color,
        thickness,
        cv2.LINE_AA,
    )


def draw_preprocessing_overlay(
    frame: cv2.typing.MatLike,
    blur_score: float,
    ssim_score: float,
    is_blurred: bool,
    is_glitch: bool,
    inference_skipped: bool,
) -> None:
    text_scale, thickness, _ = _draw_scale(frame)
    overlay_lines = ["CLAHE: Active", f"Blur Score: {blur_score:.1f}"]
    overlay_lines.append(f"SSIM: {ssim_score:.3f}")
    if is_blurred:
        overlay_lines.append("Frame: Blurry")
    if is_glitch:
        overlay_lines.append("Frame: Glitch")
    if inference_skipped:
        overlay_lines.append("YOLO: Skipped (Low Quality)")

    font = cv2.FONT_HERSHEY_SIMPLEX
    scale = text_scale
    line_height = int(28 * max(scale, 0.75))
    max_width = 0
    for line in overlay_lines:
        (line_width, _), _ = cv2.getTextSize(line, font, scale, thickness)
        max_width = max(max_width, line_width)

    origin_x = max(frame.shape[1] - max_width - 20, 10)
    origin_y = 30
    for index, line in enumerate(overlay_lines):
        text_y = origin_y + index * line_height
        cv2.putText(frame, line, (origin_x, text_y), font, scale, (255, 255, 255), thickness, cv2.LINE_AA)


def draw_violation_overlay(frame: cv2.typing.MatLike, current_time: float) -> None:
    frame_height, frame_width = frame.shape[:2]
    cv2.rectangle(frame, (0, 0), (frame_width - 1, frame_height - 1), (0, 0, 255), 12)
    if int(current_time * 2) % 2 == 0:
        font = cv2.FONT_HERSHEY_TRIPLEX
        scale = max(frame_width / 780.0, 1.4)
        thickness = 6
        (text_width, text_height), baseline = cv2.getTextSize(VIOLATION_MESSAGE, font, scale, thickness)
        origin_x = max((frame_width - text_width) // 2, 10)
        origin_y = max(text_height + 30, 55)
        cv2.putText(frame, VIOLATION_MESSAGE, (origin_x, origin_y), font, scale, (0, 0, 255), thickness, cv2.LINE_AA)
        cv2.putText(frame, VIOLATION_MESSAGE, (origin_x, origin_y), font, scale, (255, 255, 255), 2, cv2.LINE_AA)


def beep_alert() -> None:
    if winsound is None:
        os.system("printf '\a'")
        return
    winsound.Beep(2200, 250)


def alert_sound_loop(stop_event: threading.Event) -> None:
    while not stop_event.is_set():
        beep_alert()
        stop_event.wait(0.35)


def speak_warning_message() -> None:
    if pyttsx3 is None:
        return
    engine = pyttsx3.init()
    engine.say("Warning: No safety helmet detected")
    engine.runAndWait()


def speak_warning_async() -> None:
    if pyttsx3 is None:
        return
    threading.Thread(target=speak_warning_message, daemon=True).start()


def log_violation_started() -> None:
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {VIOLATION_MESSAGE}")


def append_violation_log(track_id: int, start_time: datetime, end_time: datetime, duration_seconds: float) -> None:
    log_exists = VIOLATION_LOG_PATH.exists()
    with VIOLATION_LOG_PATH.open("a", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        if not log_exists:
            writer.writerow(["track_id", "start_time", "end_time", "duration_seconds"])
        writer.writerow([
            track_id,
            start_time.strftime("%Y-%m-%d %H:%M:%S"),
            end_time.strftime("%Y-%m-%d %H:%M:%S"),
            f"{duration_seconds:.2f}",
        ])


def finalize_violation(track_id: int, started_at: datetime, started_perf: float) -> None:
    duration_seconds = max(time.perf_counter() - started_perf, 0.0)
    end_time = datetime.now()
    append_violation_log(track_id, started_at, end_time, duration_seconds)
    print(
        f"Track {track_id} violation ended. "
        f"Start: {started_at.strftime('%Y-%m-%d %H:%M:%S')} | "
        f"End: {end_time.strftime('%Y-%m-%d %H:%M:%S')} | "
        f"Duration: {duration_seconds:.2f}s"
    )


def save_violation_crop(
    frame: cv2.typing.MatLike,
    track_id: int,
    person_box: tuple[int, int, int, int],
    confidence: float,
    started_at: datetime,
) -> Path:
    VIOLATIONS_DIR.mkdir(parents=True, exist_ok=True)
    frame_height, frame_width = frame.shape[:2]
    x1, y1, x2, y2 = person_box
    box_width = max(x2 - x1, 1)
    box_height = max(y2 - y1, 1)
    center_x = x1 + (box_width / 2.0)
    center_y = y1 + (box_height / 2.0)

    left = max(int(center_x - ((box_width * EVIDENCE_SCALE_FACTOR) / 2.0)), 0)
    top = max(int(center_y - ((box_height * EVIDENCE_SCALE_FACTOR) / 2.0)), 0)
    right = min(int(center_x + ((box_width * EVIDENCE_SCALE_FACTOR) / 2.0)), frame_width)
    bottom = min(int(center_y + ((box_height * EVIDENCE_SCALE_FACTOR) / 2.0)), frame_height)

    # Safety clamp: keep the scaled crop fully inside frame boundaries.
    left = max(left, 0)
    top = max(top, 0)
    right = min(right, frame_width)
    bottom = min(bottom, frame_height)

    cropped_frame = frame[top:bottom, left:right]
    if cropped_frame.size == 0:
        cropped_frame = frame.copy()

    evidence_frame = cropped_frame.copy()
    evidence_height, evidence_width = evidence_frame.shape[:2]
    relative_x1 = max(x1 - left, 0)
    relative_y1 = max(y1 - top, 0)
    relative_x2 = min(x2 - left, evidence_width - 1)
    relative_y2 = min(y2 - top, evidence_height - 1)
    cv2.rectangle(evidence_frame, (relative_x1, relative_y1), (relative_x2, relative_y2), (0, 0, 255), 4)

    header_height = max(52, min(84, evidence_height // 4 if evidence_height > 0 else 52))
    header_overlay = evidence_frame.copy()
    cv2.rectangle(header_overlay, (0, 0), (evidence_width, header_height), (0, 0, 0), -1)
    cv2.addWeighted(header_overlay, 0.65, evidence_frame, 0.35, 0.0, evidence_frame)

    banner_font = cv2.FONT_HERSHEY_DUPLEX
    banner_scale = max(min(evidence_width / 700.0, 0.95), 0.5)
    metadata_font = cv2.FONT_HERSHEY_SIMPLEX
    metadata_scale = max(min(evidence_width / 900.0, 0.65), 0.45)
    metadata_text = f"Track_ID: {track_id}  |  {started_at.strftime('%Y-%m-%d %H:%M:%S')}"
    (_, banner_text_height), banner_baseline = cv2.getTextSize(SAVED_VIOLATION_LABEL, banner_font, banner_scale, 2)
    (metadata_width, metadata_text_height), metadata_baseline = cv2.getTextSize(metadata_text, metadata_font, metadata_scale, 1)
    banner_y = max((header_height + banner_text_height) // 2 - banner_baseline, 26)
    metadata_y = max((header_height + metadata_text_height) // 2 - metadata_baseline, 24)

    cv2.putText(evidence_frame, SAVED_VIOLATION_LABEL, (10, banner_y), banner_font, banner_scale, (0, 0, 255), 2, cv2.LINE_AA)
    cv2.putText(
        evidence_frame,
        metadata_text,
        (max(evidence_width - metadata_width - 10, 10), metadata_y),
        metadata_font,
        metadata_scale,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )
    cv2.putText(
        evidence_frame,
        f"Conf: {confidence:.2f}",
        (10, min(evidence_height - 12, relative_y2 + 24)),
        metadata_font,
        metadata_scale,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )

    snapshot_path = VIOLATIONS_DIR / f"Violation_ID_{track_id}_{started_at.strftime('%Y%m%d_%H%M%S')}.jpg"
    cv2.imwrite(str(snapshot_path), evidence_frame)
    return snapshot_path


def build_inspector_panel(
    roi_data: list[tuple[int, np.ndarray, np.ndarray, float]],
    thumb_w: int = INSPECTOR_THUMB_W,
    thumb_h: int = INSPECTOR_THUMB_H,
    brightness_threshold: float = 200.0,
) -> np.ndarray:
    """Build a side-by-side RAW vs CLAHE-enhanced diagnostic panel.

    Each row shows:
      ID label + Brightness Mean + mode tag
      [ RAW thumbnail ] | [ CLAHE-enhanced thumbnail ]

    Args:
        roi_data: list of (track_id, raw_crop, enhanced_crop, brightness_mean)
        thumb_w / thumb_h: pixel size for each thumbnail
        brightness_threshold: mean brightness above which mode reads HIGH

    Returns:
        BGR image ready for cv2.imshow.
    """
    _PANEL_BG   = (30, 30, 30)
    _LABEL_H    = 22
    _HEADER_H   = 26
    _ROW_PAD    = 4
    _SEP_W      = 4   # gap between RAW and ENHANCED columns
    _FONT       = cv2.FONT_HERSHEY_SIMPLEX

    panel_w = 8 + thumb_w + _SEP_W + thumb_w + 8
    row_h   = _LABEL_H + thumb_h + _ROW_PAD
    panel_h = _HEADER_H + max(len(roi_data), 1) * row_h + 8

    panel = np.full((panel_h, panel_w, 3), _PANEL_BG, dtype=np.uint8)

    # Header bar
    cv2.putText(panel, "Head ROI Inspector", (8, 17), _FONT, 0.48,
                (200, 200, 200), 1, cv2.LINE_AA)
    cv2.line(panel, (0, _HEADER_H), (panel_w, _HEADER_H), (70, 70, 70), 1)

    if not roi_data:
        cv2.putText(panel, "No workers in frame", (8, _HEADER_H + 20), _FONT,
                    0.44, (110, 110, 110), 1, cv2.LINE_AA)
        return panel

    col_raw_x = 8
    col_enh_x = 8 + thumb_w + _SEP_W

    for idx, (track_id, raw_crop, enhanced_crop, brightness_mean) in enumerate(roi_data):
        row_y  = _HEADER_H + idx * row_h
        thumb_y = row_y + _LABEL_H

        # Row label with brightness mode indicator
        if brightness_mean > brightness_threshold:
            mode_tag    = "[HIGH]"
            label_color = (80, 200, 255)   # orange-ish in BGR
        else:
            mode_tag    = "[NORMAL]"
            label_color = (140, 220, 140)  # soft green in BGR
        label_text = f"ID={track_id}  Brightness={brightness_mean:.0f}  {mode_tag}"
        cv2.putText(panel, label_text, (col_raw_x, row_y + 15), _FONT, 0.42,
                    label_color, 1, cv2.LINE_AA)

        # RAW thumbnail
        raw_thumb = cv2.resize(raw_crop, (thumb_w, thumb_h),
                               interpolation=cv2.INTER_LINEAR)
        panel[thumb_y:thumb_y + thumb_h, col_raw_x:col_raw_x + thumb_w] = raw_thumb
        cv2.putText(panel, "RAW",
                    (col_raw_x + 4, thumb_y + thumb_h - 5),
                    _FONT, 0.37, (180, 180, 180), 1, cv2.LINE_AA)

        # CLAHE-enhanced thumbnail
        enh_thumb = cv2.resize(enhanced_crop, (thumb_w, thumb_h),
                               interpolation=cv2.INTER_LINEAR)
        panel[thumb_y:thumb_y + thumb_h, col_enh_x:col_enh_x + thumb_w] = enh_thumb
        cv2.putText(panel, "CLAHE",
                    (col_enh_x + 4, thumb_y + thumb_h - 5),
                    _FONT, 0.37, (80, 255, 200), 1, cv2.LINE_AA)

    return panel


def main() -> None:
    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"Trained model not found: {MODEL_PATH}")
    model_size = MODEL_PATH.stat().st_size
    if model_size != EXPECTED_MODEL_BYTES:
        raise RuntimeError(
            f"Unexpected model size for {MODEL_PATH}: {model_size} bytes "
            f"(expected {EXPECTED_MODEL_BYTES})"
        )
    print(f"[webcam_demo] Model Path: {MODEL_PATH} ({model_size} bytes)")
    if not PERSON_MODEL_PATH.exists():
        raise FileNotFoundError(f"Person tracking model not found: {PERSON_MODEL_PATH}")

    system = HelmetSystem(
        helmet_model_path=MODEL_PATH,
        person_model_path=PERSON_MODEL_PATH,
        inference_image_size=INFERENCE_IMAGE_SIZE,
        helmet_confidence_threshold=HELMET_CONFIDENCE_THRESHOLD,
        person_confidence_threshold=PERSON_TRACK_CONFIDENCE,
        person_iou_threshold=PERSON_TRACK_IOU,
        blur_threshold=BLUR_THRESHOLD,
        head_roi_ratio=HEAD_ROI_RATIO,
        validation_window_size=VALIDATION_WINDOW_SIZE,
        validation_required_hits=VALIDATION_REQUIRED_HITS,
        device="cpu",
        temporal_validator=TrackViolationValidator(
            window_size=VALIDATION_WINDOW_SIZE,
            required_hits=VALIDATION_REQUIRED_HITS,
        ),
    )

    capture = cv2.VideoCapture(0)
    capture.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    if not capture.isOpened():
        raise RuntimeError("Could not open webcam source 0.")

    cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(WINDOW_NAME, 1280, 720)
    cv2.namedWindow(ENHANCED_WINDOW_NAME, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(ENHANCED_WINDOW_NAME, 480, 270)
    cv2.namedWindow(INSPECTOR_WINDOW_NAME, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(INSPECTOR_WINDOW_NAME, INSPECTOR_THUMB_W * 2 + 20, 350)
    cv2.moveWindow(INSPECTOR_WINDOW_NAME, 1300, 0)  # position to the right of the main window

    # Higher capture/display resolution improves demo clarity but can reduce FPS on CPU.
    # Keep YOLO inference at imgsz=640; if frame resizing is needed before inference,
    # use cv2.resize(..., interpolation=cv2.INTER_LINEAR) for a balanced speed/quality tradeoff.

    preprocessor = Preprocessor(
        blur_threshold=PREPROCESSOR_BLUR_THRESHOLD,
        ssim_threshold=PREPROCESSOR_SSIM_THRESHOLD,
        ssim_check_interval=PREPROCESSOR_SSIM_INTERVAL,
    )

    previous_frame_time = time.perf_counter()
    previous_frame_for_glitch: cv2.typing.MatLike | None = None
    active_events: dict[int, tuple[datetime, float]] = {}
    alert_stop_event: threading.Event | None = None
    last_helmet_detections: list[Detection] = []
    last_validation_results: list[PersonValidationResult] = []
    last_person_status_labels: dict[int, str] = {}
    last_roi_inspector_data: list[tuple[int, np.ndarray, np.ndarray, float]] = []

    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                print("Failed to read frame from webcam.")
                break

            preprocess_result = preprocessor.process(frame, previous_frame_for_glitch)
            previous_frame_for_glitch = frame
            display_frame = frame.copy()
            enhanced_frame = enhance_frame(preprocess_result.cleaned_frame)
            print(
                f"Status: Blur={preprocess_result.blur_score:.2f}, "
                f"SSIM={preprocess_result.ssim_score:.3f}, "
                f"Process={preprocess_result.should_process}"
            )
            current_time = time.perf_counter()

            if preprocess_result.should_process:
                frame_result = system.process_frame(enhanced_frame)
                # Apply per-class confidence filtering: discard detections whose
                # confidence is below the class-specific threshold.  This prevents
                # ambiguous low-score "no helmet" predictions from being treated as
                # violations while still preserving low-scoring helmet detections.
                thresholded_detections = filter_detections_by_class_threshold(
                    frame_result.helmet_detections,
                    per_class_thresholds=CLASS_THRESHOLDS,
                )
                # Spatial constraint: only keep headwear detections around the head zone.
                last_helmet_detections = filter_detections_by_spatial_constraint(
                    thresholded_detections,
                    frame_result.tracked_persons,
                    head_top_ratio=HEAD_SPATIAL_TOP_RATIO,
                )
                # Unified rule: violation only when other_hat/no_helmet remains after
                # threshold + spatial filtering and no valid helmet is present.
                last_validation_results, last_person_status_labels = build_person_validation_results(
                    frame_result.tracked_persons,
                    last_helmet_detections,
                    head_top_ratio=HEAD_SPATIAL_TOP_RATIO,
                )

                # Collect head-ROI crops: apply adaptive CLAHE per person, log brightness,
                # and store (raw, enhanced) pairs for the Inspector Window.
                _frame_roi_data: list[tuple[int, np.ndarray, np.ndarray, float]] = []
                for _r in last_validation_results:
                    _rx1, _ry1, _rx2, _ry2 = _r.head_roi
                    if _rx2 > _rx1 and _ry2 > _ry1:
                        _roi_crop = frame[_ry1:_ry2, _rx1:_rx2]
                        if _roi_crop.size > 0:
                            _enhanced, _brightness = preprocessor.apply_clahe_to_region(
                                _roi_crop.copy(),
                                debug_label=f"Person ID={_r.track_id}",
                            )
                            _frame_roi_data.append(
                                (_r.track_id, _roi_crop.copy(), _enhanced, _brightness)
                            )
                last_roi_inspector_data = _frame_roi_data

                current_confirmed = {
                    result.track_id: result
                    for result in last_validation_results
                    if result.confirmed_violation
                }
                visible_track_ids = {result.track_id for result in last_validation_results}

                ended_track_ids = set(active_events) - set(current_confirmed)
                for track_id in ended_track_ids:
                    if track_id not in visible_track_ids or track_id not in current_confirmed:
                        started_at, started_perf = active_events.pop(track_id)
                        finalize_violation(track_id, started_at, started_perf)

                if not active_events and alert_stop_event is not None:
                    alert_stop_event.set()
                    alert_stop_event = None

                new_confirmed_ids = set(current_confirmed) - set(active_events)
                for track_id in new_confirmed_ids:
                    result = current_confirmed[track_id]
                    started_at = datetime.now()
                    started_perf = time.perf_counter()
                    active_events[track_id] = (started_at, started_perf)
                    log_violation_started()
                    snapshot_path = save_violation_crop(
                        frame,
                        track_id,
                        result.person_box,
                        result.confidence,
                        started_at,
                    )
                    print(f"Violation snapshot saved: {snapshot_path}")
                    if alert_stop_event is None or alert_stop_event.is_set():
                        alert_stop_event = threading.Event()
                        threading.Thread(target=alert_sound_loop, args=(alert_stop_event,), daemon=True).start()
                    speak_warning_async()

            for detection in last_helmet_detections:
                draw_detection(display_frame, detection)

            for result in last_validation_results:
                draw_person_result(
                    display_frame,
                    result,
                    last_person_status_labels.get(result.track_id, "No Helmet"),
                )

            elapsed = current_time - previous_frame_time
            fps = 1.0 / elapsed if elapsed > 0 else 0.0
            previous_frame_time = current_time

            cv2.putText(display_frame, f"FPS: {fps:.1f}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2, cv2.LINE_AA)
            global_violation = any(result.confirmed_violation for result in last_validation_results)
            global_status = "VIOLATION" if global_violation else "SAFE"
            global_status_color = (0, 0, 255) if global_violation else (0, 255, 0)
            cv2.putText(
                display_frame,
                f"Status: {global_status}",
                (10, 65),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                global_status_color,
                2,
                cv2.LINE_AA,
            )
            draw_preprocessing_overlay(
                display_frame,
                preprocess_result.blur_score,
                preprocess_result.ssim_score,
                preprocess_result.is_blurred,
                preprocess_result.is_glitch,
                not preprocess_result.should_process,
            )

            if active_events:
                draw_violation_overlay(display_frame, current_time)
                cv2.putText(
                    display_frame,
                    f"Confirmed IDs: {', '.join(str(track_id) for track_id in sorted(active_events))}",
                    (10, 100),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (0, 0, 255),
                    2,
                    cv2.LINE_AA,
                )

            cv2.imshow(WINDOW_NAME, display_frame)
            cv2.imshow(
                ENHANCED_WINDOW_NAME,
                cv2.resize(enhanced_frame, (480, 270), interpolation=cv2.INTER_LINEAR),
            )

            # Inspector Window: show RAW vs CLAHE-enhanced head ROI for each tracked person.
            # Diagnostic only — no re-inference is performed on these crops.
            inspector_panel = build_inspector_panel(last_roi_inspector_data)
            cv2.imshow(INSPECTOR_WINDOW_NAME, inspector_panel)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        if alert_stop_event is not None:
            alert_stop_event.set()
        for track_id, (started_at, started_perf) in list(active_events.items()):
            finalize_violation(track_id, started_at, started_perf)
        capture.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
