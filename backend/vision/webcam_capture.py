"""
svams/backend/vision/webcam_capture.py

Webcam capture loop:
  - Reads frames from cv2.VideoCapture(0)
  - Runs PlateDetector on every Nth frame
  - On detection → calls /api/verify or /api/exit
  - Saves snapshot images to disk
  - Annotated frames are pushed into a global queue
    so Flask can serve them as MJPEG stream

Run standalone:
    cd svams
    python -m backend.vision.webcam_capture

Or started automatically by Flask on first stream request.
"""

import cv2
import time
import queue
import threading
import requests
import os
import base64
from datetime import datetime
from pathlib import Path

from backend.vision.plate_detector import PlateDetector

# ── Config ───────────────────────────────────────────────────
API_BASE        = os.getenv("API_BASE_URL", "http://localhost:5000/api")
SNAPSHOT_DIR    = Path(os.getenv("SNAPSHOT_DIR", "snapshots"))
PROCESS_EVERY_N = int(os.getenv("PROCESS_EVERY_N_FRAMES", 10))  # run YOLO every N frames
DIRECTION       = os.getenv("GATE_DIRECTION", "ENTRY")           # ENTRY | EXIT
CAMERA_INDEX    = int(os.getenv("CAMERA_INDEX", 0))
DEDUPE_SECONDS  = int(os.getenv("DEDUPE_SECONDS", 30))          # ignore same plate within N sec

# Thread-safe frame queue for MJPEG streaming
frame_queue: queue.Queue = queue.Queue(maxsize=2)

# Global state
_capture_thread: threading.Thread | None = None
_stop_event     = threading.Event()
_recent_plates: dict[str, float] = {}   # plate → last_seen timestamp
_lock           = threading.Lock()


# ═══════════════════════════════════════════════════════════════
# SNAPSHOT HELPER
# ═══════════════════════════════════════════════════════════════
def _save_snapshot(frame, plate: str, direction: str) -> str:
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    name = f"{direction}_{plate}_{ts}.jpg"
    path = SNAPSHOT_DIR / name
    cv2.imwrite(str(path), frame)
    return str(path)


# ═══════════════════════════════════════════════════════════════
# API CALLER
# ═══════════════════════════════════════════════════════════════
def _call_api(plate: str, confidence: float, image_path: str, direction: str):
    endpoint = "/verify" if direction == "ENTRY" else "/exit"
    payload  = {
        "plate_number":     plate,
        "ocr_confidence":   confidence,
        "direction":        direction,
        f"{'entry' if direction == 'ENTRY' else 'exit'}_image_path": image_path,
    }
    try:
        r = requests.post(f"{API_BASE}{endpoint}", json=payload, timeout=5)
        result = r.json()
        print(f"[API] {plate} → {result.get('access', result.get('success', '?'))} "
              f"| reason: {result.get('reason', '—')}")
        return result
    except Exception as e:
        print(f"[API] Error calling {endpoint}: {e}")
        return None


# ═══════════════════════════════════════════════════════════════
# DEDUP CHECK
# ═══════════════════════════════════════════════════════════════
def _is_duplicate(plate: str) -> bool:
    now = time.time()
    with _lock:
        last = _recent_plates.get(plate, 0)
        if now - last < DEDUPE_SECONDS:
            return True
        _recent_plates[plate] = now
        return False


# ═══════════════════════════════════════════════════════════════
# MAIN CAPTURE LOOP
# ═══════════════════════════════════════════════════════════════
def capture_loop(direction: str = DIRECTION):
    global _recent_plates

    print(f"[VISION] Starting webcam capture (camera={CAMERA_INDEX}, direction={direction})")
    detector = PlateDetector()

    cap = cv2.VideoCapture(CAMERA_INDEX)
    if not cap.isOpened():
        print(f"[VISION] ERROR: Cannot open camera index {CAMERA_INDEX}")
        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    cap.set(cv2.CAP_PROP_FPS,          30)

    frame_idx = 0
    print("[VISION] Capture loop running. Press Ctrl+C to stop.")

    while not _stop_event.is_set():
        ret, frame = cap.read()
        if not ret:
            print("[VISION] Frame read failed — retrying...")
            time.sleep(0.1)
            continue

        frame_idx += 1

        # ── Run detection every N frames ─────────────────────
        if frame_idx % PROCESS_EVERY_N == 0:
            detections = detector.process_frame(frame)

            for det in detections:
                plate = det["plate"]
                conf  = det["confidence"]

                if _is_duplicate(plate):
                    print(f"[VISION] Duplicate suppressed: {plate}")
                    continue

                print(f"[VISION] Detected: {plate} ({conf:.1f}%)")

                # Save snapshot
                img_path = _save_snapshot(frame, plate, direction)

                # Call Flask API
                _call_api(plate, conf, img_path, direction)

            # Annotate and push to stream queue
            annotated = detector.annotate_frame(frame, detections)
        else:
            annotated = frame

        # Push frame to queue (drop old frames if full)
        if frame_queue.full():
            try:
                frame_queue.get_nowait()
            except queue.Empty:
                pass
        frame_queue.put(annotated)

    cap.release()
    print("[VISION] Capture loop stopped.")


# ═══════════════════════════════════════════════════════════════
# THREAD MANAGEMENT
# ═══════════════════════════════════════════════════════════════
def start_capture(direction: str = DIRECTION):
    global _capture_thread, _stop_event
    if _capture_thread and _capture_thread.is_alive():
        print("[VISION] Capture already running.")
        return

    _stop_event.clear()
    _capture_thread = threading.Thread(
        target=capture_loop,
        args=(direction,),
        daemon=True,
        name="svams-capture",
    )
    _capture_thread.start()


def stop_capture():
    global _stop_event
    _stop_event.set()
    print("[VISION] Stop signal sent.")


def is_running() -> bool:
    return _capture_thread is not None and _capture_thread.is_alive()


# ═══════════════════════════════════════════════════════════════
# FRAME GENERATOR (for MJPEG stream)
# ═══════════════════════════════════════════════════════════════
def frame_generator():
    """
    Yields MJPEG-encoded frames from the queue.
    Used by Flask /api/stream endpoint.
    """
    while True:
        try:
            frame = frame_queue.get(timeout=1.0)
        except queue.Empty:
            # yield a blank frame so the stream doesn't hang
            blank = 255 * __import__("numpy").ones((480, 640, 3), dtype="uint8")
            _, buf = cv2.imencode(".jpg", blank)
            yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"
                   + buf.tobytes() + b"\r\n")
            continue

        _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"
               + buf.tobytes() + b"\r\n")


# ═══════════════════════════════════════════════════════════════
# STANDALONE RUN
# ═══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import signal

    def _shutdown(sig, frame):
        stop_capture()
        raise SystemExit(0)

    signal.signal(signal.SIGINT,  _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    capture_loop(direction="ENTRY")
