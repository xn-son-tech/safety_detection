from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = PROJECT_ROOT / "helmet_v2_final.pt"
PERSON_MODEL_PATH = PROJECT_ROOT / "yolov8n.pt"
INPUT_IMAGES_DIR = PROJECT_ROOT / "test_inputs" / "images"
EXPECTED_MODEL_BYTES = 6_262_257

THRESHOLDS = {
    "helmet": 0.30,
    "other_hat": 0.45,
    "no_helmet": 0.60,
}
SPATIAL_TOP_RATIO = 0.35

CLAHE = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))


@dataclass(frozen=True)
class Detection:
    class_name: str
    confidence: float
    box: tuple[float, float, float, float]


@dataclass(frozen=True)
class PersonDecision:
    person_box: tuple[int, int, int, int]
    head_box: tuple[int, int, int, int]
    status_label: str
    is_violation: bool


def normalize_class_name(name: str) -> str:
    return name.lower().replace(" ", "_")


def enhance_frame(frame: np.ndarray) -> np.ndarray:
    lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
    l_channel, a_channel, b_channel = cv2.split(lab)
    l_channel = CLAHE.apply(l_channel)
    enhanced_lab = cv2.merge((l_channel, a_channel, b_channel))
    enhanced = cv2.cvtColor(enhanced_lab, cv2.COLOR_LAB2BGR)
    blur = cv2.GaussianBlur(enhanced, (5, 5), 1.0)
    sharpened = cv2.addWeighted(enhanced, 1.5, blur, -0.5, 0)
    return np.clip(sharpened, 0, 255).astype(np.uint8)


def in_head_top_zone(det: Detection, person_box: tuple[int, int, int, int]) -> bool:
    x1, y1, x2, y2 = det.box
    cx = 0.5 * (x1 + x2)
    cy = 0.5 * (y1 + y2)
    px1, py1, px2, py2 = person_box
    head_bottom = py1 + int(max(py2 - py1, 1) * SPATIAL_TOP_RATIO)
    return px1 <= cx <= px2 and py1 <= cy <= head_bottom


def parse_detections(result) -> list[Detection]:
    boxes = result.boxes
    if boxes is None or boxes.xyxy is None or boxes.cls is None or boxes.conf is None:
        return []

    detections: list[Detection] = []
    for box in boxes:
        class_id = int(box.cls.item())
        class_name = normalize_class_name(str(result.names[class_id]))
        confidence = float(box.conf.item())
        x1, y1, x2, y2 = (float(v) for v in box.xyxy[0].tolist())
        detections.append(Detection(class_name=class_name, confidence=confidence, box=(x1, y1, x2, y2)))
    return detections


def parse_person_boxes(result) -> list[tuple[int, int, int, int]]:
    boxes = result.boxes
    if boxes is None or boxes.xyxy is None:
        return []
    person_boxes: list[tuple[int, int, int, int]] = []
    for box in boxes.xyxy.tolist():
        x1, y1, x2, y2 = (int(v) for v in box)
        person_boxes.append((x1, y1, x2, y2))
    return person_boxes


def filter_detections(detections: list[Detection], person_boxes: list[tuple[int, int, int, int]]) -> list[Detection]:
    thresholded = [d for d in detections if d.confidence >= THRESHOLDS.get(d.class_name, 1.0)]
    if not person_boxes:
        return []

    filtered: list[Detection] = []
    for d in thresholded:
        if d.class_name in {"helmet", "other_hat", "no_helmet"}:
            if any(in_head_top_zone(d, pb) for pb in person_boxes):
                filtered.append(d)
        else:
            filtered.append(d)
    return filtered


def evaluate_persons(
    person_boxes: list[tuple[int, int, int, int]],
    detections: list[Detection],
) -> list[PersonDecision]:
    decisions: list[PersonDecision] = []
    for person_box in person_boxes:
        px1, py1, px2, py2 = person_box
        head_bottom = py1 + int(max(py2 - py1, 1) * SPATIAL_TOP_RATIO)
        head_box = (px1, py1, px2, head_bottom)
        head_detections = [d for d in detections if in_head_top_zone(d, person_box)]

        has_helmet = any(d.class_name == "helmet" for d in head_detections)
        has_other_hat = any(d.class_name == "other_hat" for d in head_detections)
        has_no_helmet = any(d.class_name == "no_helmet" for d in head_detections)

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

        decisions.append(
            PersonDecision(
                person_box=person_box,
                head_box=head_box,
                status_label=status_label,
                is_violation=is_violation,
            )
        )
    return decisions


