from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Sequence

import cv2
import numpy as np
from ultralytics.engine.results import Results


HEAD_ROI_RATIO = 0.35

# ---------------------------------------------------------------------------
# Generalised Material Analysis constants
# Replaces the old single-threshold gloss approach to handle dark, white, and
# over-exposed helmets with a unified colour-invariant M-Score pipeline.
# ---------------------------------------------------------------------------
# Structuring element size for the White Top-Hat transform.  Should be larger
# than the expected highlight spot but smaller than the helmet dome.
_MAT_TOPHAT_KSIZE: int = 15
# Smallest connected-component (px²) in the Top-Hat output treated as a real spot.
_MAT_MIN_CLUSTER_AREA: int = 8
# Upper bound on highlight cluster count; more than this looks like noise.
_MAT_MAX_CLUSTERS: int = 10
# Minimum circularity (4π·A/P²) for the largest cluster to be dome-consistent.
_MAT_MIN_CIRCULARITY: float = 0.25
# Contribution weights for the three signal streams.
_MAT_SKEWNESS_WEIGHT: float = 0.25   # right-skew → dark/glossy helmet highlights
_MAT_STD_WEIGHT:      float = 0.25   # local variance → white/light helmet edges
_MAT_TOPHAT_WEIGHT:   float = 0.50   # curvature-consistent bright spots (colour-invariant)
# Unified M-Score threshold above which the material analysis overrides YOLO.
MATERIAL_SCORE_THRESHOLD: float = 0.50


@dataclass(frozen=True)
class MaterialAnalysisResult:
    """Generalised material / surface analysis result for a single head-ROI crop.

    Works for any helmet colour (yellow, white, blue, black) and any exposure
    level by operating on a contrast-stretched brightness channel.

    All scores are in [0, 1] unless noted.  ``is_helmet_material`` summarises
    whether the composite M-Score clears ``MATERIAL_SCORE_THRESHOLD``.
    """

    # Step 1 – Contrast Stretching
    stretch_range: float            # v_max − v_min before normalisation
    # Step 2 – Peak Analysis
    intensity_std: float            # std-dev of stretched V channel
    intensity_skewness: float       # Fisher skewness (right tail → dark helmet gloss)
    local_variance_score: float     # normalised mean local variance (light helmet edges)
    skewness_score: float           # normalised skewness contribution [0, 1]
    # Step 3 – Morphological Top-Hat
    tophat_cluster_count: int       # bright highlight spots found after Top-Hat
    tophat_circularity: float       # 4π·A/P² of largest spot (dome-consistency)
    tophat_score: float             # combined cluster + curvature score [0, 1]
    # Step 4 – Unified M-Score
    m_score: float                  # weighted composite score [0, 1]
    is_helmet_material: bool        # True when m_score ≥ MATERIAL_SCORE_THRESHOLD


@dataclass(frozen=True)
class Detection:
    class_name: str
    bounding_box: tuple[float, float, float, float]
    confidence: float
    track_id: int | None = None


@dataclass(frozen=True)
class HelmetViolation:
    subject_box: tuple[float, float, float, float]
    head_roi: tuple[float, float, float, float]
    aspect_ratio: float
    track_id: int | None
    confidence: float
    predicted_class: str
    violation: bool
    matched_helmet_box: tuple[float, float, float, float] | None
    best_iou: float


@dataclass(frozen=True)
class TrackedPerson:
    track_id: int
    confidence: float
    bounding_box: tuple[int, int, int, int]


@dataclass(frozen=True)
class PersonValidationResult:
    track_id: int
    confidence: float
    person_box: tuple[int, int, int, int]
    head_roi: tuple[int, int, int, int]
    best_helmet_overlap: float
    potential_violation: bool
    confirmed_violation: bool
    violation_ratio: float
    # Material analysis fields (optional; default 0 / False when frame not provided).
    material_score: float = 0.0      # unified M-Score from analyse_head_roi_material
    material_override: bool = False  # True when M-Score flipped a YOLO miss to SAFE


