# LIDMS

## About

**Lab Information Digitalization and Management Systems (LIDMS)** is a group college minor project for managing laboratory equipment, stock requests and maintenance. It connects administrators, faculty and technicians through role-based dashboards, approval workflows and shared records.

## Key Features

- Equipment inventory, stock adjustments and low-stock tracking.
- Equipment requests, approvals, issues and partial/full returns.
- Hardware/software complaints, technician assignments and repair tracking.
- Role-based dashboards, activity history and notifications.
- Inventory, request and complaint CSV reports.
- Account approval, role management, profiles and password changes.
- Responsive pages for desktop, tablet and mobile.

## Live Website

[Open LIDMS](https://lidms.vercel.app/)

Select **Demo account credentials** on the login page to explore the three roles using sample data.

## Tech Stack

| Layer | Technology |
| --- | --- |
| Backend | Python 3.14, Django 5.2 |
| Frontend | Django templates, HTML, CSS, JavaScript |
| Database | Neon PostgreSQL; SQLite for local development and tests |
| Hosting | Vercel |
| Testing | Django tests, Ruff, Playwright |

## Prerequisites

- Python 3.14 and the project source.
- Neon connection details when using PostgreSQL.
- Windows PowerShell for the commands below. On macOS/Linux, use `.venv/bin/python` instead of `.venv\Scripts\python.exe`.

## Installation & Environment Setup

Run from the repository root (`LIDMS_Code` in the local project folder):

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env.local
```

For a fresh setup, generate a key and save it as `DJANGO_SECRET_KEY` in `.env.local`. Keep existing environment files when the project is already configured.

```powershell
.\.venv\Scripts\python.exe -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Leave `DATABASE_URL` blank for SQLite. To use Neon, copy `.env.neon.example` to `.env.neon` and fill in its pooled and direct connection URLs. Keep environment files private.

The configured local app and live website share Neon records. Local changes therefore affect the live data; do not seed or reimport the existing shared database.

## Local Run, Build & Test Commands

Initialize a new database and create an administrator:

```powershell
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py createsuperuser
```

Start the application:

```powershell
.\.venv\Scripts\python.exe manage.py runserver
```

Open `http://127.0.0.1:8000/`.

Collect static files for deployment:

```powershell
.\.venv\Scripts\python.exe manage.py --env-file .env.local collectstatic --noinput
```

Run checks with `.env.local` configured for SQLite:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\ruff.exe format --check .
.\.venv\Scripts\python.exe manage.py --env-file .env.local test --noinput
```

## Project Structure

```text
LIDMS/
|-- LIDMS_Code/             # Application and public README
|   |-- inventory/          # Models, workflows, permissions and tests
|   |-- lidms/              # Settings, routes and entrypoints
|   |-- templates/          # Page templates
|   |-- static/             # Styles, scripts and runtime assets
|   `-- tools/              # Browser verification
|-- LIDMS_Docs/             # PROJECT_DETAILS.md and CASE_STUDY.md
|-- LIDMS_College_Documents/ # College reports and supporting material
|-- LIDMS_Assets/           # Branding library and logo candidates
`-- LIDMS_Visuals/           # Reserved for future visuals
```

Only `LIDMS_Code` is the Git repository. Private documents, assets, environment files and database backups are not published.

## Acknowledgements & Credits

The bundled Mulish font is distributed under the SIL Open Font License, included in `static/fonts/OFL.txt`.
