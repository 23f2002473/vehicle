"""
svams/backend/routes/stream.py
Live camera stream endpoints

GET  /api/stream/video      — MJPEG live feed (embed in <img> tag)
POST /api/stream/start      — Start webcam capture loop
POST /api/stream/stop       — Stop webcam capture loop
GET  /api/stream/status     — Is capture running?
POST /api/stream/frame      — Manual single-frame submission (edge device push)
"""

import cv2
import numpy as np
import base64
import os
import time
from pathlib import Path
from datetime import datetime
from flask import Blueprint, Response, request, jsonify
from flask_jwt_extended import jwt_required

stream_bp = Blueprint("stream", __name__, url_prefix="/api/stream")

SNAPSHOT_DIR = Path(os.getenv("SNAPSHOT_DIR", "snapshots"))


def _lazy_import():
    """Lazy import so Flask starts even if vision deps missing."""
    from backend.vision.webcam_capture import (
        start_capture, stop_capture, is_running, frame_generator
    )
    return start_capture, stop_capture, is_running, frame_generator


# ── GET /api/stream/video ─────────────────────────────────────
@stream_bp.route("/video", methods=["GET"])
def video_feed():
    """
    MJPEG stream — embed as:
        <img src="http://localhost:5000/api/stream/video">
    Or in Streamlit:
        st.image("http://localhost:5000/api/stream/video")
    """
    try:
        _, _, _, frame_generator = _lazy_import()
        return Response(
            frame_generator(),
            mimetype="multipart/x-mixed-replace; boundary=frame",
        )
    except Exception as e:
        return jsonify({"error": f"Stream unavailable: {e}"}), 503


# ── POST /api/stream/start ────────────────────────────────────
@stream_bp.route("/start", methods=["POST"])
@jwt_required()
def start_stream():
    data      = request.get_json(silent=True) or {}
    direction = data.get("direction", "ENTRY").upper()
    if direction not in ("ENTRY", "EXIT"):
        return jsonify({"error": "direction must be ENTRY or EXIT"}), 400

    try:
        start_capture, _, is_running, _ = _lazy_import()
        if is_running():
            return jsonify({"message": "Capture already running.", "running": True}), 200
        start_capture(direction=direction)
        return jsonify({"message": f"Capture started ({direction}).", "running": True}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── POST /api/stream/stop ─────────────────────────────────────
@stream_bp.route("/stop", methods=["POST"])
@jwt_required()
def stop_stream():
    try:
        _, stop_capture, _, _ = _lazy_import()
        stop_capture()
        return jsonify({"message": "Capture stopped.", "running": False}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── GET /api/stream/status ────────────────────────────────────
@stream_bp.route("/status", methods=["GET"])
@jwt_required()
def stream_status():
    try:
        _, _, is_running, _ = _lazy_import()
        return jsonify({"running": is_running()}), 200
    except Exception as e:
        return jsonify({"running": False, "error": str(e)}), 200


# ── POST /api/stream/frame ────────────────────────────────────
@stream_bp.route("/frame", methods=["POST"])
def process_single_frame():
    """
    Accept a single base64-encoded JPEG frame from any edge device,
    run YOLO+OCR on it, and return detections WITHOUT calling /api/verify.
    (Caller is responsible for calling /api/verify with the result.)

    Body:
    {
        "image_b64": "<base64 jpeg>",
        "direction": "ENTRY"
    }
    """
    data      = request.get_json(silent=True) or {}
    image_b64 = data.get("image_b64")
    direction = data.get("direction", "ENTRY").upper()

    if not image_b64:
        return jsonify({"error": "image_b64 is required."}), 400

    # Decode base64 → numpy array
    try:
        img_bytes = base64.b64decode(image_b64)
        np_arr    = np.frombuffer(img_bytes, np.uint8)
        frame     = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        if frame is None:
            raise ValueError("Failed to decode image")
    except Exception as e:
        return jsonify({"error": f"Invalid image: {e}"}), 400

    # Run detector
    try:
        from backend.vision.plate_detector import PlateDetector
        detector   = PlateDetector()
        detections = detector.process_frame(frame)
    except Exception as e:
        return jsonify({"error": f"Detection failed: {e}"}), 500

    results = []
    for det in detections:
        # Save snapshot
        SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
        ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{direction}_{det['plate']}_{ts}.jpg"
        filepath = SNAPSHOT_DIR / filename
        cv2.imwrite(str(filepath), det["crop"])

        results.append({
            "plate":      det["plate"],
            "confidence": det["confidence"],
            "bbox":       det["bbox"],
            "image_path": str(filepath),
        })

    return jsonify({"detections": results, "count": len(results)}), 200
