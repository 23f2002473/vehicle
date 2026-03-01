"""
svams/backend/app.py
Flask application factory and entry point

Run:
    python -m backend.app
    -- or --
    cd svams && python -m backend.app
"""

import os
from datetime import timedelta
from flask import Flask, jsonify
from flask_jwt_extended import JWTManager
from dotenv import load_dotenv

load_dotenv()

# ── Blueprints ───────────────────────────────────────────────
from backend.routes.auth     import auth_bp
from backend.routes.verify   import verify_bp
from backend.routes.vehicles import vehicles_bp
from backend.routes.logs     import logs_bp
from backend.routes.users    import users_bp
from backend.routes.stream   import stream_bp


def create_app() -> Flask:
    app = Flask(__name__)

    # Config
    app.config["SECRET_KEY"]                   = os.getenv("FLASK_SECRET_KEY", "dev_secret")
    app.config["JWT_SECRET_KEY"]               = os.getenv("JWT_SECRET_KEY",   "dev_jwt_secret")
    app.config["JWT_ACCESS_TOKEN_EXPIRES"]     = timedelta(hours=8)
    app.config["JWT_TOKEN_LOCATION"]           = ["headers"]
    app.config["JWT_HEADER_NAME"]              = "Authorization"
    app.config["JWT_HEADER_TYPE"]              = "Bearer"

    # JWT
    jwt = JWTManager(app)

    @jwt.unauthorized_loader
    def unauthorized_response(reason):
        return jsonify({"error": "Missing or invalid token.", "detail": reason}), 401

    @jwt.expired_token_loader
    def expired_token_response(jwt_header, jwt_payload):
        return jsonify({"error": "Token has expired. Please log in again."}), 401

    @jwt.invalid_token_loader
    def invalid_token_response(reason):
        return jsonify({"error": "Invalid token.", "detail": reason}), 422

    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(verify_bp)
    app.register_blueprint(vehicles_bp)
    app.register_blueprint(logs_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(stream_bp)

    # Health check
    @app.route("/api/health", methods=["GET"])
    def health():
        return jsonify({"status": "ok", "service": "SVAMS API"}), 200

    return app


if __name__ == "__main__":
    port  = int(os.getenv("FLASK_PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "True").lower() == "true"
    app   = create_app()
    print(f"\n🚀 SVAMS Flask API running on http://localhost:{port}")
    print("   Endpoints:")
    print("   POST  /api/auth/login")
    print("   POST  /api/auth/register")
    print("   GET   /api/auth/me")
    print("   POST  /api/verify")
    print("   POST  /api/exit")
    print("   GET   /api/vehicles")
    print("   POST  /api/vehicles")
    print("   PUT   /api/vehicles/<id>")
    print("   PATCH /api/vehicles/<id>/toggle")
    print("   DELETE /api/vehicles/<id>")
    print("   GET   /api/logs")
    print("   GET   /api/unauthorized")
    print("   GET   /api/dashboard/stats")
    print("   GET   /api/users\n")
    print("   GET   /api/stream/video      ← MJPEG live feed")
    print("   POST  /api/stream/start      ← Start webcam")
    print("   POST  /api/stream/stop       ← Stop webcam")
    print("   GET   /api/stream/status")
    print("   POST  /api/stream/frame      ← Push single frame\n")
    app.run(host="0.0.0.0", port=port, debug=debug)