def analyse_head_roi_material(
    roi_bgr,
    tophat_ksize=_MAT_TOPHAT_KSIZE,
    min_cluster_area=_MAT_MIN_CLUSTER_AREA,
    max_clusters=_MAT_MAX_CLUSTERS,
    min_circularity=_MAT_MIN_CIRCULARITY,
    score_threshold=MATERIAL_SCORE_THRESHOLD,
):
    """Generalised material analysis for any helmet colour or exposure level.

    Pipeline
    --------
    1. Contrast Stretching: Min-Max normalise the V channel so dark and
       over-exposed helmets share a common 0-255 dynamic range.
    2. Peak Analysis: Std-Dev and Skewness of the stretched V channel.
       High Skewness = rare bright highlights on darker surface (dark/glossy).
       High Local Variance = sharp reflection edges (white/light helmets).
    3. White Top-Hat: isolates small bright spots smaller than the kernel.
       Curvature of the largest spot is checked for helmet-dome consistency.
    4. Unified M-Score: Skewness 25% + Local Variance 25% + Top-Hat 50%.
       If M-Score >= MATERIAL_SCORE_THRESHOLD -> is_helmet_material=True.

    Returns
    -------
    MaterialAnalysisResult
    """
    _empty = MaterialAnalysisResult(
        stretch_range=0.0, intensity_std=0.0, intensity_skewness=0.0,
        local_variance_score=0.0, skewness_score=0.0,
        tophat_cluster_count=0, tophat_circularity=0.0, tophat_score=0.0,
        m_score=0.0, is_helmet_material=False,
    )
    if roi_bgr is None or roi_bgr.size == 0:
        return _empty

    # Step 1: Color-invariant V channel + Min-Max Contrast Stretch
    hsv = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2HSV)
    v_channel = hsv[:, :, 2]
    v_min = int(v_channel.min())
    v_max = int(v_channel.max())
    stretch_range = float(v_max - v_min)
    if stretch_range < 1.0:
        return _empty
    stretched = np.clip(
        (v_channel.astype(np.float32) - v_min) / stretch_range * 255.0, 0, 255
    ).astype(np.uint8)

    # Step 2: Peak Analysis
    v_flat = stretched.ravel().astype(np.float64)
    intensity_std      = float(v_flat.std())
    mu                 = float(v_flat.mean())
    sigma              = float(v_flat.std())
    # Fisher skewness: positive = right-tailed (dark glossy helmet highlights)
    intensity_skewness = float(((v_flat - mu) ** 3).mean() / (sigma ** 3 + 1e-6))
    skewness_score     = float(np.clip(max(intensity_skewness, 0.0) / 4.0, 0.0, 1.0))

    v_f32   = stretched.astype(np.float32) / 255.0
    mean_sq = cv2.boxFilter(v_f32 * v_f32, ddepth=-1, ksize=(9, 9))
    sq_mean = cv2.boxFilter(v_f32, ddepth=-1, ksize=(9, 9)) ** 2
    local_var            = np.maximum(mean_sq - sq_mean, 0.0)
    # High local variance = sharp reflection edges (white/light helmets).
    std_score            = float(np.clip(intensity_std / 80.0, 0.0, 1.0))
    local_variance_score = float(np.clip(local_var.mean() * 8.0, 0.0, 1.0)) * std_score

    # Step 3: White Top-Hat morphological transform
    # Top-Hat = I - open(I): isolates bright peaks smaller than the kernel.
    k_tophat = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (tophat_ksize, tophat_ksize))
    tophat   = cv2.morphologyEx(stretched, cv2.MORPH_TOPHAT, k_tophat)

    tophat_max = int(tophat.max())
    if tophat_max < 5:
        tophat_cluster_count = 0
        tophat_circularity   = 0.0
        tophat_score         = 0.0
    else:
        th_value = max(int(tophat_max * 0.10), 5)
        _, tophat_mask = cv2.threshold(tophat, th_value, 255, cv2.THRESH_BINARY)
        k_close     = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        tophat_mask = cv2.morphologyEx(tophat_mask, cv2.MORPH_CLOSE, k_close)

        num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(
            tophat_mask, connectivity=8
        )
        valid = [
            i for i in range(1, num_labels)
            if stats[i, cv2.CC_STAT_AREA] >= min_cluster_area
        ]
        tophat_cluster_count = len(valid)

        if tophat_cluster_count == 0:
            cluster_score = 0.0
        elif tophat_cluster_count <= max_clusters:
            cluster_score = float(1.0 - (tophat_cluster_count - 1) / max_clusters)
        else:
            cluster_score = 0.0

        # Circularity: rounded helmet dome -> compact, roughly circular highlight.
        tophat_circularity = 0.0
        if valid:
            largest_idx = max(valid, key=lambda i: stats[i, cv2.CC_STAT_AREA])
            lmask = (labels == largest_idx).astype(np.uint8) * 255
            contours, _ = cv2.findContours(
                lmask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
            )
            if contours:
                area      = cv2.contourArea(contours[0])
                perimeter = cv2.arcLength(contours[0], True)
                if perimeter > 0:
                    tophat_circularity = min(
                        float(4.0 * np.pi * area / (perimeter ** 2)), 1.0
                    )

        circ_score   = float(np.clip(
            tophat_circularity / max(min_circularity, 1e-6), 0.0, 1.0
        ))
        tophat_score = float(0.50 * cluster_score + 0.50 * circ_score)

    # Step 4: Unified M-Score
    # Skewness 25% (dark helmets) + Local Variance 25% (light helmets)
    # + Top-Hat curvature 50% (colour-independent).
    m_score = float(np.clip(
        _MAT_SKEWNESS_WEIGHT * skewness_score
        + _MAT_STD_WEIGHT    * local_variance_score
        + _MAT_TOPHAT_WEIGHT * tophat_score,
        0.0, 1.0,
    ))

    return MaterialAnalysisResult(
        stretch_range=stretch_range,
        intensity_std=intensity_std,
        intensity_skewness=intensity_skewness,
        local_variance_score=local_variance_score,
        skewness_score=skewness_score,
        tophat_cluster_count=tophat_cluster_count,
        tophat_circularity=tophat_circularity,
        tophat_score=tophat_score,
        m_score=m_score,
        is_helmet_material=m_score >= score_threshold,
    )


