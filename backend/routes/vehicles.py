"""
svams/backend/routes/vehicles.py
Authorized vehicle CRUD endpoints
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from backend.utils.db import execute_query

vehicles_bp = Blueprint("vehicles", __name__, url_prefix="/api/vehicles")

VALID_TYPES = {"CAR", "MOTORCYCLE", "SUV", "TRUCK", "OTHER"}


# ── GET /api/vehicles ────────────────────────────────────────
@vehicles_bp.route("", methods=["GET"])
@jwt_required()
def list_vehicles():
    search     = request.args.get("search", "").strip()
    is_active  = request.args.get("is_active")      # '0' | '1' | None
    page       = max(int(request.args.get("page",  1)), 1)
    per_page   = min(int(request.args.get("per_page", 20)), 100)
    offset     = (page - 1) * per_page

    conditions = []
    params     = []

    if search:
        conditions.append("(av.plate_number LIKE %s OR u.full_name LIKE %s OR u.id_temp LIKE %s)")
        like = f"%{search}%"
        params += [like, like, like]

    if is_active in ("0", "1"):
        conditions.append("av.is_active = %s")
        params.append(int(is_active))

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    rows = execute_query(
        f"""
        SELECT av.*, u.full_name, u.department, u.phone,
               a.username AS registered_by_username
        FROM authorized_vehicles av
        JOIN users u        ON u.id_temp   = av.user_id
        LEFT JOIN admin_users a ON a.admin_id = av.registered_by
        {where}
        ORDER BY av.registered_at DESC
        LIMIT %s OFFSET %s
        """,
        tuple(params) + (per_page, offset),
        fetch="all",
    )

    count_row = execute_query(
        f"""
        SELECT COUNT(*) AS total
        FROM authorized_vehicles av
        JOIN users u ON u.id_temp = av.user_id
        {where}
        """,
        tuple(params),
        fetch="one",
    )

    return jsonify({
        "data":      rows,
        "total":     count_row["total"],
        "page":      page,
        "per_page":  per_page,
    }), 200


# ── GET /api/vehicles/<id> ───────────────────────────────────
@vehicles_bp.route("/<int:vehicle_id>", methods=["GET"])
@jwt_required()
def get_vehicle(vehicle_id):
    row = execute_query(
        """
        SELECT av.*, u.full_name, u.department, u.phone
        FROM authorized_vehicles av
        JOIN users u ON u.id_temp = av.user_id
        WHERE av.vehicle_id = %s
        """,
        (vehicle_id,),
        fetch="one",
    )
    if not row:
        return jsonify({"error": "Vehicle not found."}), 404
    return jsonify(row), 200


# ── POST /api/vehicles ───────────────────────────────────────
@vehicles_bp.route("", methods=["POST"])
@jwt_required()
def create_vehicle():
    admin_id = int(get_jwt_identity())
    data     = request.get_json(silent=True) or {}

    user_id       = str(data.get("user_id", "")).strip()
    plate_number  = str(data.get("plate_number", "")).strip().upper()
    vehicle_type  = str(data.get("vehicle_type", "")).strip().upper()
    vehicle_make  = data.get("vehicle_make")
    vehicle_model = data.get("vehicle_model")
    vehicle_color = data.get("vehicle_color")
    notes         = data.get("notes")

    # Validation
    if not user_id or not plate_number or not vehicle_type:
        return jsonify({"error": "user_id, plate_number, vehicle_type are required."}), 400
    if vehicle_type not in VALID_TYPES:
        return jsonify({"error": f"vehicle_type must be one of {VALID_TYPES}"}), 400

    # User exists?
    user = execute_query("SELECT id_temp FROM users WHERE id_temp = %s", (user_id,), fetch="one")
    if not user:
        return jsonify({"error": "User not found."}), 404

    # Plate duplicate?
    dup = execute_query(
        "SELECT vehicle_id FROM authorized_vehicles WHERE plate_number = %s", (plate_number,), fetch="one"
    )
    if dup:
        return jsonify({"error": "Plate number already registered."}), 409

    # Max 2 active vehicles per user
    count = execute_query(
        "SELECT COUNT(*) AS cnt FROM authorized_vehicles WHERE user_id = %s AND is_active = 1",
        (user_id,),
        fetch="one",
    )
    if count["cnt"] >= 2:
        return jsonify({"error": "User already has 2 active vehicles (maximum reached)."}), 422

    result = execute_query(
        """
        INSERT INTO authorized_vehicles
            (user_id, plate_number, vehicle_type, vehicle_make, vehicle_model, vehicle_color, registered_by, notes)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        """,
        (user_id, plate_number, vehicle_type, vehicle_make, vehicle_model, vehicle_color, admin_id, notes),
        fetch="none",
    )

    return jsonify({"message": "Vehicle registered.", "vehicle_id": result["lastrowid"]}), 201


# ── PUT /api/vehicles/<id> ───────────────────────────────────
@vehicles_bp.route("/<int:vehicle_id>", methods=["PUT"])
@jwt_required()
def update_vehicle(vehicle_id):
    data = request.get_json(silent=True) or {}

    existing = execute_query(
        "SELECT * FROM authorized_vehicles WHERE vehicle_id = %s", (vehicle_id,), fetch="one"
    )
    if not existing:
        return jsonify({"error": "Vehicle not found."}), 404

    vehicle_type  = str(data.get("vehicle_type",  existing["vehicle_type"])).upper()
    vehicle_make  = data.get("vehicle_make",  existing["vehicle_make"])
    vehicle_model = data.get("vehicle_model", existing["vehicle_model"])
    vehicle_color = data.get("vehicle_color", existing["vehicle_color"])
    notes         = data.get("notes",         existing["notes"])

    if vehicle_type not in VALID_TYPES:
        return jsonify({"error": f"vehicle_type must be one of {VALID_TYPES}"}), 400

    execute_query(
        """
        UPDATE authorized_vehicles
        SET vehicle_type=%s, vehicle_make=%s, vehicle_model=%s, vehicle_color=%s, notes=%s
        WHERE vehicle_id=%s
        """,
        (vehicle_type, vehicle_make, vehicle_model, vehicle_color, notes, vehicle_id),
        fetch="none",
    )
    return jsonify({"message": "Vehicle updated."}), 200


# ── PATCH /api/vehicles/<id>/toggle ─────────────────────────
@vehicles_bp.route("/<int:vehicle_id>/toggle", methods=["PATCH"])
@jwt_required()
def toggle_vehicle(vehicle_id):
    """Activate or deactivate a vehicle."""
    existing = execute_query(
        "SELECT is_active, user_id FROM authorized_vehicles WHERE vehicle_id = %s",
        (vehicle_id,),
        fetch="one",
    )
    if not existing:
        return jsonify({"error": "Vehicle not found."}), 404

    new_status = 0 if existing["is_active"] else 1

    # If re-activating, enforce max 2 rule
    if new_status == 1:
        count = execute_query(
            "SELECT COUNT(*) AS cnt FROM authorized_vehicles WHERE user_id=%s AND is_active=1",
            (existing["user_id"],),
            fetch="one",
        )
        if count["cnt"] >= 2:
            return jsonify({"error": "Cannot activate: user already has 2 active vehicles."}), 422

    execute_query(
        "UPDATE authorized_vehicles SET is_active=%s WHERE vehicle_id=%s",
        (new_status, vehicle_id),
        fetch="none",
    )
    status_str = "activated" if new_status else "deactivated"
    return jsonify({"message": f"Vehicle {status_str}.", "is_active": new_status}), 200


# ── DELETE /api/vehicles/<id> ────────────────────────────────
@vehicles_bp.route("/<int:vehicle_id>", methods=["DELETE"])
@jwt_required()
def delete_vehicle(vehicle_id):
    existing = execute_query(
        "SELECT vehicle_id FROM authorized_vehicles WHERE vehicle_id = %s", (vehicle_id,), fetch="one"
    )
    if not existing:
        return jsonify({"error": "Vehicle not found."}), 404

    execute_query(
        "DELETE FROM authorized_vehicles WHERE vehicle_id = %s", (vehicle_id,), fetch="none"
    )
    return jsonify({"message": "Vehicle deleted."}), 200
