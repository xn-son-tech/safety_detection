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

app = Flask(__name__)

# Global state for MJPEG stream
current_frame = None

def generate_frames():
    global current_frame
    while True:
        if current_frame is not None:
            ret, buffer = cv2.imencode('.jpg', current_frame)
            if ret:
                frame_bytes = buffer.tobytes()
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        else:
            time.sleep(0.05)

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
    # Use HelmetSystem or configure tracker. Let's setup the default tracker.
    tracker = YoloWorkerTracker(model_path="helmet_v2_final.pt") # Assumes models are in CWD
    pipeline = WorkerSafetyPipeline(tracker=tracker)
    
    print(f"[*] Starting Pipeline on source: {source_url}")
    print(f"[*] MJPEG streaming on /stream")
    print(f"[*] Outbound backend API: {backend_api_url}")
    
    for frame_data in pipeline.run(source_url):
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
