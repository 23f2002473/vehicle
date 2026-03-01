"""
svams/frontend/app.py
SVAMS — Streamlit Dashboard

Run:
    cd svams
    streamlit run frontend/app.py
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, timedelta

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import frontend.api_client as api

# ═══════════════════════════════════════════════════════════════
# PAGE CONFIG
# ═══════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="SVAMS — Security Dashboard",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ═══════════════════════════════════════════════════════════════
# GLOBAL CSS — Clean Corporate Light
# ═══════════════════════════════════════════════════════════════
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@300;400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap');

html, body, [class*="css"] {
    font-family: 'IBM Plex Sans', sans-serif;
}

/* ── Root palette ── */
:root {
    --primary:    #1a56db;
    --primary-lt: #e8f0fe;
    --success:    #057a55;
    --success-lt: #def7ec;
    --danger:     #c81e1e;
    --danger-lt:  #fde8e8;
    --warning:    #b45309;
    --warning-lt: #fef3c7;
    --neutral:    #374151;
    --border:     #e5e7eb;
    --bg:         #f9fafb;
    --card:       #ffffff;
}

/* ── Main background ── */
.main { background: var(--bg); }
.block-container { padding: 1.5rem 2rem !important; }

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background: #111827 !important;
    border-right: 1px solid #1f2937;
}
[data-testid="stSidebar"] * { color: #d1d5db !important; }
[data-testid="stSidebar"] .stRadio label { 
    padding: 0.5rem 0.75rem;
    border-radius: 6px;
    transition: background 0.15s;
}
[data-testid="stSidebar"] .stRadio label:hover { background: #1f2937; }

/* ── Metric cards ── */
.metric-card {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 1.25rem 1.5rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    border-left: 4px solid var(--primary);
}
.metric-card.green  { border-left-color: var(--success); }
.metric-card.red    { border-left-color: var(--danger);  }
.metric-card.amber  { border-left-color: var(--warning); }
.metric-val  { font-size: 2rem; font-weight: 700; color: var(--neutral); margin: 0; }
.metric-lbl  { font-size: 0.75rem; font-weight: 500; color: #6b7280; text-transform: uppercase; letter-spacing: 0.05em; margin: 0; }

/* ── Section headers ── */
.section-header {
    font-size: 1.05rem;
    font-weight: 600;
    color: #111827;
    border-bottom: 2px solid var(--primary);
    padding-bottom: 0.4rem;
    margin-bottom: 1rem;
}

/* ── Status badges ── */
.badge {
    display: inline-block;
    padding: 0.2rem 0.65rem;
    border-radius: 999px;
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.04em;
}
.badge-green  { background: var(--success-lt); color: var(--success); }
.badge-red    { background: var(--danger-lt);  color: var(--danger);  }
.badge-amber  { background: var(--warning-lt); color: var(--warning); }
.badge-blue   { background: var(--primary-lt); color: var(--primary); }

/* ── Alert banner ── */
.alert-banner {
    background: var(--danger-lt);
    border: 1px solid #f98080;
    border-radius: 8px;
    padding: 0.75rem 1rem;
    font-size: 0.85rem;
    color: var(--danger);
    font-weight: 500;
    margin-bottom: 1rem;
}

/* ── Login card ── */
.login-wrap {
    max-width: 420px;
    margin: 6rem auto;
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 2.5rem;
    box-shadow: 0 4px 20px rgba(0,0,0,0.08);
}
.login-logo {
    font-size: 1.6rem;
    font-weight: 700;
    color: var(--primary);
    margin-bottom: 0.25rem;
}
.login-sub { color: #6b7280; font-size: 0.85rem; margin-bottom: 1.5rem; }

/* ── Dataframe tweaks ── */
[data-testid="stDataFrame"] { border: 1px solid var(--border); border-radius: 8px; }
thead tr th { background: #f3f4f6 !important; }

/* ── Buttons ── */
.stButton > button {
    border-radius: 6px !important;
    font-weight: 500 !important;
    transition: all 0.15s !important;
}
.stButton > button[kind="primary"] {
    background: var(--primary) !important;
    border: none !important;
}

/* ── Forms ── */
.stTextInput input, .stSelectbox select, .stTextArea textarea {
    border-radius: 6px !important;
    border: 1px solid var(--border) !important;
}
</style>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════
# SESSION STATE INIT
# ═══════════════════════════════════════════════════════════════
for key in ["token", "admin_info", "page"]:
    if key not in st.session_state:
        st.session_state[key] = None
if "page" not in st.session_state or st.session_state["page"] is None:
    st.session_state["page"] = "Dashboard"


# ═══════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════
def badge(text, color="blue"):
    return f'<span class="badge badge-{color}">{text}</span>'

def metric_card(label, value, color="blue"):
    return f"""
    <div class="metric-card {color}">
        <p class="metric-lbl">{label}</p>
        <p class="metric-val">{value}</p>
    </div>"""

def section(title):
    st.markdown(f'<div class="section-header">📌 {title}</div>', unsafe_allow_html=True)

def success(msg): st.success(f"✅ {msg}")
def error(msg):   st.error(f"❌ {msg}")
def warn(msg):    st.warning(f"⚠️ {msg}")


# ═══════════════════════════════════════════════════════════════
# LOGIN PAGE
# ═══════════════════════════════════════════════════════════════
def page_login():
    st.markdown("""
    <div class="login-wrap">
        <div class="login-logo">🛡️ SVAMS</div>
        <div class="login-sub">Smart Vehicle Access Management System</div>
    </div>
    """, unsafe_allow_html=True)

    # Center the form
    _, col, _ = st.columns([1, 1.2, 1])
    with col:
        st.markdown("### Admin Login")
        username = st.text_input("Username", placeholder="Enter username")
        password = st.text_input("Password", type="password", placeholder="Enter password")
        if st.button("Login", type="primary", use_container_width=True):
            if not username or not password:
                error("Please fill in all fields.")
            else:
                data, status = api.login(username, password)
                if status == 200:
                    st.session_state["token"]      = data["access_token"]
                    st.session_state["admin_info"] = data["admin"]
                    st.session_state["page"]       = "Dashboard"
                    st.rerun()
                else:
                    error(data.get("error", "Login failed."))


# ═══════════════════════════════════════════════════════════════
# SIDEBAR NAV
# ═══════════════════════════════════════════════════════════════
def sidebar():
    admin = st.session_state.get("admin_info") or {}
    with st.sidebar:
        st.markdown(f"""
        <div style="padding: 1rem 0 1.5rem 0; border-bottom: 1px solid #1f2937; margin-bottom:1rem;">
            <div style="font-size:1.3rem; font-weight:700; color:#f9fafb;">🛡️ SVAMS</div>
            <div style="font-size:0.75rem; color:#9ca3af; margin-top:2px;">Security Dashboard</div>
        </div>
        <div style="font-size:0.78rem; color:#9ca3af; margin-bottom:0.5rem;">
            Logged in as <strong style="color:#d1d5db">{admin.get('username','—')}</strong>
        </div>
        """, unsafe_allow_html=True)

        pages = ["Dashboard", "Live Camera", "Entry Logs", "Unauthorized Alerts", "Vehicle Management", "Users", "Settings"]
        icons = {"Dashboard":"📊", "Live Camera":"📹", "Entry Logs":"📋", "Unauthorized Alerts":"🚨",
                 "Vehicle Management":"🚗", "Users":"👥", "Settings":"⚙️"}

        for p in pages:
            label = f"{icons[p]}  {p}"
            if st.button(label, key=f"nav_{p}",
                         use_container_width=True,
                         type="primary" if st.session_state["page"] == p else "secondary"):
                st.session_state["page"] = p
                st.rerun()

        st.markdown("---")
        if st.button("🔓 Logout", use_container_width=True):
            st.session_state["token"]      = None
            st.session_state["admin_info"] = None
            st.session_state["page"]       = "Dashboard"
            st.rerun()


# ═══════════════════════════════════════════════════════════════
# PAGE: DASHBOARD
# ═══════════════════════════════════════════════════════════════
def page_dashboard():
    st.markdown("## 📊 Dashboard Overview")
    st.caption(f"Today: {date.today().strftime('%A, %d %B %Y')}")

    data, status = api.get_stats()
    if status != 200:
        error("Could not load dashboard stats. Is the Flask API running?")
        return

    # ── KPI Row ─────────────────────────────────────────────
    c1, c2, c3, c4, c5 = st.columns(5)
    kpis = [
        (c1, "Active Vehicles",    data["total_active_vehicles"], "blue"),
        (c2, "Inside Right Now",   data["vehicles_inside_now"],   "green"),
        (c3, "Today's Entries",    data["today_entries"],         "blue"),
        (c4, "Today's Denied",     data["today_denied"],          "red"),
        (c5, "Unread Alerts",      data["unread_alerts"],         "amber"),
    ]
    for col, lbl, val, color in kpis:
        with col:
            st.markdown(metric_card(lbl, val, color), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Alert banner ─────────────────────────────────────────
    if data["unread_alerts"] > 0:
        st.markdown(
            f'<div class="alert-banner">🚨 {data["unread_alerts"]} unread unauthorized access alert(s) require attention.</div>',
            unsafe_allow_html=True,
        )

    # ── Charts row ───────────────────────────────────────────
    col_left, col_right = st.columns([3, 2])

    with col_left:
        section("Today's Hourly Traffic")
        hourly = data.get("hourly_traffic", [])
        if hourly:
            df_h = pd.DataFrame(hourly)
            fig = px.bar(df_h, x="hour", y="entries",
                         labels={"hour": "Hour of Day", "entries": "Vehicles"},
                         color_discrete_sequence=["#1a56db"])
            fig.update_layout(
                margin=dict(l=0, r=0, t=10, b=0),
                plot_bgcolor="white",
                paper_bgcolor="white",
                xaxis=dict(tickmode="linear", dtick=1, gridcolor="#f3f4f6"),
                yaxis=dict(gridcolor="#f3f4f6"),
                font=dict(family="IBM Plex Sans"),
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No entries recorded today yet.")

    with col_right:
        section("Denied Access Reasons Today")
        reasons = data.get("reason_breakdown", [])
        if reasons:
            df_r = pd.DataFrame(reasons)
            fig2 = px.pie(df_r, names="reason", values="cnt",
                          color_discrete_sequence=["#c81e1e", "#b45309", "#1a56db"],
                          hole=0.45)
            fig2.update_layout(
                margin=dict(l=0, r=0, t=10, b=0),
                paper_bgcolor="white",
                font=dict(family="IBM Plex Sans"),
                legend=dict(orientation="h"),
            )
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("No denied attempts today.")

    # ── Recent Entries ────────────────────────────────────────
    section("Recent Entries")
    recent = data.get("recent_entries", [])
    if recent:
        df_rec = pd.DataFrame(recent)
        df_rec["Status"] = df_rec["exit_time"].apply(
            lambda x: "🟢 Inside" if x is None else "⚪ Exited"
        )
        df_rec = df_rec.rename(columns={
            "plate_number": "Plate", "full_name": "Owner",
            "vehicle_type": "Type", "entry_time": "Entry Time",
        })[["Plate", "Owner", "Type", "Entry Time", "Status"]]
        st.dataframe(df_rec, use_container_width=True, hide_index=True)
    else:
        st.info("No recent entries.")


# ═══════════════════════════════════════════════════════════════
# PAGE: ENTRY LOGS
# ═══════════════════════════════════════════════════════════════
def page_entry_logs():
    st.markdown("## 📋 Entry & Exit Logs")

    # ── Filters ──────────────────────────────────────────────
    with st.expander("🔍 Filters", expanded=True):
        fc1, fc2, fc3, fc4 = st.columns(4)
        with fc1: search     = st.text_input("Search plate", placeholder="e.g. MH12AB1234")
        with fc2: date_from  = st.date_input("From", value=date.today() - timedelta(days=7))
        with fc3: date_to    = st.date_input("To",   value=date.today())
        with fc4:
            st.markdown("<br>", unsafe_allow_html=True)
            still_inside = st.checkbox("Still inside only")

    data, status = api.list_logs(
        search=search, date_from=date_from, date_to=date_to, still_inside=still_inside
    )

    if status != 200:
        error("Failed to load logs.")
        return

    rows  = data.get("data", [])
    total = data.get("total", 0)
    st.caption(f"{total} record(s) found")

    if rows:
        df = pd.DataFrame(rows)
        display_cols = {
            "plate_number":   "Plate",
            "full_name":      "Owner",
            "department":     "Department",
            "vehicle_type":   "Type",
            "entry_time":     "Entry",
            "exit_time":      "Exit",
            "duration_minutes":"Duration (min)",
            "ocr_confidence": "OCR %",
        }
        df = df[[c for c in display_cols if c in df.columns]].rename(columns=display_cols)
        df["Exit"] = df["Exit"].fillna("— still inside")
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No logs found for selected filters.")


# ═══════════════════════════════════════════════════════════════
# PAGE: UNAUTHORIZED ALERTS
# ═══════════════════════════════════════════════════════════════
def page_unauthorized():
    st.markdown("## 🚨 Unauthorized Access Alerts")

    with st.expander("🔍 Filters", expanded=True):
        fc1, fc2, fc3, fc4 = st.columns(4)
        with fc1:
            reason = st.selectbox("Reason", ["", "NOT_REGISTERED", "DEACTIVATED", "LOW_OCR_CONFIDENCE"])
        with fc2: date_from = st.date_input("From", value=date.today() - timedelta(days=7))
        with fc3: date_to   = st.date_input("To",   value=date.today())
        with fc4:
            st.markdown("<br>", unsafe_allow_html=True)
            auto_mark = st.checkbox("Auto-mark viewed as sent")

    data, status = api.list_unauthorized(reason=reason, date_from=date_from, date_to=date_to)

    if status != 200:
        error("Failed to load unauthorized attempts.")
        return

    rows  = data.get("data", [])
    total = data.get("total", 0)
    st.caption(f"{total} record(s) found")

    if not rows:
        st.info("No unauthorized attempts found.")
        return

    for row in rows:
        alert_color = "#fde8e8" if not row["alert_sent"] else "#f9fafb"
        border_col  = "#c81e1e" if not row["alert_sent"] else "#d1d5db"

        with st.container():
            st.markdown(f"""
            <div style="background:{alert_color}; border:1px solid {border_col}; border-left: 4px solid {border_col};
                        border-radius:8px; padding:0.85rem 1.1rem; margin-bottom:0.6rem;">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <div>
                        <strong style="font-size:1rem; font-family:'IBM Plex Mono',monospace">
                            {row['plate_number']}
                        </strong>
                        &nbsp;·&nbsp;
                        <span style="font-size:0.78rem; color:#6b7280">{row['attempt_time']}</span>
                    </div>
                    <div>
                        <span class="badge badge-{'red' if not row['alert_sent'] else 'green'}">
                            {'⚠ Unread' if not row['alert_sent'] else '✓ Sent'}
                        </span>
                    </div>
                </div>
                <div style="margin-top:0.4rem; font-size:0.82rem; color:#374151">
                    <strong>Reason:</strong> {row['reason']} &nbsp;|&nbsp;
                    <strong>Direction:</strong> {row['direction']} &nbsp;|&nbsp;
                    <strong>OCR:</strong> {row.get('ocr_confidence', '—')}%
                </div>
            </div>
            """, unsafe_allow_html=True)

            if not row["alert_sent"]:
                col_btn, _ = st.columns([1, 5])
                with col_btn:
                    if st.button("✅ Mark Sent", key=f"alert_{row['attempt_id']}"):
                        api.mark_alert_sent(row["attempt_id"])
                        st.rerun()


# ═══════════════════════════════════════════════════════════════
# PAGE: VEHICLE MANAGEMENT
# ═══════════════════════════════════════════════════════════════
def page_vehicles():
    st.markdown("## 🚗 Vehicle Management")

    tab1, tab2 = st.tabs(["📋 Vehicle List", "➕ Register New Vehicle"])

    # ── Tab 1: List ──────────────────────────────────────────
    with tab1:
        sc1, sc2, sc3 = st.columns([3, 1, 1])
        with sc1: search    = st.text_input("Search plate, owner or ID", placeholder="Search...")
        with sc2: status_f  = st.selectbox("Status", ["All", "Active", "Inactive"])
        with sc3: st.markdown("<br>", unsafe_allow_html=True)

        is_active_param = None
        if status_f == "Active":   is_active_param = 1
        if status_f == "Inactive": is_active_param = 0

        data, status = api.list_vehicles(search=search, is_active=is_active_param)
        if status != 200:
            error("Failed to load vehicles.")
            return

        rows  = data.get("data", [])
        total = data.get("total", 0)
        st.caption(f"{total} vehicle(s) found")

        if not rows:
            st.info("No vehicles found.")
        else:
            for v in rows:
                is_active = v.get("is_active", 1)
                bg = "#ffffff" if is_active else "#f9fafb"

                with st.container():
                    col_info, col_actions = st.columns([5, 1])
                    with col_info:
                        st.markdown(f"""
                        <div style="background:{bg}; border:1px solid #e5e7eb; border-radius:8px;
                                    padding:0.8rem 1rem; margin-bottom:0.5rem;">
                            <div style="display:flex; align-items:center; gap:0.75rem;">
                                <span style="font-family:'IBM Plex Mono',monospace; font-weight:600; font-size:1rem;">
                                    {v['plate_number']}
                                </span>
                                {'<span class="badge badge-green">Active</span>' if is_active else '<span class="badge badge-red">Inactive</span>'}
                                <span class="badge badge-blue">{v.get('vehicle_type','—')}</span>
                            </div>
                            <div style="margin-top:0.3rem; font-size:0.82rem; color:#6b7280;">
                                👤 {v.get('full_name','—')} ({v.get('user_id','—')}) &nbsp;|&nbsp;
                                🏢 {v.get('department','—')} &nbsp;|&nbsp;
                                🚘 {v.get('vehicle_make','—')} {v.get('vehicle_model','—')} · {v.get('vehicle_color','—')}
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

                    with col_actions:
                        vid = v["vehicle_id"]
                        btn_label = "Deactivate" if is_active else "Activate"
                        if st.button(btn_label, key=f"tog_{vid}", use_container_width=True):
                            res, s = api.toggle_vehicle(vid)
                            if s == 200: success(res["message"]); st.rerun()
                            else: error(res.get("error", "Failed."))
                        if st.button("🗑 Delete", key=f"del_{vid}", use_container_width=True):
                            res, s = api.delete_vehicle(vid)
                            if s == 200: success("Vehicle deleted."); st.rerun()
                            else: error(res.get("error", "Failed."))

    # ── Tab 2: Register ──────────────────────────────────────
    with tab2:
        st.markdown("#### Register a New Vehicle")
        with st.form("register_vehicle_form"):
            rc1, rc2 = st.columns(2)
            with rc1:
                user_id      = st.text_input("Employee ID (id_temp)*", placeholder="e.g. EMP001")
                plate_number = st.text_input("Plate Number*", placeholder="e.g. MH12AB1234")
                vehicle_type = st.selectbox("Vehicle Type*", ["CAR", "MOTORCYCLE", "SUV", "TRUCK", "OTHER"])
            with rc2:
                vehicle_make  = st.text_input("Make",  placeholder="e.g. Hyundai")
                vehicle_model = st.text_input("Model", placeholder="e.g. Creta")
                vehicle_color = st.text_input("Color", placeholder="e.g. White")
            notes = st.text_area("Notes (optional)", height=80)

            submitted = st.form_submit_button("Register Vehicle", type="primary")
            if submitted:
                if not user_id or not plate_number or not vehicle_type:
                    warn("Employee ID, Plate Number and Vehicle Type are required.")
                else:
                    res, s = api.create_vehicle({
                        "user_id": user_id, "plate_number": plate_number,
                        "vehicle_type": vehicle_type, "vehicle_make": vehicle_make,
                        "vehicle_model": vehicle_model, "vehicle_color": vehicle_color,
                        "notes": notes,
                    })
                    if s == 201: success(f"Vehicle registered! ID: {res['vehicle_id']}")
                    else: error(res.get("error", "Registration failed."))


