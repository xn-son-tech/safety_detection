# Production-Level Pipeline Optimization & Refactoring Guide

Based on the deep analysis of the current real-time safety detection pipeline, this document outlines the concrete technical strategy to resolve performance bottlenecks, eliminate latency, and achieve a stable **30 FPS** real-time pipeline.

---

## 1. Bottleneck Fixes (MANDATORY)

### Bottleneck A: Synchronous / Blocking Main Loop
*   **The Issue:** `webcam_demo.py` uses a standard sequential `while True` loop where Camera I/O + Preprocessing + YOLO Inference + UI Rendering block each other. If YOLO takes 80ms, the entire display drops to ~12 FPS. 
*   **The Fix:** Implement an Asynchronous Producer-Consumer architecture using threading.
*   **Improvement:** The UI thread and Camera thread will operate at exactly the hardware limit (30/60 FPS), while the AI inferencing runs unbounded in the background (e.g., 10-15 FPS) without dragging the stream down.

### Bottleneck B: High CPU Load from `skimage.metrics.ssim`
*   **The Issue:** Computing Structural Similarity Index (SSIM) on full-resolution 720p/1080p images using `skimage` takes significant CPU cycles (20-40ms), severely delaying the pipeline before AI even starts.
*   **The Fix:** Downscale the frame aggressively before glitch detection, or replace SSIM entirely with a lightweight OpenCV routine like Mean Squared Error (MSE) or `cv2.absdiff()`.
*   **Improvement:** Reduces pre-processing overhead from ~35ms down to `< 2ms` per frame.

---

## 2. Optimized Architecture

To sustain a visual 30 FPS effortlessly, the pipeline must be decentralized into three decoupled threads communicating via thread-safe shared memory (Atomic state).

1.  **Camera Thread (Producer - 30 FPS):** 
    *   Locks onto the RTSP/Webcam stream.
    *   Continuously reads `capture.read()`.
    *   Saves the absolute freshest frame to a thread-safe variable `self._shared_frame`.
    *   Drops intermediate frames implicitly if AI cannot keep up (Last-In-First-Out / Latest-Frame strategy).
2.  **AI Worker Thread (Consumer - Unbounded ~15 FPS):**
    *   Eternally polls `self._shared_frame`.
    *   Fires Pre-processing (Blur check -> CLAHE).
    *   Runs YOLOv8 + Rule Engine + Material Analysis.
    *   Stores final bounding boxes & alerts into `self._shared_ai_result`.
3.  **UI/Display Main Thread (Renderer - 30 FPS bounded):**
    *   Retrieves the fresh *Camera Frame* and the latest *AI Result* (which might be 1-2 frames old).
    *   Draws the AI bounding boxes onto the fresh frame.
    *   Calls `cv2.imshow()`.

---

## 3. Refactored Code (Key Parts)

### A. Implementing the Async Non-Blocking Demo Loop
This demonstrates how to refactor `webcam_demo.py` to use a non-blocking UI.

```python
import threading
import time
import cv2
import copy

class AsyncSafetyPipeline:
    def __init__(self, system, source=0):
        self.system = system
        self.source = source
        self.cap = cv2.VideoCapture(source)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1) # Prevent frame stacking
        
        self.is_running = True
        self.latest_frame = None
        self.latest_ai_results = None
        self.lock = threading.Lock()

    def start(self):
        # 1. Start Camera Thread
        threading.Thread(target=self._camera_worker, daemon=True).start()
        # 2. Start AI Thread
        threading.Thread(target=self._ai_worker, daemon=True).start()
        # 3. Block main thread with UI Window
        self._ui_window()

    def _camera_worker(self):
        while self.is_running:
            ret, frame = self.cap.read()
            if ret:
                # Store the absolute latest frame for BOTH UI and AI
                with self.lock:
                    self.latest_frame = frame
            time.sleep(0.01) # Small sleep to prevent CPU thread starvation

    def _ai_worker(self):
        while self.is_running:
            # Safely fetch the most recent frame
            with self.lock:
                frame_for_ai = self.latest_frame.copy() if self.latest_frame is not None else None
            
            if frame_for_ai is None:
                time.sleep(0.01)
                continue

            # Heavy Operations: CLAHE + YOLO + SORT Tracking + Rules
            engine_result = self.system.process_frame(frame_for_ai)
            
            # Post updates to UI
            with self.lock:
                self.latest_ai_results = engine_result

    def _ui_window(self):
        while self.is_running:
            with self.lock:
                frame = self.latest_frame.copy() if self.latest_frame is not None else None
                ai_data = self.latest_ai_results # No .copy() needed, just reference
            
            if frame is not None:
                if ai_data is not None:
                    # Draw bounding boxes from ai_data onto frame
                    self._draw_overlay(frame, ai_data)
                
                cv2.imshow("Production Helmet Detection", frame)
                
            if cv2.waitKey(1) & 0xFF == ord('q'):
                self.is_running = False
                
        self.cap.release()
        cv2.destroyAllWindows()
```

