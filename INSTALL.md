# Installation

## Requirements

- Python 3.10+
- pip

## Setup

```bash
# 1. Clone and enter the project
cd lumini

# 2. Create virtual environment
python -m venv .venv
source .venv/bin/activate   # Linux/macOS
.venv\Scripts\activate      # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
```

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `SECRET_KEY` | No | auto-generated | Flask session signing key |
| `SENDGRID_API_KEY` | No | — | SendGrid API key for email sending |
| `EMAIL_ORIGEN` | No | `lumini.appag@gmail.com` | Sender email address |
| `FLASK_ENV` | No | `production` | Set to `development` for debug mode |
| `PORT` | No | `8000` (production) / `5000` (dev) | HTTP port |
| `ADMIN_USER` | No | `admin` | Admin panel username |
| `ADMIN_PASS` | No | auto-generated | Admin panel password (written to `admin_password.txt`) |

## Run

```bash
# Development
python flask_app.py
# → http://localhost:5000

# Production (waitress)
FLASK_ENV=production python flask_app.py
# → http://localhost:8000
```

## First Use

1. Open the app and go to `/admin`
2. Log in with the credentials from `admin_password.txt` (or your `ADMIN_USER`/`ADMIN_PASS` env vars)
3. Create a school (colegio) — this generates registration codes
4. Share the teacher registration code so teachers can sign up at `/<slug>/login`
5. Teachers create students, courses, and evaluations
6. Coordinators (directoras) can generate and email report cards

## Database

- `master.db` — school registry (one row per colegio, registration codes, colors)
- `colegios_db/<slug>.db` — per-school database (teachers, students, grades, attendance, communications)
- Backups are created automatically every 24h in the `backups/` directory
