"""
SVAMS — Smart Vehicle Access Management System
MySQL Database Setup Script
------------------------------------------------------------
Requirements:
    pip install mysql-connector-python

Usage:
    python svams_db_setup.py

Edit the DB_CONFIG section below with your MySQL credentials.
"""

import mysql.connector
from mysql.connector import Error

# ============================================================
# DB CONFIGURATION — update these values
# ============================================================
DB_CONFIG = {
    "host":     "localhost",
    "port":     3306,
    "user": "root", # your MySQL username
    "password": "newpassword123", # your MySQL password
}

DATABASE_NAME = "svams_db"

# ============================================================
# SQL STATEMENTS
# ============================================================

CREATE_DATABASE = f"CREATE DATABASE IF NOT EXISTS `{DATABASE_NAME}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

TABLES = {

    "1_users": """
        CREATE TABLE IF NOT EXISTS users (
            id_temp         VARCHAR(20)     NOT NULL,
            full_name       VARCHAR(100)    NOT NULL,
            email           VARCHAR(100)    UNIQUE,
            department      VARCHAR(100)    NULL,
            phone           VARCHAR(20)     NULL,
            is_active       TINYINT(1)      DEFAULT 1,
            created_at      DATETIME        DEFAULT NOW(),
            PRIMARY KEY (id_temp)
        ) ENGINE=InnoDB;
    """,

    "2_admin_users": """
        CREATE TABLE IF NOT EXISTS admin_users (
            admin_id        INT UNSIGNED    NOT NULL AUTO_INCREMENT,
            username        VARCHAR(60)     NOT NULL UNIQUE,
            password_hash   VARCHAR(255)    NOT NULL,
            full_name       VARCHAR(100)    NULL,
            email           VARCHAR(100)    UNIQUE,
            is_active       TINYINT(1)      DEFAULT 1,
            created_at      DATETIME        DEFAULT NOW(),
            PRIMARY KEY (admin_id)
        ) ENGINE=InnoDB;
    """,

    "3_authorized_vehicles": """
        CREATE TABLE IF NOT EXISTS authorized_vehicles (
            vehicle_id      INT UNSIGNED    NOT NULL AUTO_INCREMENT,
            user_id         VARCHAR(20)     NOT NULL,
            plate_number    VARCHAR(20)     NOT NULL UNIQUE,
            vehicle_type    ENUM('CAR','MOTORCYCLE','SUV','TRUCK','OTHER') NOT NULL,
            vehicle_make    VARCHAR(60)     NULL,
            vehicle_model   VARCHAR(60)     NULL,
            vehicle_color   VARCHAR(40)     NULL,
            is_active       TINYINT(1)      DEFAULT 1,
            registered_by   INT UNSIGNED    NOT NULL,
            registered_at   DATETIME        DEFAULT NOW(),
            notes           TEXT            NULL,
            PRIMARY KEY (vehicle_id),
            CONSTRAINT fk_av_user
                FOREIGN KEY (user_id)       REFERENCES users(id_temp)        ON UPDATE CASCADE ON DELETE RESTRICT,
            CONSTRAINT fk_av_admin
                FOREIGN KEY (registered_by) REFERENCES admin_users(admin_id) ON UPDATE CASCADE ON DELETE RESTRICT
        ) ENGINE=InnoDB;
    """,

    "4_entry_logs": """
        CREATE TABLE IF NOT EXISTS entry_logs (
            log_id              BIGINT UNSIGNED     NOT NULL AUTO_INCREMENT,
            plate_number        VARCHAR(20)         NOT NULL,
            vehicle_id          INT UNSIGNED        NULL,
            user_id             VARCHAR(20)         NULL,
            entry_time          DATETIME            NOT NULL,
            exit_time           DATETIME            NULL,
            duration_minutes    INT UNSIGNED        GENERATED ALWAYS AS (
                                    TIMESTAMPDIFF(MINUTE, entry_time, exit_time)
                                ) VIRTUAL,
            entry_image_path    VARCHAR(255)        NULL,
            exit_image_path     VARCHAR(255)        NULL,
            ocr_confidence      DECIMAL(5,2)        NULL,
            remarks             VARCHAR(255)        NULL,
            PRIMARY KEY (log_id),
            INDEX idx_plate  (plate_number),
            INDEX idx_entry  (entry_time),
            CONSTRAINT fk_el_vehicle
                FOREIGN KEY (vehicle_id) REFERENCES authorized_vehicles(vehicle_id) ON UPDATE CASCADE ON DELETE SET NULL,
            CONSTRAINT fk_el_user
                FOREIGN KEY (user_id)    REFERENCES users(id_temp)                  ON UPDATE CASCADE ON DELETE SET NULL
        ) ENGINE=InnoDB;
    """,

    "5_unauthorized_attempts": """
        CREATE TABLE IF NOT EXISTS unauthorized_attempts (
            attempt_id      BIGINT UNSIGNED     NOT NULL AUTO_INCREMENT,
            plate_number    VARCHAR(20)         NOT NULL,
            attempt_time    DATETIME            NOT NULL,
            direction       ENUM('ENTRY','EXIT') NOT NULL,
            reason          ENUM(
                                'NOT_REGISTERED',
                                'DEACTIVATED',
                                'LOW_OCR_CONFIDENCE'
                            )                   NOT NULL,
            image_path      VARCHAR(255)        NULL,
            ocr_confidence  DECIMAL(5,2)        NULL,
            alert_sent      TINYINT(1)          DEFAULT 0,
            PRIMARY KEY (attempt_id),
            INDEX idx_ua_plate (plate_number),
            INDEX idx_ua_time  (attempt_time)
        ) ENGINE=InnoDB;
    """,
}

# ============================================================
# SETUP FUNCTION
# ============================================================

def setup_database():
    connection = None
    try:
        # Step 1 — Connect without selecting a DB
        print(" Connecting to MySQL server...")
        connection = mysql.connector.connect(**DB_CONFIG)
        cursor = connection.cursor()

        # Step 2 — Create database
        print(f" Creating database '{DATABASE_NAME}' if not exists...")
        cursor.execute(CREATE_DATABASE)
        print(f"    Database '{DATABASE_NAME}' ready.")

        # Step 3 — Switch to the database
        cursor.execute(f"USE `{DATABASE_NAME}`;")

        # Step 4 — Create tables in order
        for table_key, ddl in TABLES.items():
            table_name = table_key.split("_", 1)[1]  # strip leading number
            print(f" Creating table '{table_name}'...")
            cursor.execute(ddl)
            print(f"   Table '{table_name}' created.")

        connection.commit()
        print("\n SVAMS database setup complete!")
        print(f"   Database : {DATABASE_NAME}")
        print(f"   Tables   : {', '.join(t.split('_',1)[1] for t in TABLES.keys())}")

    except Error as e:
        print(f"\n MySQL Error: {e}")

    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()
            print(" Connection closed.")


if __name__ == "__main__":
    setup_database()