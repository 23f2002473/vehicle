import sys; sys.path.insert(0,".")
from backend.utils.db import execute_query
from backend.utils.auth import hash_password
execute_query(
    "INSERT INTO admin_users (username, password_hash, full_name) VALUES (%s,%s,%s)",
    ("admin", hash_password("admin123"), "System Administrator"),
    fetch="none"
)
print("Admin created: admin / admin123")