def validate_helmet_violations(
    detections,
    head_roi_ratio=HEAD_ROI_RATIO,
    min_helmet_iou=0.5,
):
    headwear_detections = [
        d for d in detections
        if d.class_name in {"helmet", "other_hat", "no_helmet"}
    ]
    helmet_detections = [d for d in headwear_detections if d.class_name == 'helmet']

    violations = []
    for headwear_detection in headwear_detections:
        x1, y1, x2, y2 = headwear_detection.bounding_box
        width  = max(x2 - x1, 1e-6)
        height = max(y2 - y1, 1e-6)
        aspect_ratio = height / width
        head_roi = (x1, y1, x2, y1 + (height * head_roi_ratio))

        best_iou = 0.0
        matched_helmet_box = None
        for helmet_detection in helmet_detections:
            iou_score = _calculate_iou(head_roi, helmet_detection.bounding_box)
            if iou_score > best_iou:
                best_iou           = iou_score
                matched_helmet_box = helmet_detection.bounding_box

        has_approved_helmet = (
            headwear_detection.class_name == 'helmet' or best_iou >= min_helmet_iou
        )
        violations.append(
            HelmetViolation(
                subject_box=headwear_detection.bounding_box,
                head_roi=head_roi,
                aspect_ratio=aspect_ratio,
                track_id=headwear_detection.track_id,
                confidence=headwear_detection.confidence,
                predicted_class=headwear_detection.class_name,
                violation=not has_approved_helmet,
                matched_helmet_box=matched_helmet_box if has_approved_helmet else None,
                best_iou=best_iou,
            )
        )

    return violations

def extract_detections_from_results(results: Results) -> list[Detection]:
    boxes = results.boxes
    if boxes is None or boxes.cls is None or boxes.xyxy is None:
        return []

    class_names = results.names
    track_ids: Iterable[int | None]
    if boxes.id is None:
        track_ids = [None] * len(boxes)
    else:
        track_ids = [int(track_id) for track_id in boxes.id.tolist()]

    confidences = [float(confidence) for confidence in boxes.conf.tolist()] if boxes.conf is not None else [0.0] * len(boxes)
    detections: list[Detection] = []
    for class_id, bounding_box, confidence, track_id in zip(
        boxes.cls.tolist(),
        boxes.xyxy.tolist(),
        confidences,
        track_ids,
    ):
        x1, y1, x2, y2 = (float(value) for value in bounding_box)
        detections.append(
            Detection(
                class_name=str(class_names[int(class_id)]).lower(),
                bounding_box=(x1, y1, x2, y2),
                confidence=confidence,
                track_id=track_id,
            )
        )

    return detections


def validate_helmet_violations_from_results(
    results: Results,
    head_roi_ratio: float = HEAD_ROI_RATIO,
    min_helmet_iou: float = 0.5,
) -> list[HelmetViolation]:
    detections = extract_detections_from_results(results)
    return validate_helmet_violations(
        detections,
        head_roi_ratio=head_roi_ratio,
        min_helmet_iou=min_helmet_iou,
    )


