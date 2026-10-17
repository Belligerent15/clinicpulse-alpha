"""
ClinicPulse Alpha — Flask application.

A mobile-first, low-data web app that helps Sekhukhune District residents
find clinics, see live status, queue, and chronic-medication availability.

Run locally:
    pip install -r requirements.txt
    cp .env.example .env   # then edit values
    python database.py
    flask --app app run
"""
import os
import secrets
from functools import wraps
from urllib.parse import quote_plus

from dotenv import load_dotenv
from flask import (
    Flask,
    abort,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

from database import get_connection, init_db, now_iso

load_dotenv()


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get(
        "FLASK_SECRET_KEY", secrets.token_hex(32)
    )
    app.config["ADMIN_USERNAME"] = os.environ.get("ADMIN_USERNAME", "admin")
    # Hash the admin password at startup so we never compare plaintext.
    raw_pw = os.environ.get("ADMIN_PASSWORD", "admin")
    app.config["ADMIN_PASSWORD_HASH"] = generate_password_hash(raw_pw)

    # Ensure DB and tables exist on first run (safe/idempotent).
    init_db()

    register_routes(app)
    register_filters(app)
    register_error_handlers(app)
    return app


# ---------- helpers ---------- #

def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("admin_logged_in"):
            flash("Please sign in to continue.", "warning")
            return redirect(url_for("admin_login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def row_to_clinic(row):
    if row is None:
        return None
    clinic = dict(row)
    services = clinic.get("services") or ""
    clinic["services_list"] = [s.strip() for s in services.split(";") if s.strip()]
    return clinic


def fetch_all_clinics(filters=None):
    filters = filters or {}
    sql = "SELECT * FROM clinics WHERE is_published = 1"
    params = []

    q = (filters.get("q") or "").strip()
    if q:
        sql += " AND (LOWER(name) LIKE ? OR LOWER(village) LIKE ? OR LOWER(town) LIKE ?)"
        like = f"%{q.lower()}%"
        params.extend([like, like, like])

    status = (filters.get("status") or "").strip()
    if status:
        sql += " AND status = ?"
        params.append(status)

    service = (filters.get("service") or "").strip()
    if service:
        sql += " AND LOWER(services) LIKE ?"
        params.append(f"%{service.lower()}%")

    sql += " ORDER BY name ASC"

    conn = get_connection()
    try:
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()
    return [row_to_clinic(r) for r in rows]


def fetch_clinic(clinic_id: int):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM clinics WHERE id = ?", (clinic_id,)
        ).fetchone()
    finally:
        conn.close()
    return row_to_clinic(row)


# ---------- routes ---------- #

def register_routes(app: Flask):

    @app.get("/")
    def index():
        clinics = fetch_all_clinics()
        return render_template("index.html", clinics=clinics)

    @app.get("/clinics")
    def clinics_list():
        filters = {
            "q": request.args.get("q", ""),
            "status": request.args.get("status", ""),
            "service": request.args.get("service", ""),
        }
        clinics = fetch_all_clinics(filters)
        service_options = [
            "Chronic medication",
            "Antenatal care",
            "Immunisation",
            "HIV/TB services",
            "Family planning",
        ]
        status_options = ["Open", "Closed", "Limited"]
        return render_template(
            "clinics.html",
            clinics=clinics,
            filters=filters,
            service_options=service_options,
            status_options=status_options,
        )

    @app.get("/clinics/<int:clinic_id>")
    def clinic_detail(clinic_id):
        clinic = fetch_clinic(clinic_id)
        if not clinic or not clinic.get("is_published"):
            abort(404)

        # Build share and directions URLs here (safer than in Jinja).
        share_text = (
            f"{clinic['name']} ({clinic['village']}) — "
            f"Status: {clinic['status']}, Queue: {clinic['queue_status']}, "
            f"Medicine: {clinic['medication_status']}. "
            f"ClinicPulse: {request.url}"
        )
        clinic["whatsapp_url"] = f"https://wa.me/?text={quote_plus(share_text)}"
        clinic["directions_url"] = (
            f"https://www.openstreetmap.org/directions?to="
            f"{clinic['latitude']},{clinic['longitude']}"
        )
        return render_template("clinic.html", clinic=clinic)

    @app.route("/report/<int:clinic_id>", methods=["GET", "POST"])
    def report(clinic_id):
        clinic = fetch_clinic(clinic_id)
        if not clinic:
            abort(404)

        if request.method == "POST":
            reporter_name = (request.form.get("reporter_name") or "").strip()
            contact = (request.form.get("contact_details") or "").strip()
            issue_type = (request.form.get("issue_type") or "").strip()
            description = (request.form.get("description") or "").strip()

            if not description or not issue_type:
                flash("Please choose an issue type and describe the problem.", "danger")
                return render_template(
                    "report.html",
                    clinic=clinic,
                    form={
                        "reporter_name": reporter_name,
                        "contact_details": contact,
                        "issue_type": issue_type,
                        "description": description,
                    },
                )

            conn = get_connection()
            try:
                conn.execute(
                    """
                    INSERT INTO reports
                        (clinic_id, reporter_name, contact_details,
                         issue_type, description, status, created_at)
                    VALUES (?, ?, ?, ?, ?, 'open', ?)
                    """,
                    (
                        clinic_id,
                        reporter_name or None,
                        contact or None,
                        issue_type,
                        description,
                        now_iso(),
                    ),
                )
                conn.commit()
            finally:
                conn.close()

            flash("Thank you — your report has been received.", "success")
            return redirect(url_for("clinic_detail", clinic_id=clinic_id))

        return render_template("report.html", clinic=clinic, form={})

    @app.get("/about")
    def about():
        return render_template("about.html")

    # ---------- admin ---------- #

    @app.route("/admin/login", methods=["GET", "POST"])
    def admin_login():
        if request.method == "POST":
            username = (request.form.get("username") or "").strip()
            password = request.form.get("password") or ""
            if (
                username == app.config["ADMIN_USERNAME"]
                and check_password_hash(app.config["ADMIN_PASSWORD_HASH"], password)
            ):
                session["admin_logged_in"] = True
                session["admin_user"] = username
                flash("Signed in.", "success")
                next_url = request.args.get("next") or url_for("admin_dashboard")
                return redirect(next_url)
            flash("Invalid username or password.", "danger")
        return render_template("admin/login.html")

    @app.post("/admin/logout")
    def admin_logout():
        session.clear()
        flash("Signed out.", "success")
        return redirect(url_for("index"))

    @app.get("/admin")
    @login_required
    def admin_dashboard():
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT * FROM clinics ORDER BY name ASC"
            ).fetchall()
            reports_count = conn.execute(
                "SELECT COUNT(*) AS c FROM reports WHERE status='open'"
            ).fetchone()["c"]
        finally:
            conn.close()
        clinics = [row_to_clinic(r) for r in rows]
        return render_template(
            "admin/dashboard.html",
            clinics=clinics,
            reports_count=reports_count,
        )

    @app.route(
        "/admin/clinics/<int:clinic_id>/edit", methods=["GET", "POST"]
    )
    @login_required
    def admin_edit_clinic(clinic_id):
        clinic = fetch_clinic(clinic_id)
        if not clinic:
            abort(404)

        if request.method == "POST":
            fields = {
                "name": (request.form.get("name") or "").strip(),
                "village": (request.form.get("village") or "").strip(),
                "town": (request.form.get("town") or "").strip(),
                "address": (request.form.get("address") or "").strip(),
                "phone": (request.form.get("phone") or "").strip(),
                "latitude": request.form.get("latitude") or None,
                "longitude": request.form.get("longitude") or None,
                "operating_hours": (request.form.get("operating_hours") or "").strip(),
                "services": (request.form.get("services") or "").strip(),
                "status": (request.form.get("status") or "Open").strip(),
                "queue_status": (request.form.get("queue_status") or "Short").strip(),
                "medication_status": (
                    request.form.get("medication_status") or "Available"
                ).strip(),
                "is_published": 1 if request.form.get("is_published") else 0,
                "note": (request.form.get("note") or "").strip(),
            }

            if not fields["name"]:
                flash("Clinic name is required.", "danger")
                clinic.update(fields)
                return render_template("admin/edit_clinic.html", clinic=clinic)

            try:
                lat = float(fields["latitude"]) if fields["latitude"] else None
                lng = float(fields["longitude"]) if fields["longitude"] else None
            except ValueError:
                flash("Latitude and longitude must be numbers.", "danger")
                clinic.update(fields)
                return render_template("admin/edit_clinic.html", clinic=clinic)

            updated_at = now_iso()
            conn = get_connection()
            try:
                conn.execute(
                    """
                    UPDATE clinics SET
                        name=?, village=?, town=?, address=?, phone=?,
                        latitude=?, longitude=?, operating_hours=?, services=?,
                        status=?, queue_status=?, medication_status=?,
                        is_published=?, last_updated=?
                    WHERE id=?
                    """,
                    (
                        fields["name"], fields["village"], fields["town"],
                        fields["address"], fields["phone"], lat, lng,
                        fields["operating_hours"], fields["services"],
                        fields["status"], fields["queue_status"],
                        fields["medication_status"], fields["is_published"],
                        updated_at, clinic_id,
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO status_updates
                        (clinic_id, status, queue_status, medication_status,
                         note, updated_by, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        clinic_id, fields["status"], fields["queue_status"],
                        fields["medication_status"], fields["note"] or None,
                        session.get("admin_user") or "admin", updated_at,
                    ),
                )
                conn.commit()
            finally:
                conn.close()

            flash("Clinic updated.", "success")
            return redirect(url_for("admin_dashboard"))

        return render_template("admin/edit_clinic.html", clinic=clinic)

    @app.post("/admin/clinics/<int:clinic_id>/toggle")
    @login_required
    def admin_toggle_clinic(clinic_id):
        clinic = fetch_clinic(clinic_id)
        if not clinic:
            abort(404)
        new_val = 0 if clinic.get("is_published") else 1
        conn = get_connection()
        try:
            conn.execute(
                "UPDATE clinics SET is_published=?, last_updated=? WHERE id=?",
                (new_val, now_iso(), clinic_id),
            )
            conn.commit()
        finally:
            conn.close()
        flash(
            "Clinic " + ("published" if new_val else "hidden") + ".",
            "success",
        )
        return redirect(url_for("admin_dashboard"))

    # ---------- lightweight JSON for map ---------- #

    @app.get("/api/clinics.json")
    def api_clinics():
        clinics = fetch_all_clinics()
        # Only send what the map needs — keep payload small.
        return {
            "clinics": [
                {
                    "id": c["id"],
                    "name": c["name"],
                    "village": c["village"],
                    "town": c["town"],
                    "latitude": c["latitude"],
                    "longitude": c["longitude"],
                    "status": c["status"],
                    "queue_status": c["queue_status"],
                    "medication_status": c["medication_status"],
                }
                for c in clinics
                if c.get("latitude") and c.get("longitude")
            ]
        }


# ---------- filters & errors ---------- #

def register_filters(app: Flask):
    @app.template_filter("status_class")
    def status_class(value: str) -> str:
        if not value:
            return "status-unknown"
        v = value.strip().lower()
        mapping = {
            "open": "status-ok",
            "closed": "status-bad",
            "limited": "status-warn",
            "limited services": "status-warn",
            "short": "status-ok",
            "moderate": "status-warn",
            "long": "status-bad",
            "available": "status-ok",
            "unavailable": "status-bad",
        }
        return mapping.get(v, "status-unknown")


def register_error_handlers(app: Flask):
    @app.errorhandler(404)
    def not_found(_e):
        return render_template("error.html", code=404,
                               message="Page not found."), 404

    @app.errorhandler(500)
    def server_error(_e):
        return render_template("error.html", code=500,
                               message="Something went wrong."), 500


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
