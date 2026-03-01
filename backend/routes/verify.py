"""
svams/backend/routes/verify.py
Core gate logic: /api/verify and /api/exit
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from backend.utils.db import execute_query
from datetime import datetime

verify_bp = Blueprint("verify", __name__, url_prefix="/api")


# ── POST /api/verify ─────────────────────────────────────────
@verify_bp.route("/verify", methods=["POST"])
def verify():
    """
    Called by the edge unit on vehicle detection.
    Checks if plate is authorized and logs entry.
    """
    data            = request.get_json(silent=True) or {}
    plate_number    = (data.get("plate_number") or "").strip().upper()
    ocr_confidence  = data.get("ocr_confidence")
    entry_image     = data.get("entry_image_path")
    direction       = data.get("direction", "ENTRY").upper()

    if not plate_number:
        return jsonify({"error": "plate_number is required."}), 400

    # Low OCR confidence — reject immediately
    if ocr_confidence is not None and float(ocr_confidence) < 60.0:
        _log_unauthorized(plate_number, direction, "LOW_OCR_CONFIDENCE", ocr_confidence, entry_image)
        return jsonify({"access": "DENIED", "reason": "LOW_OCR_CONFIDENCE"}), 200

    # Lookup vehicle
    vehicle = execute_query(
        """
        SELECT av.*, u.full_name, u.department, u.phone
        FROM authorized_vehicles av
        JOIN users u ON u.id_temp = av.user_id
        WHERE av.plate_number = %s
        """,
        (plate_number,),
        fetch="one",
    )

    if not vehicle:
        _log_unauthorized(plate_number, direction, "NOT_REGISTERED", ocr_confidence, entry_image)
        return jsonify({"access": "DENIED", "reason": "NOT_REGISTERED"}), 200

    if not vehicle["is_active"]:
        _log_unauthorized(plate_number, direction, "DEACTIVATED", ocr_confidence, entry_image)
        return jsonify({"access": "DENIED", "reason": "DEACTIVATED"}), 200

    # Log entry
    result = execute_query(
        """
        INSERT INTO entry_logs
            (plate_number, vehicle_id, user_id, entry_time, entry_image_path, ocr_confidence)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (
            plate_number,
            vehicle["vehicle_id"],
            vehicle["user_id"],
            datetime.now(),
            entry_image,
            ocr_confidence,
        ),
        fetch="none",
    )

    return jsonify({
        "access": "GRANTED",
        "log_id": result["lastrowid"],
        "vehicle": {
            "plate_number":  vehicle["plate_number"],
            "vehicle_type":  vehicle["vehicle_type"],
            "vehicle_make":  vehicle["vehicle_make"],
            "vehicle_model": vehicle["vehicle_model"],
            "vehicle_color": vehicle["vehicle_color"],
        },
        "owner": {
            "name":       vehicle["full_name"],
            "department": vehicle["department"],
            "phone":      vehicle["phone"],
        },
    }), 200


# ── POST /api/exit ───────────────────────────────────────────
@verify_bp.route("/exit", methods=["POST"])
def exit_vehicle():
    """
    Called when vehicle exits. Updates exit_time on the open entry log.
    """
    data           = request.get_json(silent=True) or {}
    plate_number   = (data.get("plate_number") or "").strip().upper()
    exit_image     = data.get("exit_image_path")
    ocr_confidence = data.get("ocr_confidence")

    if not plate_number:
        return jsonify({"error": "plate_number is required."}), 400

    # Find the most recent open log for this plate
    open_log = execute_query(
        """
        SELECT log_id FROM entry_logs
        WHERE plate_number = %s AND exit_time IS NULL
        ORDER BY entry_time DESC LIMIT 1
        """,
        (plate_number,),
        fetch="one",
    )

    if not open_log:
        _log_unauthorized(plate_number, "EXIT", "NOT_REGISTERED", ocr_confidence, exit_image)
        return jsonify({"access": "DENIED", "reason": "NO_OPEN_ENTRY_FOUND"}), 200

    execute_query(
        """
        UPDATE entry_logs
        SET exit_time = %s, exit_image_path = %s
        WHERE log_id = %s
        """,
        (datetime.now(), exit_image, open_log["log_id"]),
        fetch="none",
    )

    return jsonify({"success": True, "log_id": open_log["log_id"], "message": "Exit recorded."}), 200


# ── Helper ───────────────────────────────────────────────────
def _log_unauthorized(plate, direction, reason, confidence, image):
    execute_query(
        """
        INSERT INTO unauthorized_attempts
            (plate_number, attempt_time, direction, reason, image_path, ocr_confidence)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (plate, datetime.now(), direction, reason, image, confidence),
        fetch="none",
    )