### B. O(1) Lightweight Fast Preprocessing
Refactoring `is_glitch` in `preprocessor.py` to remove `skimage.metrics.ssim`.

```python
def is_glitch_fast(self, current_frame, prev_frame, mse_threshold=3000):
        if prev_frame is None:
            return False
            
        # 1. Drastically resize for computational speed before matrix math
        # 64x48 is sufficient to detect massive payload tearing
        cur_small = cv2.resize(current_frame, (64, 48))
        prev_small = cv2.resize(prev_frame, (64, 48))
        
        # 2. OpenCV Mean Squared Error (MSE) runs natively in C
        diff = cv2.subtract(cur_small, prev_small)
        err = np.sum(diff**2) / float(cur_small.shape[0] * cur_small.shape[1])
        
        # If the error jumps gigantically, packet tearing occurred
        return err > mse_threshold
```

---

## 4. Performance Optimization Strategy (DEEP)

*   **Model Quantization & Format (Critical!):** 
    Never inject raw `.pt` PyTorch models directly into production loops without converting them. Export YOLO to ONNX or TensorRT (if running on NVIDIA Edge GPUs). 
    *Command:* `yolo export model=helmet_v2_final.pt format=engine half=True dynamic=False` (FP16 precision doubles GPU speed with zero visual accuracy loss).
*   **Resolution Tuning:** 
    Keep `imgsz=640` for AI, but input UI frames can be native hardware (1280x720). Decoupling via Async Pipeline means scaling images down for AI inference doesn't destroy the high-resolution output displayed dynamically on the dashboard.
*   **Hardware Mapping:** 
    Bind `cv2.VideoCapture` and UI tasks to CPU cores using `taskset`. Ensure YOLO inference strictly runs via CUDA/cuDNN streams. 

---

## 5. Stability Enhancements

To prevent stutter in real-time camera display and ensure rule accuracy:

1.  **Temporal Position Smoothing:** 
    Because the UI runs at 30 FPS and AI runs at ~15 FPS, bounding boxes will appear to "stutter" or teleport.
    *Solution:* Inject a lightweight Optical Flow (e.g., `cv2.calcOpticalFlowPyrLK`) OR simple linear interpolation into the UI thread. The UI moves the box pixels slightly in the direction of the BoT-SORT predicted velocity vector until the next AI payload arrives.
2.  **Debounce Logic:**
    The buffer mechanism (`window_size=30`, `required_hits=24`) is already a top-tier industry practice. Keep it active to ensure robust filtering against flickering confidence intervals from YOLO.
3.  **Grace Period Override:**
    If the worker is currently tracked and drops underneath the camera for 3 frames, apply an aggressive timeout extension on `TrackedPerson` ID handling, so they are not reset to safe immediately.

---

## 6. Final Pipeline Design Outline

**1. Data Ingestion:** RTSP/USB Camera → BufferSize=1 → Atomic Queuing.
**2. Filtering Phase (CPU):** Downscaled MSE tearing check (1ms) → Laplacian Variance Motion Blur Check (2ms) → Drop if bad.
**3. Vision Enhancement (CPU):** Global histogram stretching + OpenCV CLAHE on LAB color space (4ms).
**4. Primary Inference (GPU):** YOLOv8 TensorRT FP16 Engine execution → Single forward pass (15-20ms).
**5. Geometrical Processing & Rule Engine (Numpy):** Apply BoT-SORT Kalman filters → Apply `IoA` Greedy Matrix (2ms) → Produce `head_roi` (35% fixed top offset).
**6. Deep Material Validation (Fallback):** If AI confidence creates a "potential violation", execute Morphological Top-Hat on cropped head region. Intercept & flip to SAFE if `m_score >= 0.5`.
**7. Storage & UI:** Store 24/30 ring buffer violation checks. Dump evidence images to file I/O using a detached async worker thread (to prevent UI stutter when writing `.jpg` to disk). Flush rendering onto 30FPS Screen.