def draw(frame: np.ndarray, decisions: list[PersonDecision], detections: list[Detection]) -> np.ndarray:
    out = frame.copy()
    for decision in decisions:
        px1, py1, px2, py2 = decision.person_box
        hx1, hy1, hx2, hy2 = decision.head_box
        if decision.status_label in {"Helmet", "Safe"}:
            person_color = (0, 255, 0)
        elif decision.status_label == "Other Hat":
            person_color = (0, 215, 255)
        else:
            person_color = (0, 0, 255)

        cv2.rectangle(out, (px1, py1), (px2, py2), person_color, 2)
        cv2.rectangle(out, (hx1, hy1), (hx2, hy2), (255, 220, 0), 2)
        state = "VIOLATION" if decision.is_violation else "SAFE"
        cv2.putText(
            out,
            f"{decision.status_label} - {state}",
            (px1, max(20, py1 - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            person_color,
            2,
            cv2.LINE_AA,
        )

    colors = {
        "helmet": (0, 255, 0),
        "other_hat": (0, 255, 255),
        "no_helmet": (0, 0, 255),
    }
    for d in detections:
        x1, y1, x2, y2 = (int(v) for v in d.box)
        color = colors.get(d.class_name, (255, 255, 255))
        cv2.rectangle(out, (x1, y1), (x2, y2), color, 2)
        cv2.putText(out, f"{d.class_name} {d.confidence:.2f}", (x1, max(20, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2, cv2.LINE_AA)

    has_violation = any(decision.is_violation for decision in decisions)
    status = "VIOLATION" if has_violation else "SAFE"
    status_color = (0, 0, 255) if has_violation else (0, 255, 0)
    cv2.putText(out, status, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1.0, status_color, 2, cv2.LINE_AA)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Run unified helmet pipeline on one image")
    parser.add_argument(
        "--source",
        required=True,
        help="Input image path. Relative paths are resolved from test_inputs/images/",
    )
    args = parser.parse_args()

    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"Model not found: {MODEL_PATH}")
    model_size = MODEL_PATH.stat().st_size
    if model_size != EXPECTED_MODEL_BYTES:
        raise RuntimeError(f"Unexpected model size: {model_size} bytes (expected {EXPECTED_MODEL_BYTES})")
    print(f"[test_image] Model Path: {MODEL_PATH} ({model_size} bytes)")

    if not PERSON_MODEL_PATH.exists():
        raise FileNotFoundError(f"Person model not found: {PERSON_MODEL_PATH}")
    if not INPUT_IMAGES_DIR.exists():
        raise FileNotFoundError(f"Input images folder not found: {INPUT_IMAGES_DIR}")

    image_path = Path(args.source)
    if not image_path.is_absolute():
        image_path = INPUT_IMAGES_DIR / image_path
    frame = cv2.imread(str(image_path))
    if frame is None:
        raise RuntimeError(f"Failed to read image: {image_path}")

    enhanced = enhance_frame(frame)
    helmet_model = YOLO(str(MODEL_PATH))
    person_model = YOLO(str(PERSON_MODEL_PATH))

    helmet_result = helmet_model.predict(enhanced, conf=min(THRESHOLDS.values()), iou=0.45, verbose=False)[0]
    person_result = person_model.predict(enhanced, classes=[0], conf=0.25, iou=0.45, verbose=False)[0]

    detections = parse_detections(helmet_result)
    person_boxes = parse_person_boxes(person_result)
    filtered = filter_detections(detections, person_boxes)
    decisions = evaluate_persons(person_boxes, filtered)

    output = draw(enhanced, decisions, filtered)
    out_dir = PROJECT_ROOT / "test_results" / "images"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{image_path.stem}_result.jpg"
    cv2.imwrite(str(out_path), output)
    print(f"Saved: {out_path}")


if __name__ == "__main__":
    main()
