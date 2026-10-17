# ClinicPulse — Alpha

**Tagline:** *Know before you go.*

ClinicPulse is a mobile-first, low-data web app that helps residents of
**Sekhukhune District, Limpopo (South Africa)** find nearby clinics and
check whether a clinic is **open**, what **services** are available,
how long the **queue** is, and whether **chronic medication** is in stock.

> ⚠️ **Alpha release — all clinic data in this repo is sample / unverified.**
> Verify details with each clinic before publishing or relying on them.

---

## Features

- Homepage with search, map (Leaflet + OpenStreetMap), and clinic cards
- "Find clinics near me" using the browser's Geolocation API
- Clinic listing with search and filters (status, service)
- Clinic profile page with hours, services, directions, WhatsApp share, and report link
- Public “Report incorrect information” form
- Password-protected **admin area** to add/edit clinics and update live status
- Mobile-first styling, large touch targets, minimal images

## Technology stack

- **Backend:** Python 3 + Flask
- **Database:** SQLite
- **Frontend:** HTML, CSS, vanilla JavaScript
- **Map:** Leaflet.js (CDN) + OpenStreetMap tiles
- No React, no Next.js, no Docker, no paid APIs

## Project structure

```
clinicpulse-alpha/
├── app.py                 # Flask app, routes, admin
├── database.py            # SQLite init + CSV import
├── requirements.txt
├── .env.example
├── .gitignore
├── data/
│   └── clinics.csv        # Sample (unverified) clinics
├── static/
│   ├── css/style.css
│   └── js/map.js
└── templates/
    ├── base.html
    ├── index.html
    ├── clinics.html
    ├── clinic.html
    ├── report.html
    ├── about.html
    ├── error.html
    ├── _clinic_card.html
    └── admin/
        ├── login.html
        ├── dashboard.html
        └── edit_clinic.html
```

## Run locally

```bash
# 1. Create and activate a virtual env (optional)
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Create a .env from the example and edit values
cp .env.example .env

# 4. Initialise the database (creates clinicpulse.db + imports CSV)
python database.py

# 5. Start the server
flask --app app run
# or:
python app.py
```

Open <http://127.0.0.1:5000>.

## Environment variables

Set these in a local `.env` file (never commit it):

| Name | Purpose |
| --- | --- |
| `FLASK_SECRET_KEY` | Long random string used for session signing |
| `ADMIN_USERNAME` | Username for the admin area |
| `ADMIN_PASSWORD` | Password for the admin area (hashed at startup) |
| `DATABASE_PATH` | Optional; defaults to `clinicpulse.db` |

## Replacing the sample data

Edit `data/clinics.csv` with real, verified clinic details and re-run
`python database.py`. The importer skips rows whose `name` already exists,
so adding new rows is safe. To refresh an existing clinic, edit it from the
admin dashboard.

## Deploy to Render

1. Push the project to GitHub.
2. In Render, create a **Web Service** from the repo.
3. **Build command:** `pip install -r requirements.txt && python database.py`
4. **Start command:** `gunicorn app:app`
5. Add environment variables (`FLASK_SECRET_KEY`, `ADMIN_USERNAME`,
   `ADMIN_PASSWORD`).
6. Render exposes `$PORT` automatically — `gunicorn app:app` honours it.

> SQLite on Render's free tier uses ephemeral disk. For persistence, attach
> a persistent disk or switch to a managed database before launch.

## Disclaimers

- **Data disclaimer:** The 10 clinics shipped in `data/clinics.csv` are
  placeholders with approximate coordinates. All details must be verified
  before public use.
- **Medical disclaimer:** ClinicPulse does **not** provide medical advice,
  diagnosis or treatment. In an emergency call **10177** (South Africa) or
  go to the nearest hospital.

## Roadmap

- Verified clinic directory (replace sample data)
- SMS / USSD channel for feature-phone users
- Multi-user admin with per-clinic roles
- WhatsApp status updates automation
- Analytics for health programmes and NGOs
- Appointments and chronic-medication pickup reminders
