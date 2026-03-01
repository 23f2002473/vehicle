"""
svams/backend/routes/users.py
Read-only access to the users table (SVAMS never modifies it)
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from backend.utils.db import execute_query

users_bp = Blueprint("users", __name__, url_prefix="/api/users")


# ── GET /api/users ───────────────────────────────────────────
@users_bp.route("", methods=["GET"])
@jwt_required()
def list_users():
    search   = request.args.get("search", "").strip()
    page     = max(int(request.args.get("page", 1)), 1)
    per_page = min(int(request.args.get("per_page", 20)), 100)
    offset   = (page - 1) * per_page

    conditions = []
    params     = []

    if search:
        conditions.append("(id_temp LIKE %s OR full_name LIKE %s OR department LIKE %s)")
        like = f"%{search}%"
        params += [like, like, like]

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    rows = execute_query(
        f"""
        SELECT u.id_temp, u.full_name, u.email, u.department, u.phone, u.is_active,
               COUNT(av.vehicle_id) AS vehicle_count
        FROM users u
        LEFT JOIN authorized_vehicles av ON av.user_id = u.id_temp AND av.is_active = 1
        {where}
        GROUP BY u.id_temp
        ORDER BY u.full_name
        LIMIT %s OFFSET %s
        """,
        tuple(params) + (per_page, offset),
        fetch="all",
    )

    count_row = execute_query(
        f"SELECT COUNT(*) AS total FROM users {where}", tuple(params), fetch="one"
    )

    return jsonify({"data": rows, "total": count_row["total"], "page": page, "per_page": per_page}), 200


# ── GET /api/users/<id_temp> ─────────────────────────────────
@users_bp.route("/<string:id_temp>", methods=["GET"])
@jwt_required()
def get_user(id_temp):
    user = execute_query(
        "SELECT id_temp, full_name, email, department, phone, is_active FROM users WHERE id_temp = %s",
        (id_temp,),
        fetch="one",
    )
    if not user:
        return jsonify({"error": "User not found."}), 404

    vehicles = execute_query(
        "SELECT * FROM authorized_vehicles WHERE user_id = %s",
        (id_temp,),
        fetch="all",
    )

    return jsonify({"user": user, "vehicles": vehicles}), 200