# ═══════════════════════════════════════════════════════════════
# PAGE: USERS
# ═══════════════════════════════════════════════════════════════
def page_users():
    st.markdown("## 👥 Users (Read-Only)")
    search = st.text_input("Search by ID, name or department", placeholder="Search...")

    data, status = api.list_users(search=search)
    if status != 200:
        error("Failed to load users.")
        return

    rows = data.get("data", [])
    st.caption(f"{data.get('total', 0)} user(s) found")

    if rows:
        df = pd.DataFrame(rows)
        rename = {"id_temp":"Employee ID","full_name":"Name","department":"Department",
                  "phone":"Phone","email":"Email","is_active":"Active","vehicle_count":"Vehicles"}
        df = df[[c for c in rename if c in df.columns]].rename(columns=rename)
        df["Active"] = df["Active"].map({1: "✅ Yes", 0: "❌ No"})
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No users found.")


# ═══════════════════════════════════════════════════════════════
# PAGE: SETTINGS
# ═══════════════════════════════════════════════════════════════
def page_settings():
    st.markdown("## ⚙️ Settings")

    tab1, tab2 = st.tabs(["👤 My Profile", "➕ Create Admin"])

    with tab1:
        me, status = api.get_me()
        if status == 200:
            st.markdown(f"""
            | Field | Value |
            |---|---|
            | **Admin ID** | {me.get('admin_id')} |
            | **Username** | {me.get('username')} |
            | **Full Name** | {me.get('full_name')} |
            | **Email** | {me.get('email', '—')} |
            | **Since** | {me.get('created_at')} |
            """)
        else:
            error("Could not load profile.")

    with tab2:
        st.markdown("#### Create New Admin Account")
        with st.form("create_admin_form"):
            a1, a2 = st.columns(2)
            with a1:
                new_username  = st.text_input("Username*")
                new_password  = st.text_input("Password*", type="password")
            with a2:
                new_fullname  = st.text_input("Full Name*")
                new_email     = st.text_input("Email (optional)")

            if st.form_submit_button("Create Admin", type="primary"):
                if not new_username or not new_password or not new_fullname:
                    warn("Username, password and full name are required.")
                else:
                    res, s = api.register_admin(new_username, new_password, new_fullname, new_email or None)
                    if s == 201: success(f"Admin created. ID: {res['admin_id']}")
                    else: error(res.get("error", "Failed to create admin."))


