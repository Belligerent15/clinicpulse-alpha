"""
Database initialisation and helpers for ClinicPulse Alpha.

Creates the SQLite tables if they don't exist and imports the sample
clinics from data/clinics.csv (idempotent — won't duplicate on re-runs).

Run directly to initialise the database:
    python database.py
"""
import csv
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = os.environ.get("DATABASE_PATH", str(BASE_DIR / "clinicpulse.db"))
CSV_PATH = BASE_DIR / "data" / "clinics.csv"


def get_connection():
    """Return a SQLite connection with Row factory for dict-like access."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def now_iso() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def create_tables(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS clinics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            village TEXT,
            town TEXT,
            district TEXT,
            province TEXT,
            address TEXT,
            phone TEXT,
            latitude REAL,
            longitude REAL,
            operating_hours TEXT,
            services TEXT,
            status TEXT,
            queue_status TEXT,
            medication_status TEXT,
            last_updated TEXT,
            is_published INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS status_updates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            clinic_id INTEGER NOT NULL,
            status TEXT,
            queue_status TEXT,
            medication_status TEXT,
            note TEXT,
            updated_by TEXT,
            created_at TEXT,
            FOREIGN KEY (clinic_id) REFERENCES clinics(id)
        );

        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            clinic_id INTEGER NOT NULL,
            reporter_name TEXT,
            contact_details TEXT,
            issue_type TEXT,
            description TEXT,
            status TEXT DEFAULT 'open',
            created_at TEXT,
            FOREIGN KEY (clinic_id) REFERENCES clinics(id)
        );
        """
    )
    conn.commit()


def import_clinics_from_csv(conn: sqlite3.Connection) -> int:
    """Import clinics from CSV. Skips rows whose name already exists."""
    if not CSV_PATH.exists():
        print(f"[warn] CSV not found at {CSV_PATH} — skipping import.")
        return 0

    inserted = 0
    cur = conn.cursor()
    with CSV_PATH.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cur.execute("SELECT 1 FROM clinics WHERE name = ?", (row["name"],))
            if cur.fetchone():
                continue
            cur.execute(
                """
                INSERT INTO clinics (
                    name, village, town, district, province, address, phone,
                    latitude, longitude, operating_hours, services,
                    status, queue_status, medication_status,
                    last_updated, is_published
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                """,
                (
                    row["name"],
                    row.get("village"),
                    row.get("town"),
                    row.get("district"),
                    row.get("province"),
                    row.get("address"),
                    row.get("phone"),
                    float(row["latitude"]) if row.get("latitude") else None,
                    float(row["longitude"]) if row.get("longitude") else None,
                    row.get("operating_hours"),
                    row.get("services"),
                    row.get("status") or "Open",
                    row.get("queue_status") or "Short",
                    row.get("medication_status") or "Available",
                    now_iso(),
                ),
            )
            inserted += 1
    conn.commit()
    return inserted


def init_db() -> None:
    conn = get_connection()
    try:
        create_tables(conn)
        inserted = import_clinics_from_csv(conn)
        print(f"[ok] Database ready at {DB_PATH}. Inserted {inserted} new clinic(s).")
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
