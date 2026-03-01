# 🛡️ SVAMS — Smart Vehicle Access Management System

## Project Structure

```
svams/
├── .env                        ← All config (DB credentials, secrets)
├── requirements.txt
├── backend/
│   ├── app.py                  ← Flask entry point
│   ├── routes/
│   │   ├── auth.py             ← POST /api/auth/login, register, me
│   │   ├── verify.py           ← POST /api/verify, /api/exit
│   │   ├── vehicles.py         ← CRUD /api/vehicles
│   │   ├── logs.py             ← GET /api/logs, /api/unauthorized, /api/dashboard/stats
│   │   └── users.py            ← GET /api/users
│   └── utils/
│       ├── db.py               ← MySQL connection pool
│       └── auth.py             ← bcrypt helpers
└── frontend/
    ├── app.py                  ← Streamlit dashboard
    └── api_client.py           ← API wrapper for Streamlit
```

---

## ⚡ Quick Setup

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure .env
Edit `.env` with your MySQL credentials:
```
DB_HOST=localhost
DB_USER=root
DB_PASSWORD=yourpassword
DB_NAME=svams_db
FLASK_SECRET_KEY=your_long_random_key
JWT_SECRET_KEY=another_random_key
```

### 3. Create the database
Run the DB setup script first (from the earlier `svams_db_setup.py`).

### 4. Create first admin (one-time seed)
```python
# run this once in a Python shell from the svams/ directory
import sys; sys.path.insert(0,".")
from backend.utils.db import execute_query
from backend.utils.auth import hash_password
execute_query(
    "INSERT INTO admin_users (username, password_hash, full_name) VALUES (%s,%s,%s)",
    ("admin", hash_password("admin123"), "System Administrator"),
    fetch="none"
)
print("Admin created: admin / admin123")
```

### 5. Start the Flask API
```bash
cd svams
python -m backend.app
# API running at http://localhost:5000
```

### 6. Start the Streamlit UI (new terminal)
```bash
cd svams
streamlit run frontend/app.py
# Dashboard at http://localhost:8501
```

---

## 🔌 API Endpoints Summary

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | /api/auth/login | ❌ | Admin login → returns JWT |
| POST | /api/auth/register | ✅ | Create new admin |
| GET | /api/auth/me | ✅ | Get current admin profile |
| GET | /api/health | ❌ | Health check |
| POST | /api/verify | ❌ | Edge unit: verify plate on entry |
| POST | /api/exit | ❌ | Edge unit: log vehicle exit |
| GET | /api/vehicles | ✅ | List all vehicles (paginated, searchable) |
| POST | /api/vehicles | ✅ | Register new vehicle |
| PUT | /api/vehicles/:id | ✅ | Update vehicle details |
| PATCH | /api/vehicles/:id/toggle | ✅ | Activate / deactivate vehicle |
| DELETE | /api/vehicles/:id | ✅ | Delete vehicle |
| GET | /api/logs | ✅ | Entry/exit log history (filterable) |
| GET | /api/unauthorized | ✅ | Unauthorized attempt log |
| PATCH | /api/unauthorized/:id/alert | ✅ | Mark alert as sent |
| GET | /api/dashboard/stats | ✅ | KPIs + charts data |
| GET | /api/users | ✅ | List org users (read-only) |
| GET | /api/users/:id_temp | ✅ | User detail + their vehicles |

---

## 🖥️ Dashboard Pages

| Page | Features |
|------|----------|
| **Dashboard** | KPI cards, hourly traffic chart, denial reason pie, recent entries |
| **Entry Logs** | Searchable/filterable log table with entry/exit/duration |
| **Unauthorized Alerts** | Alert cards with unread badges, mark-as-sent actions |
| **Vehicle Management** | List with activate/deactivate/delete, register form |
| **Users** | Read-only employee directory with vehicle counts |
| **Settings** | Admin profile view, create new admin account |
