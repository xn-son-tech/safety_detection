import cv2
import threading
import requests
import base64
import time
import argparse
from datetime import datetime, timezone
from flask import Flask, Response

from ai_helmet_detection.pipeline import WorkerSafetyPipeline, HelmetSystem
from ai_helmet_detection.tracking import YoloWorkerTracker
from ai_helmet_detection.alert_validation import ViolationValidator

app = Flask(__name__)

# Global state for MJPEG stream
current_frame = None

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
    # Assumes models are in CWD
    tracker = YoloWorkerTracker(model_path="helmet_v2_final.pt")
    
    # Custom Validator: Khớp nhịp vụ Async AI
    # Đưa window_size về 1 (Tức là chỉ cần 1 khung hình xuất hiện vi phạm là Bắt ngay lập tức)
    # Khắc phục triệt để tình trạng người chuyển động làm đứt chuỗi Track_ID.
    validator = ViolationValidator(window_size=1, alert_threshold=0.0, cooldown_seconds=2.0)
    
    pipeline = WorkerSafetyPipeline(tracker=tracker, validator=validator)
    
    print(f"[*] Starting ASYNC Pipeline on source: {source_url}")
    print(f"[*] MJPEG streaming on /stream (V2 - 30 FPS Smooth)")
    print(f"[*] Outbound backend API: {backend_api_url}")
    
    for frame_data in pipeline.async_run(source_url):
        current_frame = frame_data.display_frame
        
        # Oubound REST API Integration for sending alerts
        if frame_data.official_alerts:
            # Encode frame to Base64 Evidence
            ret, buffer = cv2.imencode('.jpg', current_frame)
            b64_img = base64.b64encode(buffer).decode('utf-8') if ret else ""
            
            for alert in frame_data.official_alerts:
                payload = {
                     "siteId": site_id,
                     "cameraId": camera_id,
                     "criterionId": "00000000-0000-0000-0000-000000000000",
                     "trackId": f"person_{alert.track_id}",
                     "severity": 3,
                     "status": "open",
                     "startedAt": datetime.now(timezone.utc).isoformat(),
                     "confirmedAt": datetime.now(timezone.utc).isoformat(),
                     "voteTotalFrames": 30,
                     "voteViolationFrames": int(alert.violation_ratio * 30),
                     "evidences": [
                         {
                             "captureTs": datetime.now(timezone.utc).isoformat(),
                             "imagePath": "data:image/jpeg;base64," + b64_img
                         }
                     ]
                }
                
                try:
                    res = requests.post(f"{backend_api_url}/api/Violations", json=payload, timeout=2)
                    print(f"[!] Sent Alert ID={alert.track_id} | Status: {res.status_code}")
                except Exception as e:
                    print(f"[-] API Error: {e}")

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