def evaluate_tracked_person_violations(
    persons: Sequence[TrackedPerson],
    helmet_detections: Sequence[Detection],
    confirmed_ratios: dict[int, float] | None = None,
    head_roi_ratio: float = HEAD_ROI_RATIO,
    min_head_iou: float = 0.1,
    frame: np.ndarray | None = None,
    material_score_threshold: float = MATERIAL_SCORE_THRESHOLD,
) -> list[PersonValidationResult]:
    """Evaluate per-person helmet violations with optional material-score override.

    When *frame* is supplied each person's head ROI is cropped and analysed by
    :func:`analyse_head_roi_material`.  If YOLOv8 gave a low IoU (potential
    violation) but the M-Score indicates helmet surface material is present
    (``m_score >= material_score_threshold``), the result is overridden to
    ``potential_violation=False`` (SAFE) and ``material_override=True`` is set.
    """
    # Rule Engine: compare helmet geometry only with the dynamic head ROI, not the
    # full person box. This suppresses false positives from helmets carried in hands
    # or hanging near the body and keeps validation strict: only class helmet is SAFE.
    helmet_boxes = np.array(
        [
            [
                float(detection.bounding_box[0]),
                float(detection.bounding_box[1]),
                float(detection.bounding_box[2]),
                float(detection.bounding_box[3]),
            ]
            for detection in helmet_detections
            if detection.class_name == "helmet"
        ],
        dtype=np.float32,
    )
    ratios = confirmed_ratios or {}
    head_rois = [build_head_roi(person.bounding_box, head_roi_ratio=head_roi_ratio) for person in persons]
    head_roi_matrix = np.array(head_rois, dtype=np.float32) if head_rois else np.empty((0, 4), dtype=np.float32)

    if len(head_roi_matrix) and len(helmet_boxes):
        iou_matrix = calculate_iou_matrix(head_roi_matrix, helmet_boxes)
        
        # Edge Case Fix: Occlusion / Hugging
        # Prevent one helmet from satisfying multiple people's Head ROI.
        best_person_for_helmet = iou_matrix.argmax(axis=0)
        mask = np.zeros_like(iou_matrix, dtype=bool)
        for h_idx, p_idx in enumerate(best_person_for_helmet):
            if iou_matrix[p_idx, h_idx] > 0:
                mask[p_idx, h_idx] = True
        iou_matrix = np.where(mask, iou_matrix, 0.0)
        
        best_overlaps = iou_matrix.max(axis=1).tolist()
    else:
        best_overlaps = [0.0] * len(persons)

    frame_h, frame_w = (frame.shape[:2] if frame is not None else (0, 0))

    validation_results: list[PersonValidationResult] = []
    for person, head_roi, best_overlap in zip(persons, head_rois, best_overlaps):
        would_violate = best_overlap < min_head_iou

        # ------------------------------------------------------------------
        # Material-score override (M-Score pipeline)
        # Only runs when:
        #   • a raw frame is available for cropping
        #   • YOLO is uncertain (would_violate is True)
        # analyse_head_roi_material handles dark, white, and over-exposed
        # helmets via contrast stretching + peak analysis + Top-Hat.
        # ------------------------------------------------------------------
        mat_score         = 0.0
        material_override = False
        if frame is not None and would_violate:
            rx1, ry1, rx2, ry2 = head_roi
            # Clamp ROI to frame bounds before slicing.
            rx1c = max(rx1, 0)
            ry1c = max(ry1, 0)
            rx2c = min(rx2, frame_w)
            ry2c = min(ry2, frame_h)
            if rx2c > rx1c and ry2c > ry1c:
                roi_crop = frame[ry1c:ry2c, rx1c:rx2c]
                if roi_crop.size > 0:
                    mat_result = analyse_head_roi_material(roi_crop)
                    mat_score  = mat_result.m_score
                    if mat_result.is_helmet_material:
                        would_violate     = False  # M-Score overrides YOLO miss
                        material_override = True
                        print(
                            f"[MaterialOverride] Person ID={person.track_id} "
                            f"M={mat_score:.2f} "
                            f"skew={mat_result.intensity_skewness:.2f} "
                            f"lvar={mat_result.local_variance_score:.2f} "
                            f"tophat={mat_result.tophat_score:.2f} "
                            f"circ={mat_result.tophat_circularity:.2f} → SAFE"
                        )

        validation_results.append(
            PersonValidationResult(
                # Keep BoT-SORT track continuity in the validation result payload.
                track_id=person.track_id,
                confidence=person.confidence,
                person_box=person.bounding_box,
                head_roi=head_roi,
                best_helmet_overlap=best_overlap,
                potential_violation=would_violate,
                confirmed_violation=person.track_id in ratios,
                violation_ratio=ratios.get(person.track_id, 0.0),
                material_score=mat_score,
                material_override=material_override,
            )
        )

    return validation_results


