import cv2
import threading
import requests
import base64
import time
import argparse
import os
import numpy as np
from datetime import datetime, timezone
from flask import Flask, Response

from ai_helmet_detection.pipeline import HelmetSystem
from ai_helmet_detection.core_detection.preprocessor import Preprocessor
from ai_helmet_detection.tracking.yolo_tracker import filter_detections_by_class_threshold
from ai_helmet_detection.rule_engine import Detection, PersonValidationResult, TrackedPerson

app = Flask(__name__)

# Global state for MJPEG stream
current_frame = None
CLASS_THRESHOLDS = {
    "helmet": 0.25,
    "other hat": 0.25,
    "no helmet": 0.25,
}
HEAD_SPATIAL_TOP_RATIO = 0.35
PERSON_TRACK_CONFIDENCE = 0.25
PERSON_TRACK_IOU = 0.45
HELMET_CONFIDENCE_THRESHOLD = 0.25
VALIDATION_WINDOW_SIZE = 30
VALIDATION_REQUIRED_HITS = 24
PREPROCESSOR_BLUR_THRESHOLD = 30.0
PREPROCESSOR_SSIM_THRESHOLD = 0.3
PREPROCESSOR_SSIM_INTERVAL = 3


def _normalize_class_name(class_name: str) -> str:
    return class_name.lower().replace(" ", "_")


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

        if has_helmet:
            status_label = "Helmet"
            is_violation = False
        elif has_other_hat:
            status_label = "Other Hat"
            is_violation = True
        elif has_no_helmet:
            status_label = "No Helmet"
            is_violation = True
        else:
            status_label = "No Helmet"
            is_violation = True

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


def _draw_detection(frame, detection: Detection) -> None:
    x1, y1, x2, y2 = (int(value) for value in detection.bounding_box)
    color_map = {"helmet": (0, 255, 0), "other hat": (0, 255, 255), "no helmet": (0, 0, 255)}
    color = color_map.get(detection.class_name, (255, 255, 255))
    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
    text = f"{detection.class_name} {detection.confidence:.2f}"
    cv2.putText(frame, text, (x1, max(y1 - 8, 20)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)


def _draw_person_result(frame, result: PersonValidationResult, status_label: str) -> None:
    if status_label in {"Helmet", "Safe"}:
        box_color = (0, 255, 0)
    elif status_label == "Other Hat":
        box_color = (0, 215, 255)
    else:
        box_color = (0, 0, 255)

    x1, y1, x2, y2 = result.person_box
    rx1, ry1, rx2, ry2 = result.head_roi
    cv2.rectangle(frame, (x1, y1), (x2, y2), box_color, 1)
    cv2.rectangle(frame, (rx1, ry1), (rx2, ry2), (255, 255, 0), 2)
    state = "VIOLATION" if result.confirmed_violation else "SAFE"
    cv2.putText(
        frame,
        f"ID {result.track_id} {status_label} {state}",
        (rx1, max(ry1 - 10, 20)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        box_color,
        2,
    )


def _compose_overlay_on_frame(
    base: np.ndarray,
    overlay_detections: list[Detection],
    overlay_validation: list[PersonValidationResult],
    overlay_labels: dict[int, str],
    ref_shape: tuple[int, int] | None,
) -> np.ndarray:
    """Vẽ overlay lên khung hình *hiện tại* (luôn là frame camera mới nhất).

    Tọa độ box gắn với ref_shape lúc AI chạy; nếu độ phân giải đổi thì scale.
    Cùng ý tưởng với webcam_demo: video mượt, box theo kết quả AI gần nhất
    (có thể lệch vài pixel nếu vật thể di chuyển nhanh — không còn hiện tượng tua ngược).
    """
    out = base.copy()
    if ref_shape is None:
        return out
    rh, rw = ref_shape
    h, w = base.shape[:2]
    if rh <= 0 or rw <= 0:
        return out
    sx = w / float(rw)
    sy = h / float(rh)
    if not overlay_detections and not overlay_validation:
        return out

    if abs(sx - 1.0) < 1e-3 and abs(sy - 1.0) < 1e-3:
        for d in overlay_detections:
            _draw_detection(out, d)
        for r in overlay_validation:
            _draw_person_result(out, r, overlay_labels.get(r.track_id, "No Helmet"))
        return out

    for d in overlay_detections:
        _draw_detection(out, _scale_detection(d, sx, sy))
    for r in overlay_validation:
        px1, py1, px2, py2 = r.person_box
        rx1, ry1, rx2, ry2 = r.head_roi
        scaled = PersonValidationResult(
            track_id=r.track_id,
            confidence=r.confidence,
            person_box=(int(px1 * sx), int(py1 * sy), int(px2 * sx), int(py2 * sy)),
            head_roi=(int(rx1 * sx), int(ry1 * sy), int(rx2 * sx), int(ry2 * sy)),
            best_helmet_overlap=r.best_helmet_overlap,
            potential_violation=r.potential_violation,
            confirmed_violation=r.confirmed_violation,
            violation_ratio=r.violation_ratio,
            material_score=r.material_score,
            material_override=r.material_override,
        )
        _draw_person_result(out, scaled, overlay_labels.get(r.track_id, "No Helmet"))
    return out


def generate_frames():
    global current_frame
    last_processed_frame = None
    last_frame_bytes = None
    
    while True:
        # Prevent 100% CPU lock by enforcing max 30 FPS loop rate
        time.sleep(0.033) 
        
        if current_frame is not None:
            # Only encode (heavy operation) if the frame actually changed
            if current_frame is not last_processed_frame:
                last_processed_frame = current_frame
                # Compress quality to 60 for low latency local stream
                ret, buffer = cv2.imencode('.jpg', current_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 60])
                if ret:
                    last_frame_bytes = buffer.tobytes()
            
            # Continuously push bytes to keep MJPEG socket alive
            if last_frame_bytes is not None:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + last_frame_bytes + b'\r\n')

