"""
Database initialisation and helpers for ClinicPulse Alpha.

Creates the SQLite tables if they don't exist and syncs the sample
clinics from data/clinics.csv (updates existing clinics, adds new ones).
"""
import csv
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
# Ensure the data directory exists
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

DB_PATH = os.environ.get("DATABASE_PATH", str(BASE_DIR / "clinicpulse.db"))
CSV_PATH = DATA_DIR / "clinics.csv"

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
            name TEXT NOT NULL UNIQUE,
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
            FOREIGN KEY (clinic_id) REFERENCES clinics(id) ON DELETE CASCADE
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
            FOREIGN KEY (clinic_id) REFERENCES clinics(id) ON DELETE CASCADE
        );
        """
    )
    conn.commit()

def import_clinics_from_csv(conn: sqlite3.Connection) -> tuple:
    """Import clinics from CSV. Updates existing clinics and adds new ones."""
    if not CSV_PATH.exists():
        print(f"[warn] CSV not found at {CSV_PATH} — skipping import.")
        return 0, 0

    inserted = 0
    updated = 0
    cur = conn.cursor()
    
    with CSV_PATH.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            clinic_name = row["name"].strip()
            
            # Check if clinic exists
            cur.execute("SELECT id FROM clinics WHERE name = ?", (clinic_name,))
            existing = cur.fetchone()
            
            lat = float(row["latitude"]) if row.get("latitude") else None
            lng = float(row["longitude"]) if row.get("longitude") else None

            if existing:
                # Update the existing clinic with the new CSV data
                cur.execute(
                    """
                    UPDATE clinics SET
                        village = ?, town = ?, district = ?, province = ?, address = ?, phone = ?,
                        latitude = ?, longitude = ?, operating_hours = ?, services = ?,
                        status = ?, queue_status = ?, medication_status = ?
                    WHERE id = ?
                    """,
                    (
                        row.get("village"), row.get("town"), row.get("district"), row.get("province"),
                        row.get("address"), row.get("phone"), lat, lng, row.get("operating_hours"),
                        row.get("services"), row.get("status") or "Open", 
                        row.get("queue_status") or "Short", row.get("medication_status") or "Available",
                        existing["id"]
                    )
                )
                updated += 1
            else:
                # Insert a brand new clinic
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
                        clinic_name,
                        row.get("village"),
                        row.get("town"),
                        row.get("district"),
                        row.get("province"),
                        row.get("address"),
                        row.get("phone"),
                        lat,
                        lng,
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
    return inserted, updated

def init_db() -> None:
    conn = get_connection()
    try:
        create_tables(conn)
        inserted, updated = import_clinics_from_csv(conn)
        print(f"[ok] Database ready at {DB_PATH}.")
        print(f"[ok] Inserted {inserted} new clinic(s). Updated {updated} existing clinic(s).")
    finally:
        conn.close()

if __name__ == "__main__":
    init_db()