def build_head_roi(
    person_box: tuple[int, int, int, int],
    head_roi_ratio: float = HEAD_ROI_RATIO,
) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = person_box
    top = min(y1, y2)
    bottom = max(y1, y2)
    left = min(x1, x2)
    right = max(x1, x2)

    height = max(bottom - top, 1)
    width = max(right - left, 1)
    
    # Edge Case Fix: Dynamic Head ROI based on Aspect Ratio (Squat/Bend pose and Partial View)
    aspect_ratio = height / width
    dynamic_ratio = head_roi_ratio
    
    if aspect_ratio < 1.5:  
        # Person is wide (bending/squatting) or only partial torso is seen
        dynamic_ratio = head_roi_ratio * 0.7  # Shrink ROI to avoid stomach/hands
        
    roi_bottom = top + max(int(height * dynamic_ratio), 1)
    return (left, top, right, min(roi_bottom, bottom))


def calculate_overlap_ratio(
    box_a: tuple[int, int, int, int],
    box_b: tuple[int, int, int, int],
) -> float:
    # best_helmet_overlap is IoU between dynamic head ROI and each helmet box.
    ax1, ay1, ax2, ay2 = box_a
    bx1, by1, bx2, by2 = box_b
    return _calculate_iou(
        (float(ax1), float(ay1), float(ax2), float(ay2)),
        (float(bx1), float(by1), float(bx2), float(by2)),
    )


def calculate_iou_matrix(
    boxes_a: np.ndarray,
    boxes_b: np.ndarray,
) -> np.ndarray:
    if boxes_a.size == 0 or boxes_b.size == 0:
        return np.zeros((len(boxes_a), len(boxes_b)), dtype=np.float32)

    a_x1 = boxes_a[:, 0][:, None]
    a_y1 = boxes_a[:, 1][:, None]
    a_x2 = boxes_a[:, 2][:, None]
    a_y2 = boxes_a[:, 3][:, None]

    b_x1 = boxes_b[:, 0][None, :]
    b_y1 = boxes_b[:, 1][None, :]
    b_x2 = boxes_b[:, 2][None, :]
    b_y2 = boxes_b[:, 3][None, :]

    inter_x1 = np.maximum(a_x1, b_x1)
    inter_y1 = np.maximum(a_y1, b_y1)
    inter_x2 = np.minimum(a_x2, b_x2)
    inter_y2 = np.minimum(a_y2, b_y2)

    inter_w = np.maximum(inter_x2 - inter_x1, 0.0)
    inter_h = np.maximum(inter_y2 - inter_y1, 0.0)
    intersection = inter_w * inter_h

    area_a = np.maximum(a_x2 - a_x1, 0.0) * np.maximum(a_y2 - a_y1, 0.0)
    area_b = np.maximum(b_x2 - b_x1, 0.0) * np.maximum(b_y2 - b_y1, 0.0)
    union = area_a + area_b - intersection

    return np.where(union > 0.0, intersection / union, 0.0).astype(np.float32)


def _calculate_iou(
    box_a: tuple[float, float, float, float],
    box_b: tuple[float, float, float, float],
) -> float:
    ax1, ay1, ax2, ay2 = box_a
    bx1, by1, bx2, by2 = box_b

    inter_x1 = max(ax1, bx1)
    inter_y1 = max(ay1, by1)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)

    intersection_width = max(inter_x2 - inter_x1, 0.0)
    intersection_height = max(inter_y2 - inter_y1, 0.0)
    intersection_area = intersection_width * intersection_height
    if intersection_area <= 0.0:
        return 0.0

    area_a = max(ax2 - ax1, 0.0) * max(ay2 - ay1, 0.0)
    area_b = max(bx2 - bx1, 0.0) * max(by2 - by1, 0.0)
    union_area = area_a + area_b - intersection_area
    if union_area <= 0.0:
        return 0.0

    return intersection_area / union_area