@app.route('/stream')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/latest_frame')
def get_latest_frame():
    global current_frame
    if current_frame is not None:
        ret, buffer = cv2.imencode('.jpg', current_frame)
        if ret:
            return Response(buffer.tobytes(), mimetype='image/jpeg')
    return Response("No frame", status=404)

def run_pipeline(source_url: str, backend_api_url: str, site_id: str, camera_id: str):
    global current_frame
    system = HelmetSystem(
        helmet_model_path="helmet_v2_final.pt",
        person_model_path="yolov8n.pt",
        inference_image_size=640,
        helmet_confidence_threshold=HELMET_CONFIDENCE_THRESHOLD,
        person_confidence_threshold=PERSON_TRACK_CONFIDENCE,
        person_iou_threshold=PERSON_TRACK_IOU,
        head_roi_ratio=HEAD_SPATIAL_TOP_RATIO,
        validation_window_size=VALIDATION_WINDOW_SIZE,
        validation_required_hits=VALIDATION_REQUIRED_HITS,
        device="cpu",
    )
    preprocessor = Preprocessor(
        blur_threshold=PREPROCESSOR_BLUR_THRESHOLD,
        ssim_threshold=PREPROCESSOR_SSIM_THRESHOLD,
        ssim_check_interval=PREPROCESSOR_SSIM_INTERVAL,
    )
    
    print(f"[*] Starting helmet stream pipeline on source: {source_url}")
    print(f"[*] MJPEG streaming on /stream")
    print(f"[*] Outbound backend API: {backend_api_url}")
    os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "fflags;nobuffer|flags;low_delay"
    normalized_source = int(source_url) if source_url.isdigit() else source_url
    capture = cv2.VideoCapture(normalized_source)
    if isinstance(normalized_source, int):
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    if not capture.isOpened():
        raise ValueError(f"Unable to open source: {source_url}")

    is_running = True
    state_lock = threading.Lock()
    shared_raw: list[np.ndarray | None] = [None]
    previous_frame: list[np.ndarray | None] = [None]
    overlay_lock = threading.Lock()
    overlay_state: dict = {
        "detections": [],
        "validation": [],
        "labels": {},
        "ref_shape": None,
    }
    last_alert_at: dict[int, float] = {}
    cooldown_seconds = 5.0

    def _scale_box(
        box: tuple[float, float, float, float],
        sx: float,
        sy: float,
    ) -> tuple[float, float, float, float]:
        x1, y1, x2, y2 = box
        return x1 * sx, y1 * sy, x2 * sx, y2 * sy

    def _scale_detection(det: Detection, sx: float, sy: float) -> Detection:
        x1, y1, x2, y2 = _scale_box(det.bounding_box, sx, sy)
        return Detection(
            class_name=det.class_name,
            bounding_box=(x1, y1, x2, y2),
            confidence=det.confidence,
            track_id=det.track_id,
        )

    def _scale_tracked_person(person: TrackedPerson, sx: float, sy: float) -> TrackedPerson:
        x1, y1, x2, y2 = _scale_box(person.bounding_box, sx, sy)
        return TrackedPerson(
            track_id=person.track_id,
            bounding_box=(int(x1), int(y1), int(x2), int(y2)),
            confidence=person.confidence,
        )

    def camera_worker() -> None:
        global current_frame
        while is_running:
            ok, frame = capture.read()
            if not ok:
                time.sleep(0.02)
                continue
            with state_lock:
                shared_raw[0] = frame.copy()
            with overlay_lock:
                dets = list(overlay_state["detections"])
                vals = list(overlay_state["validation"])
                labels = dict(overlay_state["labels"])
                ref_shape = overlay_state["ref_shape"]
            current_frame = _compose_overlay_on_frame(frame, dets, vals, labels, ref_shape)
            time.sleep(0.01)

    def ai_worker() -> None:
        nonlocal is_running
        while is_running:
            with state_lock:
                raw = shared_raw[0].copy() if shared_raw[0] is not None else None
                prev = previous_frame[0]

            if raw is None:
                time.sleep(0.01)
                continue

            preprocess_result = preprocessor.process(raw, prev)
            with state_lock:
                previous_frame[0] = raw

            confirmed_violations: list[PersonValidationResult] = []
            filtered_detections: list[Detection] = []
            validation_results: list[PersonValidationResult] = []
            status_labels: dict[int, str] = {}

            if preprocess_result.should_process:
                work_h, work_w = preprocess_result.cleaned_frame.shape[:2]
                disp_h, disp_w = raw.shape[:2]
                sx = disp_w / float(work_w) if work_w else 1.0
                sy = disp_h / float(work_h) if work_h else 1.0

                frame_result = system.process_frame(preprocess_result.cleaned_frame)
                thresholded_detections = filter_detections_by_class_threshold(
                    frame_result.helmet_detections,
                    per_class_thresholds=CLASS_THRESHOLDS,
                )
                scaled_detections = [_scale_detection(d, sx, sy) for d in thresholded_detections]
                scaled_persons = [_scale_tracked_person(p, sx, sy) for p in frame_result.tracked_persons]

                filtered_detections = filter_detections_by_spatial_constraint(
                    scaled_detections,
                    scaled_persons,
                    head_top_ratio=HEAD_SPATIAL_TOP_RATIO,
                )
                validation_results, status_labels = build_person_validation_results(
                    scaled_persons,
                    filtered_detections,
                    head_top_ratio=HEAD_SPATIAL_TOP_RATIO,
                )

                confirmed_violations = [
                    result for result in validation_results if result.confirmed_violation
                ]

            if preprocess_result.should_process:
                ref_shape = (int(raw.shape[0]), int(raw.shape[1]))
                with overlay_lock:
                    overlay_state["detections"] = list(filtered_detections)
                    overlay_state["validation"] = list(validation_results)
                    overlay_state["labels"] = dict(status_labels)
                    overlay_state["ref_shape"] = ref_shape

            if confirmed_violations:
                evidence = raw.copy()
                for detection in filtered_detections:
                    _draw_detection(evidence, detection)
                for result in validation_results:
                    _draw_person_result(
                        evidence,
                        result,
                        status_labels.get(result.track_id, "No Helmet"),
                    )
                ret, buffer = cv2.imencode('.jpg', evidence)
                b64_img = base64.b64encode(buffer).decode('utf-8') if ret else ""
                now = time.time()

                for result in confirmed_violations:
                    last_ts = last_alert_at.get(result.track_id, 0.0)
                    if now - last_ts < cooldown_seconds:
                        continue
                    last_alert_at[result.track_id] = now
                    payload = {
                         "siteId": site_id,
                         "cameraId": camera_id,
                         "criterionId": "00000000-0000-0000-0000-000000000000",
                         "trackId": f"person_{result.track_id}",
                         "severity": 3,
                         "status": "open",
                         "startedAt": datetime.now(timezone.utc).isoformat(),
                         "confirmedAt": datetime.now(timezone.utc).isoformat(),
                         "voteTotalFrames": 30,
                         "voteViolationFrames": int(result.violation_ratio * 30),
                         "evidences": [
                             {
                                 "captureTs": datetime.now(timezone.utc).isoformat(),
                                 "imagePath": "data:image/jpeg;base64," + b64_img
                             }
                         ]
                   }

                    def _post(p: dict) -> None:
                        try:
                            res = requests.post(f"{backend_api_url}/api/Violations", json=p, timeout=2)
                            tid = p.get("trackId", "?")
                            print(f"[!] Sent Alert {tid} | Status: {res.status_code}")
                        except Exception as e:
                            print(f"[-] API Error: {e}")

                    threading.Thread(target=_post, args=(payload,), daemon=True).start()

    try:
        threading.Thread(target=camera_worker, daemon=True).start()
        threading.Thread(target=ai_worker, daemon=True).start()
        while True:
            time.sleep(1.0)
    finally:
        is_running = False
        capture.release()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', default='0', help='RTSP URL or Camera port (e.g. 0)')
    parser.add_argument('--port', type=int, default=5000, help='MJPEG web stream port')
    parser.add_argument('--backend', default='https://localhost:5001', help='Backend API URL')
    parser.add_argument('--site', default='00000000-0000-0000-0000-000000000000', help='Site ID UUID')
    parser.add_argument('--camera', default='00000000-0000-0000-0000-000000000000', help='Camera ID UUID')
    args = parser.parse_args()
    
    t = threading.Thread(target=run_pipeline, args=(args.source, args.backend, args.site, args.camera))
    t.daemon = True
    t.start()
    
    app.run(host='0.0.0.0', port=args.port, threaded=True, debug=False)
