"""
svams/backend/routes/auth.py
Admin authentication endpoints
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from backend.utils.db import execute_query
from backend.utils.auth import hash_password, verify_password

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


# ── POST /api/auth/login ─────────────────────────────────────
@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")

    if not username or not password:
        return jsonify({"error": "Username and password are required."}), 400

    admin = execute_query(
        "SELECT * FROM admin_users WHERE username = %s AND is_active = 1",
        (username,),
        fetch="one",
    )

    if not admin or not verify_password(password, admin["password_hash"]):
        return jsonify({"error": "Invalid credentials."}), 401

    token = create_access_token(
        identity=str(admin["admin_id"]),
        additional_claims={"username": admin["username"], "full_name": admin["full_name"]},
    )

    return jsonify({
        "access_token": token,
        "admin": {
            "admin_id": admin["admin_id"],
            "username": admin["username"],
            "full_name": admin["full_name"],
        },
    }), 200


# ── POST /api/auth/register ──────────────────────────────────
@auth_bp.route("/register", methods=["POST"])
@jwt_required()
def register_admin():
    """Create a new admin (only existing admins can do this)."""
    data = request.get_json(silent=True) or {}
    username  = data.get("username", "").strip()
    password  = data.get("password", "")
    full_name = data.get("full_name", "").strip()
    email     = data.get("email", "").strip() or None

    if not username or not password or not full_name:
        return jsonify({"error": "username, password, full_name are required."}), 400

    existing = execute_query(
        "SELECT admin_id FROM admin_users WHERE username = %s", (username,), fetch="one"
    )
    if existing:
        return jsonify({"error": "Username already exists."}), 409

    hashed = hash_password(password)
    result = execute_query(
        "INSERT INTO admin_users (username, password_hash, full_name, email) VALUES (%s,%s,%s,%s)",
        (username, hashed, full_name, email),
        fetch="none",
    )
    return jsonify({"message": "Admin created.", "admin_id": result["lastrowid"]}), 201


# ── GET /api/auth/me ─────────────────────────────────────────
@auth_bp.route("/me", methods=["GET"])
@jwt_required()
def me():
    admin_id = int(get_jwt_identity())
    admin = execute_query(
        "SELECT admin_id, username, full_name, email, created_at FROM admin_users WHERE admin_id = %s",
        (admin_id,),
        fetch="one",
    )
    if not admin:
        return jsonify({"error": "Admin not found."}), 404
    return jsonify(admin), 200
