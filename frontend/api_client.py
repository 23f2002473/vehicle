"""
frontend/api_client.py
Thin wrapper around the SVAMS Flask API
"""

import os
import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv("API_BASE_URL", "http://localhost:5000/api")
TIMEOUT  = 10


def _headers():
    token = st.session_state.get("token")
    if token:
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    return {"Content-Type": "application/json"}


def _get(path: str, params: dict = None):
    try:
        r = requests.get(f"{BASE_URL}{path}", headers=_headers(), params=params, timeout=TIMEOUT)
        return r.json(), r.status_code
    except Exception as e:
        return {"error": str(e)}, 0


def _post(path: str, payload: dict = None):
    try:
        r = requests.post(f"{BASE_URL}{path}", headers=_headers(), json=payload or {}, timeout=TIMEOUT)
        return r.json(), r.status_code
    except Exception as e:
        return {"error": str(e)}, 0


def _put(path: str, payload: dict = None):
    try:
        r = requests.put(f"{BASE_URL}{path}", headers=_headers(), json=payload or {}, timeout=TIMEOUT)
        return r.json(), r.status_code
    except Exception as e:
        return {"error": str(e)}, 0


def _patch(path: str, payload: dict = None):
    try:
        r = requests.patch(f"{BASE_URL}{path}", headers=_headers(), json=payload or {}, timeout=TIMEOUT)
        return r.json(), r.status_code
    except Exception as e:
        return {"error": str(e)}, 0


def _delete(path: str):
    try:
        r = requests.delete(f"{BASE_URL}{path}", headers=_headers(), timeout=TIMEOUT)
        return r.json(), r.status_code
    except Exception as e:
        return {"error": str(e)}, 0


# ── Auth ─────────────────────────────────────────────────────
def login(username, password):
    return _post("/auth/login", {"username": username, "password": password})

def get_me():
    return _get("/auth/me")

def register_admin(username, password, full_name, email=None):
    return _post("/auth/register", {"username": username, "password": password,
                                    "full_name": full_name, "email": email})

# ── Dashboard ─────────────────────────────────────────────────
def get_stats():
    return _get("/dashboard/stats")

# ── Vehicles ──────────────────────────────────────────────────
def list_vehicles(search="", is_active=None, page=1, per_page=20):
    params = {"page": page, "per_page": per_page}
    if search:   params["search"]    = search
    if is_active is not None: params["is_active"] = is_active
    return _get("/vehicles", params)

def create_vehicle(data: dict):
    return _post("/vehicles", data)

def update_vehicle(vehicle_id, data: dict):
    return _put(f"/vehicles/{vehicle_id}", data)

def toggle_vehicle(vehicle_id):
    return _patch(f"/vehicles/{vehicle_id}/toggle")

def delete_vehicle(vehicle_id):
    return _delete(f"/vehicles/{vehicle_id}")

# ── Logs ──────────────────────────────────────────────────────
def list_logs(search="", date_from=None, date_to=None, still_inside=False, page=1, per_page=30):
    params = {"page": page, "per_page": per_page}
    if search:       params["search"]    = search
    if date_from:    params["date_from"] = str(date_from)
    if date_to:      params["date_to"]   = str(date_to)
    if still_inside: params["still_inside"] = "1"
    return _get("/logs", params)

def list_unauthorized(reason="", date_from=None, date_to=None, page=1, per_page=30):
    params = {"page": page, "per_page": per_page}
    if reason:    params["reason"]    = reason
    if date_from: params["date_from"] = str(date_from)
    if date_to:   params["date_to"]   = str(date_to)
    return _get("/unauthorized", params)

def mark_alert_sent(attempt_id):
    return _patch(f"/unauthorized/{attempt_id}/alert")

# ── Users ─────────────────────────────────────────────────────
def list_users(search="", page=1, per_page=20):
    params = {"page": page, "per_page": per_page}
    if search: params["search"] = search
    return _get("/users", params)

def get_user(id_temp):
    return _get(f"/users/{id_temp}")

# ── Stream / Camera ───────────────────────────────────────────
def stream_status():
    return _get("/stream/status")

def stream_start(direction: str = "ENTRY"):
    return _post("/stream/start", {"direction": direction})

def stream_stop():
    return _post("/stream/stop")
