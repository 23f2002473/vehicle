"""
svams/backend/routes/logs.py
Entry logs + unauthorized attempts endpoints
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from backend.utils.db import execute_query

logs_bp = Blueprint("logs", __name__, url_prefix="/api")


# ── GET /api/logs ────────────────────────────────────────────
@logs_bp.route("/logs", methods=["GET"])
@jwt_required()
def list_logs():
    page       = max(int(request.args.get("page", 1)), 1)
    per_page   = min(int(request.args.get("per_page", 30)), 100)
    offset     = (page - 1) * per_page
    search     = request.args.get("search", "").strip()
    date_from  = request.args.get("date_from")
    date_to    = request.args.get("date_to")
    still_in   = request.args.get("still_inside")   # '1' = no exit_time

    conditions = []
    params     = []

    if search:
        conditions.append("el.plate_number LIKE %s")
        params.append(f"%{search}%")
    if date_from:
        conditions.append("DATE(el.entry_time) >= %s")
        params.append(date_from)
    if date_to:
        conditions.append("DATE(el.entry_time) <= %s")
        params.append(date_to)
    if still_in == "1":
        conditions.append("el.exit_time IS NULL")

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    rows = execute_query(
        f"""
        SELECT el.log_id, el.plate_number, el.user_id,
               el.entry_time, el.exit_time, el.duration_minutes,
               el.ocr_confidence, el.remarks,
               el.entry_image_path, el.exit_image_path,
               u.full_name, u.department,
               av.vehicle_type, av.vehicle_make, av.vehicle_model, av.vehicle_color
        FROM entry_logs el
        LEFT JOIN users u ON u.id_temp = el.user_id
        LEFT JOIN authorized_vehicles av ON av.vehicle_id = el.vehicle_id
        {where}
        ORDER BY el.entry_time DESC
        LIMIT %s OFFSET %s
        """,
        tuple(params) + (per_page, offset),
        fetch="all",
    )

    count_row = execute_query(
        f"SELECT COUNT(*) AS total FROM entry_logs el {where}",
        tuple(params),
        fetch="one",
    )

    return jsonify({"data": rows, "total": count_row["total"], "page": page, "per_page": per_page}), 200


# ── GET /api/unauthorized ────────────────────────────────────
@logs_bp.route("/unauthorized", methods=["GET"])
@jwt_required()
def list_unauthorized():
    page     = max(int(request.args.get("page", 1)), 1)
    per_page = min(int(request.args.get("per_page", 30)), 100)
    offset   = (page - 1) * per_page
    reason   = request.args.get("reason", "").strip().upper()
    date_from = request.args.get("date_from")
    date_to   = request.args.get("date_to")

    conditions = []
    params     = []

    if reason:
        conditions.append("reason = %s")
        params.append(reason)
    if date_from:
        conditions.append("DATE(attempt_time) >= %s")
        params.append(date_from)
    if date_to:
        conditions.append("DATE(attempt_time) <= %s")
        params.append(date_to)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    rows = execute_query(
        f"""
        SELECT * FROM unauthorized_attempts
        {where}
        ORDER BY attempt_time DESC
        LIMIT %s OFFSET %s
        """,
        tuple(params) + (per_page, offset),
        fetch="all",
    )

    count_row = execute_query(
        f"SELECT COUNT(*) AS total FROM unauthorized_attempts {where}",
        tuple(params),
        fetch="one",
    )

    return jsonify({"data": rows, "total": count_row["total"], "page": page, "per_page": per_page}), 200


# ── PATCH /api/unauthorized/<id>/alert ──────────────────────
@logs_bp.route("/unauthorized/<int:attempt_id>/alert", methods=["PATCH"])
@jwt_required()
def mark_alert_sent(attempt_id):
    execute_query(
        "UPDATE unauthorized_attempts SET alert_sent = 1 WHERE attempt_id = %s",
        (attempt_id,),
        fetch="none",
    )
    return jsonify({"message": "Alert marked as sent."}), 200


# ── GET /api/dashboard/stats ─────────────────────────────────
@logs_bp.route("/dashboard/stats", methods=["GET"])
@jwt_required()
def dashboard_stats():
    total_vehicles = execute_query(
        "SELECT COUNT(*) AS cnt FROM authorized_vehicles WHERE is_active=1", fetch="one"
    )
    inside_now = execute_query(
        "SELECT COUNT(*) AS cnt FROM entry_logs WHERE exit_time IS NULL", fetch="one"
    )
    today_entries = execute_query(
        "SELECT COUNT(*) AS cnt FROM entry_logs WHERE DATE(entry_time) = CURDATE()", fetch="one"
    )
    today_denied = execute_query(
        "SELECT COUNT(*) AS cnt FROM unauthorized_attempts WHERE DATE(attempt_time) = CURDATE()", fetch="one"
    )
    unread_alerts = execute_query(
        "SELECT COUNT(*) AS cnt FROM unauthorized_attempts WHERE alert_sent = 0", fetch="one"
    )
    hourly_traffic = execute_query(
        """
        SELECT HOUR(entry_time) AS hour, COUNT(*) AS entries
        FROM entry_logs
        WHERE DATE(entry_time) = CURDATE()
        GROUP BY HOUR(entry_time)
        ORDER BY hour
        """,
        fetch="all",
    )
    recent_entries = execute_query(
        """
        SELECT el.plate_number, el.entry_time, el.exit_time,
               u.full_name, av.vehicle_type
        FROM entry_logs el
        LEFT JOIN users u  ON u.id_temp   = el.user_id
        LEFT JOIN authorized_vehicles av ON av.vehicle_id = el.vehicle_id
        ORDER BY el.entry_time DESC LIMIT 5
        """,
        fetch="all",
    )
    reason_breakdown = execute_query(
        """
        SELECT reason, COUNT(*) AS cnt
        FROM unauthorized_attempts
        WHERE DATE(attempt_time) = CURDATE()
        GROUP BY reason
        """,
        fetch="all",
    )

    return jsonify({
        "total_active_vehicles": total_vehicles["cnt"],
        "vehicles_inside_now":   inside_now["cnt"],
        "today_entries":         today_entries["cnt"],
        "today_denied":          today_denied["cnt"],
        "unread_alerts":         unread_alerts["cnt"],
        "hourly_traffic":        hourly_traffic,
        "recent_entries":        recent_entries,
        "reason_breakdown":      reason_breakdown,
    }), 200
