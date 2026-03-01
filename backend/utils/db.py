"""
svams/backend/utils/db.py
MySQL connection pool utility
"""

import mysql.connector
from mysql.connector import pooling, Error
import os
from dotenv import load_dotenv

load_dotenv()

_pool = None

def get_pool():
    global _pool
    if _pool is None:
        _pool = pooling.MySQLConnectionPool(
            pool_name="svams_pool",
            pool_size=5,
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", 3306)),
            user=os.getenv("DB_USER", "root"),
            password=os.getenv("DB_PASSWORD", ""),
            database=os.getenv("DB_NAME", "svams_db"),
            autocommit=False,
            charset="utf8mb4",
        )
    return _pool


def get_connection():
    return get_pool().get_connection()


def execute_query(sql: str, params: tuple = (), fetch: str = "all"):
    """
    Utility wrapper.
    fetch = 'all' | 'one' | 'none'
    Returns list[dict] | dict | None
    """
    conn = get_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(sql, params)

        if fetch == "all":
            result = cursor.fetchall()
        elif fetch == "one":
            result = cursor.fetchone()
        else:
            conn.commit()
            result = {"affected_rows": cursor.rowcount, "lastrowid": cursor.lastrowid}

        return result
    except Error as e:
        conn.rollback()
        raise e
    finally:
        cursor.close()
        conn.close()