# ═══════════════════════════════════════════════════════════════
# PAGE: LIVE CAMERA
# ═══════════════════════════════════════════════════════════════
def page_live_camera():
    import time as _time
    st.markdown("## 📹 Live Camera Feed")

    API_BASE = os.getenv("API_BASE_URL", "http://localhost:5000/api")
    STREAM_URL = API_BASE.replace("/api", "") + "/api/stream/video"

    # ── Camera controls ───────────────────────────────────────
    col1, col2, col3 = st.columns([1, 1, 3])
    with col1:
        direction = st.selectbox("Gate Direction", ["ENTRY", "EXIT"])
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        start_clicked = st.button("▶ Start Camera", type="primary", use_container_width=True)
    with col3:
        st.markdown("<br>", unsafe_allow_html=True)
        stop_clicked = st.button("⏹ Stop Camera", use_container_width=True)

    # Status
    status_data, s = api._get("/stream/status")
    is_running = status_data.get("running", False) if s == 200 else False

    if start_clicked:
        res, s = api._post("/stream/start", {"direction": direction})
        if s == 200:
            success(res.get("message", "Camera started."))
            is_running = True
            st.rerun()
        else:
            error(res.get("error", "Failed to start camera."))

    if stop_clicked:
        res, s = api._post("/stream/stop")
        if s == 200:
            success("Camera stopped.")
            is_running = False
            st.rerun()
        else:
            error(res.get("error", "Failed to stop."))

    # Status badge
    if is_running:
        st.markdown('<span class="badge badge-green">● LIVE</span>', unsafe_allow_html=True)
    else:
        st.markdown('<span class="badge badge-red">● OFFLINE</span>', unsafe_allow_html=True)

    st.markdown("---")

    # ── Live feed ─────────────────────────────────────────────
    col_feed, col_info = st.columns([3, 2])

    with col_feed:
        section("Camera Feed")
        if is_running:
            st.markdown(f"""
            <div style="border:2px solid #1a56db; border-radius:10px; overflow:hidden;">
                <img src="{STREAM_URL}" width="100%"
                     style="display:block;"
                     onerror="this.style.display='none'"/>
            </div>
            <p style="font-size:0.75rem; color:#6b7280; margin-top:0.4rem;">
                MJPEG stream · {STREAM_URL}
            </p>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div style="background:#f3f4f6; border:2px dashed #d1d5db; border-radius:10px;
                        height:300px; display:flex; align-items:center; justify-content:center;">
                <div style="text-align:center; color:#9ca3af;">
                    <div style="font-size:3rem;">📷</div>
                    <div style="margin-top:0.5rem; font-weight:500;">Camera offline</div>
                    <div style="font-size:0.8rem;">Press ▶ Start Camera to begin</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

    with col_info:
        section("Detection Info")
        st.markdown("""
        **How it works:**

        1. **YOLO** scans each frame for license plate regions
        2. Detected regions are **cropped & sharpened**
        3. **EasyOCR** reads the plate text
        4. Plate is **normalized** (spaces/dashes removed)
        5. Flask `/api/verify` is called automatically
        6. Entry is **logged** or **denied** in the database

        ---
        **Thresholds:**
        - YOLO confidence ≥ 45%
        - OCR confidence ≥ 60%
        - Same plate suppressed for 30 seconds
        """)

        st.markdown("---")
        section("Recent Detections")

        # Show last 5 entries from today
        logs_data, _ = api.list_logs(date_from=_time.strftime("%Y-%m-%d"),
                                      date_to=_time.strftime("%Y-%m-%d"), per_page=5)
        recent = logs_data.get("data", [])
        if recent:
            for row in recent:
                color = "#def7ec" if row.get("exit_time") is None else "#f9fafb"
                st.markdown(f"""
                <div style="background:{color}; border:1px solid #e5e7eb;
                            border-radius:6px; padding:0.5rem 0.75rem; margin-bottom:0.4rem;
                            font-size:0.82rem;">
                    <strong style="font-family:'IBM Plex Mono',monospace">{row['plate_number']}</strong>
                    &nbsp;·&nbsp; {row.get('full_name','Unknown')}
                    <br><span style="color:#6b7280">{row['entry_time']}</span>
                    &nbsp;
                    {'<span class="badge badge-green">Inside</span>'
                     if row.get('exit_time') is None
                     else '<span class="badge badge-blue">Exited</span>'}
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("No entries today yet.")

        if is_running:
            st.button("🔄 Refresh", on_click=st.rerun)



def main():
    if not st.session_state.get("token"):
        page_login()
        return

    sidebar()

    page = st.session_state.get("page", "Dashboard")
    if   page == "Dashboard":             page_dashboard()
    elif page == "Live Camera":           page_live_camera()
    elif page == "Entry Logs":            page_entry_logs()
    elif page == "Unauthorized Alerts":   page_unauthorized()
    elif page == "Vehicle Management":    page_vehicles()
    elif page == "Users":                 page_users()
    elif page == "Settings":              page_settings()


if __name__ == "__main__":
    main()
